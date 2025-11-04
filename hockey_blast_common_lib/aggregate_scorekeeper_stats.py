import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import sqlalchemy
from sqlalchemy.sql import func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Game, ScorekeeperSaveQuality
from hockey_blast_common_lib.options import (
    MIN_GAMES_FOR_ORG_STATS,
)
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    OrgStatsDailyScorekeeper,
    OrgStatsScorekeeper,
    OrgStatsWeeklyScorekeeper,
)
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID
from hockey_blast_common_lib.utils import (
    assign_ranks,
    calculate_percentile_value,
    get_non_human_ids,
    get_percentile_human,
    get_start_datetime,
)

# Import status constants for game filtering
FINAL_STATUS = "Final"
FINAL_SO_STATUS = "Final(SO)"
FORFEIT_STATUS = "FORFEIT"
NOEVENTS_STATUS = "NOEVENTS"


def insert_percentile_markers_scorekeeper(
    session, stats_dict, aggregation_id, total_in_rank, StatsModel
):
    """Insert percentile marker records for scorekeeper stats."""
    if not stats_dict:
        return

    stat_fields = [
        "games_recorded",
        "games_participated",
        "games_with_stats",
        "sog_given",
        "sog_per_game",
        "total_saves_recorded",
        "avg_saves_per_game",
        "avg_max_saves_per_5sec",
        "avg_max_saves_per_20sec",
        "peak_max_saves_per_5sec",
        "peak_max_saves_per_20sec",
        "quality_score",
    ]

    percentiles = [25, 50, 75, 90, 95]

    for percentile in percentiles:
        percentile_human_id = get_percentile_human(session, "Scorekeeper", percentile)

        percentile_values = {}
        for field in stat_fields:
            values = [stat[field] for stat in stats_dict.values() if field in stat]
            if values:
                percentile_values[field] = calculate_percentile_value(values, percentile)
            else:
                percentile_values[field] = 0

        scorekeeper_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=percentile_human_id,
            games_recorded=int(percentile_values.get("games_recorded", 0)),
            games_participated=int(percentile_values.get("games_participated", 0)),
            games_participated_rank=0,
            games_with_stats=int(percentile_values.get("games_with_stats", 0)),
            games_with_stats_rank=0,
            sog_given=int(percentile_values.get("sog_given", 0)),
            sog_per_game=percentile_values.get("sog_per_game", 0.0),
            total_saves_recorded=int(percentile_values.get("total_saves_recorded", 0)),
            avg_saves_per_game=percentile_values.get("avg_saves_per_game", 0.0),
            avg_max_saves_per_5sec=percentile_values.get("avg_max_saves_per_5sec", 0.0),
            avg_max_saves_per_20sec=percentile_values.get("avg_max_saves_per_20sec", 0.0),
            peak_max_saves_per_5sec=int(percentile_values.get("peak_max_saves_per_5sec", 0)),
            peak_max_saves_per_20sec=int(percentile_values.get("peak_max_saves_per_20sec", 0)),
            quality_score=percentile_values.get("quality_score", 0.0),
            games_recorded_rank=0,
            sog_given_rank=0,
            sog_per_game_rank=0,
            total_saves_recorded_rank=0,
            avg_saves_per_game_rank=0,
            avg_max_saves_per_5sec_rank=0,
            avg_max_saves_per_20sec_rank=0,
            peak_max_saves_per_5sec_rank=0,
            peak_max_saves_per_20sec_rank=0,
            quality_score_rank=0,
            total_in_rank=total_in_rank,
            first_game_id=None,
            last_game_id=None,
        )
        session.add(scorekeeper_stat)

    session.commit()


def calculate_quality_score(
    avg_max_saves_5sec, avg_max_saves_20sec, peak_max_saves_5sec, peak_max_saves_20sec
):
    """
    Calculate a quality score based on excessive clicking patterns.
    Lower scores are better (less problematic clicking).

    Logic:
    - Penalize high average clicking rates in windows
    - Heavily penalize peak clicking incidents
    - Score ranges from 0 (perfect) to higher values (problematic)
    """
    # Convert to float to handle Decimal types from database
    avg_max_saves_5sec = float(avg_max_saves_5sec or 0.0)
    avg_max_saves_20sec = float(avg_max_saves_20sec or 0.0)
    peak_max_saves_5sec = float(peak_max_saves_5sec or 0)
    peak_max_saves_20sec = float(peak_max_saves_20sec or 0)

    if avg_max_saves_5sec == 0 and avg_max_saves_20sec == 0:
        return 0.0

    # Weight factors (can be tuned based on analysis)
    avg_5sec_weight = 2.0  # Average clicking in 5sec windows
    avg_20sec_weight = 1.0  # Average clicking in 20sec windows
    peak_5sec_weight = 5.0  # Peak 5sec incidents are heavily penalized
    peak_20sec_weight = 3.0  # Peak 20sec incidents are moderately penalized

    score = (
        (avg_max_saves_5sec * avg_5sec_weight)
        + (avg_max_saves_20sec * avg_20sec_weight)
        + (peak_max_saves_5sec * peak_5sec_weight)
        + (peak_max_saves_20sec * peak_20sec_weight)
    )

    return round(score, 2)


def aggregate_scorekeeper_stats(
    session, aggregation_type, aggregation_id, aggregation_window=None
):
    # Only process scorekeeper stats for ALL_ORGS_ID - skip individual organizations
    # This prevents redundant processing when upstream logic calls with all organization IDs
    if aggregation_type == "org" and aggregation_id != ALL_ORGS_ID:
        return  # Do nothing for individual organization IDs

    human_ids_to_filter = get_non_human_ids(session)

    if aggregation_type == "org":
        aggregation_name = "All Orgs"
        filter_condition = sqlalchemy.true()  # No filter for organization
        print(
            f"Aggregating scorekeeper stats for {aggregation_name} with window {aggregation_window}..."
        )
        if aggregation_window == "Daily":
            StatsModel = OrgStatsDailyScorekeeper
        elif aggregation_window == "Weekly":
            StatsModel = OrgStatsWeeklyScorekeeper
        else:
            StatsModel = OrgStatsScorekeeper
        min_games = MIN_GAMES_FOR_ORG_STATS
    else:
        raise ValueError("Invalid aggregation type")

    # Delete existing items from the stats table
    session.query(StatsModel).filter(
        StatsModel.aggregation_id == aggregation_id
    ).delete()
    session.commit()

    # Apply aggregation window filter
    if aggregation_window:
        last_game_datetime_str = (
            session.query(func.max(func.concat(Game.date, " ", Game.time)))
            .filter(filter_condition, Game.status.like("Final%"))
            .scalar()
        )
        start_datetime = get_start_datetime(last_game_datetime_str, aggregation_window)
        if start_datetime:
            game_window_filter = func.cast(
                func.concat(Game.date, " ", Game.time), sqlalchemy.types.TIMESTAMP
            ).between(start_datetime, last_game_datetime_str)
            filter_condition = filter_condition & game_window_filter
        else:
            return

    # Aggregate scorekeeper quality data for each human
    # games_participated: Count FINAL, FINAL_SO, FORFEIT, NOEVENTS
    # games_with_stats: Count only FINAL, FINAL_SO (for per-game averages)
    # Filter by game status upfront for performance
    scorekeeper_quality_stats = (
        session.query(
            ScorekeeperSaveQuality.scorekeeper_id.label("human_id"),
            func.count(ScorekeeperSaveQuality.game_id).label("games_recorded"),
            func.count(ScorekeeperSaveQuality.game_id).label(
                "games_participated"
            ),  # Same as games_recorded after filtering
            func.count(ScorekeeperSaveQuality.game_id).label(
                "games_with_stats"
            ),  # Same as games_recorded after filtering
            func.sum(ScorekeeperSaveQuality.total_saves_recorded).label(
                "total_saves_recorded"
            ),
            func.avg(ScorekeeperSaveQuality.total_saves_recorded).label(
                "avg_saves_per_game"
            ),
            func.avg(ScorekeeperSaveQuality.max_saves_per_5sec).label(
                "avg_max_saves_per_5sec"
            ),
            func.avg(ScorekeeperSaveQuality.max_saves_per_20sec).label(
                "avg_max_saves_per_20sec"
            ),
            func.max(ScorekeeperSaveQuality.max_saves_per_5sec).label(
                "peak_max_saves_per_5sec"
            ),
            func.max(ScorekeeperSaveQuality.max_saves_per_20sec).label(
                "peak_max_saves_per_20sec"
            ),
            func.array_agg(ScorekeeperSaveQuality.game_id).label("game_ids"),
        )
        .join(Game, Game.id == ScorekeeperSaveQuality.game_id)
        .filter(
            Game.status.in_(
                [FINAL_STATUS, FINAL_SO_STATUS, FORFEIT_STATUS, NOEVENTS_STATUS]
            )
        )
    )

    scorekeeper_quality_stats = (
        scorekeeper_quality_stats.filter(filter_condition)
        .group_by(ScorekeeperSaveQuality.scorekeeper_id)
        .all()
    )

    # Combine the results
    stats_dict = {}
    for stat in scorekeeper_quality_stats:
        if stat.human_id in human_ids_to_filter or stat.human_id is None:
            continue
        key = (aggregation_id, stat.human_id)

        # Calculate quality score
        quality_score = calculate_quality_score(
            stat.avg_max_saves_per_5sec or 0.0,
            stat.avg_max_saves_per_20sec or 0.0,
            stat.peak_max_saves_per_5sec or 0,
            stat.peak_max_saves_per_20sec or 0,
        )

        stats_dict[key] = {
            "games_recorded": stat.games_recorded,  # DEPRECATED - for backward compatibility
            "games_participated": stat.games_participated,  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
            "games_with_stats": stat.games_with_stats,  # Games with full stats: FINAL, FINAL_SO only
            "sog_given": stat.total_saves_recorded,  # Legacy field name mapping
            "sog_per_game": stat.avg_saves_per_game or 0.0,  # Legacy field name mapping
            "total_saves_recorded": stat.total_saves_recorded,
            "avg_saves_per_game": stat.avg_saves_per_game or 0.0,
            "avg_max_saves_per_5sec": stat.avg_max_saves_per_5sec or 0.0,
            "avg_max_saves_per_20sec": stat.avg_max_saves_per_20sec or 0.0,
            "peak_max_saves_per_5sec": stat.peak_max_saves_per_5sec or 0,
            "peak_max_saves_per_20sec": stat.peak_max_saves_per_20sec or 0,
            "quality_score": quality_score,
            "game_ids": stat.game_ids,
            "first_game_id": None,
            "last_game_id": None,
        }

    # Filter out entries with games_recorded less than min_games
    stats_dict = {
        key: value
        for key, value in stats_dict.items()
        if value["games_recorded"] >= min_games
    }

    # Populate first_game_id and last_game_id
    for key, stat in stats_dict.items():
        all_game_ids = stat["game_ids"]
        if all_game_ids:
            first_game = (
                session.query(Game)
                .filter(Game.id.in_(all_game_ids))
                .order_by(Game.date, Game.time)
                .first()
            )
            last_game = (
                session.query(Game)
                .filter(Game.id.in_(all_game_ids))
                .order_by(Game.date.desc(), Game.time.desc())
                .first()
            )
            stat["first_game_id"] = first_game.id if first_game else None
            stat["last_game_id"] = last_game.id if last_game else None

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Assign ranks - note: for quality metrics, lower values are better (reverse_rank=True for avg and peak clicking)
    assign_ranks(stats_dict, "games_recorded")
    assign_ranks(stats_dict, "games_participated")  # Rank by total participation
    assign_ranks(stats_dict, "games_with_stats")  # Rank by games with full stats
    assign_ranks(stats_dict, "sog_given")  # Legacy field
    assign_ranks(stats_dict, "sog_per_game")  # Legacy field
    assign_ranks(stats_dict, "total_saves_recorded")
    assign_ranks(stats_dict, "avg_saves_per_game")
    assign_ranks(
        stats_dict, "avg_max_saves_per_5sec", reverse_rank=True
    )  # Lower is better (less clicking)
    assign_ranks(
        stats_dict, "avg_max_saves_per_20sec", reverse_rank=True
    )  # Lower is better
    assign_ranks(
        stats_dict, "peak_max_saves_per_5sec", reverse_rank=True
    )  # Lower is better
    assign_ranks(
        stats_dict, "peak_max_saves_per_20sec", reverse_rank=True
    )  # Lower is better
    assign_ranks(
        stats_dict, "quality_score", reverse_rank=True
    )  # Lower is better (less problematic)

    # Calculate and insert percentile marker records
    insert_percentile_markers_scorekeeper(
        session, stats_dict, aggregation_id, total_in_rank, StatsModel
    )

    # Insert aggregated stats into the appropriate table with progress output
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        scorekeeper_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_recorded=stat[
                "games_recorded"
            ],  # DEPRECATED - for backward compatibility
            games_participated=stat[
                "games_participated"
            ],  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
            games_participated_rank=stat["games_participated_rank"],
            games_with_stats=stat[
                "games_with_stats"
            ],  # Games with full stats: FINAL, FINAL_SO only
            games_with_stats_rank=stat["games_with_stats_rank"],
            sog_given=stat["sog_given"],  # Legacy field mapping
            sog_per_game=stat["sog_per_game"],  # Legacy field mapping
            total_saves_recorded=stat["total_saves_recorded"],
            total_saves_recorded_rank=stat["total_saves_recorded_rank"],
            avg_saves_per_game=stat["avg_saves_per_game"],
            avg_saves_per_game_rank=stat["avg_saves_per_game_rank"],
            avg_max_saves_per_5sec=stat["avg_max_saves_per_5sec"],
            avg_max_saves_per_5sec_rank=stat["avg_max_saves_per_5sec_rank"],
            avg_max_saves_per_20sec=stat["avg_max_saves_per_20sec"],
            avg_max_saves_per_20sec_rank=stat["avg_max_saves_per_20sec_rank"],
            peak_max_saves_per_5sec=stat["peak_max_saves_per_5sec"],
            peak_max_saves_per_5sec_rank=stat["peak_max_saves_per_5sec_rank"],
            peak_max_saves_per_20sec=stat["peak_max_saves_per_20sec"],
            peak_max_saves_per_20sec_rank=stat["peak_max_saves_per_20sec_rank"],
            quality_score=stat["quality_score"],
            quality_score_rank=stat["quality_score_rank"],
            games_recorded_rank=stat["games_recorded_rank"],
            sog_given_rank=stat["sog_given_rank"],  # Legacy field
            sog_per_game_rank=stat["sog_per_game_rank"],  # Legacy field
            total_in_rank=total_in_rank,
            first_game_id=stat["first_game_id"],
            last_game_id=stat["last_game_id"],
        )
        session.add(scorekeeper_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
    session.commit()


def run_aggregate_scorekeeper_stats():
    session = create_session("boss")
    human_id_to_debug = None

    # Get all org_id present in the Organization table (following goalie stats pattern)
    # Individual org calls will be skipped by early exit, only ALL_ORGS_ID will process
    from hockey_blast_common_lib.models import Organization

    org_ids = session.query(Organization.id).all()
    org_ids = [org_id[0] for org_id in org_ids]

    # Add ALL_ORGS_ID to the list so it gets processed
    org_ids.append(ALL_ORGS_ID)

    for org_id in org_ids:
        if human_id_to_debug is None:
            org_name = (
                "All Organizations"
                if org_id == ALL_ORGS_ID
                else session.query(Organization.organization_name)
                .filter(Organization.id == org_id)
                .scalar()
                or f"org_id {org_id}"
            )
            org_progress = create_progress_tracker(
                3, f"Processing scorekeeper stats for {org_name}"
            )
            aggregate_scorekeeper_stats(
                session, aggregation_type="org", aggregation_id=org_id
            )
            org_progress.update(1)
            aggregate_scorekeeper_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Weekly",
            )
            org_progress.update(2)
            aggregate_scorekeeper_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Daily",
            )
            org_progress.update(3)
        else:
            aggregate_scorekeeper_stats(
                session, aggregation_type="org", aggregation_id=org_id
            )
            aggregate_scorekeeper_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Weekly",
            )
            aggregate_scorekeeper_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Daily",
            )


if __name__ == "__main__":
    run_aggregate_scorekeeper_stats()

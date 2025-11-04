import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy.sql import func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import (
    Division,
    Game,
    GoalieSaves,
    Human,
    Organization,
)
from hockey_blast_common_lib.options import (
    MIN_GAMES_FOR_DIVISION_STATS,
    MIN_GAMES_FOR_LEVEL_STATS,
    MIN_GAMES_FOR_ORG_STATS,
)
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    DivisionStatsDailyGoalie,
    DivisionStatsGoalie,
    DivisionStatsWeeklyGoalie,
    LevelStatsGoalie,
    OrgStatsDailyGoalie,
    OrgStatsGoalie,
    OrgStatsWeeklyGoalie,
)
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID
from hockey_blast_common_lib.utils import (
    assign_ranks,
    calculate_percentile_value,
    get_all_division_ids_for_org,
    get_non_human_ids,
    get_percentile_human,
    get_start_datetime,
)

# Import status constants for game filtering
FINAL_STATUS = "Final"
FINAL_SO_STATUS = "Final(SO)"
FORFEIT_STATUS = "FORFEIT"
NOEVENTS_STATUS = "NOEVENTS"


def insert_percentile_markers_goalie(
    session, stats_dict, aggregation_id, total_in_rank, StatsModel
):
    """Insert percentile marker records for goalie stats.

    For each stat field, calculate the 25th, 50th, 75th, 90th, and 95th percentile values
    and insert marker records with fake human IDs.
    """
    if not stats_dict:
        return

    # Define the stat fields we want to calculate percentiles for
    stat_fields = [
        "games_played",
        "games_participated",
        "games_with_stats",
        "goals_allowed",
        "shots_faced",
        "goals_allowed_per_game",
        "save_percentage",
    ]

    percentiles = [25, 50, 75, 90, 95]

    for percentile in percentiles:
        percentile_human_id = get_percentile_human(session, "Goalie", percentile)

        percentile_values = {}
        for field in stat_fields:
            values = [stat[field] for stat in stats_dict.values() if field in stat]
            if values:
                percentile_values[field] = calculate_percentile_value(values, percentile)
            else:
                percentile_values[field] = 0

        goalie_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=percentile_human_id,
            games_played=int(percentile_values.get("games_played", 0)),
            games_participated=int(percentile_values.get("games_participated", 0)),
            games_participated_rank=0,
            games_with_stats=int(percentile_values.get("games_with_stats", 0)),
            games_with_stats_rank=0,
            goals_allowed=int(percentile_values.get("goals_allowed", 0)),
            shots_faced=int(percentile_values.get("shots_faced", 0)),
            goals_allowed_per_game=percentile_values.get("goals_allowed_per_game", 0.0),
            save_percentage=percentile_values.get("save_percentage", 0.0),
            games_played_rank=0,
            goals_allowed_rank=0,
            shots_faced_rank=0,
            goals_allowed_per_game_rank=0,
            save_percentage_rank=0,
            total_in_rank=total_in_rank,
            first_game_id=None,
            last_game_id=None,
        )
        session.add(goalie_stat)

    session.commit()


def aggregate_goalie_stats(
    session,
    aggregation_type,
    aggregation_id,
    debug_human_id=None,
    aggregation_window=None,
):
    human_ids_to_filter = get_non_human_ids(session)

    # Get the name of the aggregation, for debug purposes
    if aggregation_type == "org":
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = (
                session.query(Organization)
                .filter(Organization.id == aggregation_id)
                .first()
                .organization_name
            )
            filter_condition = Game.org_id == aggregation_id
        print(
            f"Aggregating goalie stats for {aggregation_name} with window {aggregation_window}..."
        )
        if aggregation_window == "Daily":
            StatsModel = OrgStatsDailyGoalie
        elif aggregation_window == "Weekly":
            StatsModel = OrgStatsWeeklyGoalie
        else:
            StatsModel = OrgStatsGoalie
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == "division":
        if aggregation_window == "Daily":
            StatsModel = DivisionStatsDailyGoalie
        elif aggregation_window == "Weekly":
            StatsModel = DivisionStatsWeeklyGoalie
        else:
            StatsModel = DivisionStatsGoalie
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == "level":
        StatsModel = LevelStatsGoalie
        min_games = MIN_GAMES_FOR_LEVEL_STATS
        filter_condition = Division.level_id == aggregation_id
        # Add filter to only include games for the last 5 years
        five_years_ago = datetime.now() - timedelta(days=5 * 365)
        level_window_filter = (
            func.cast(
                func.concat(Game.date, " ", Game.time), sqlalchemy.types.TIMESTAMP
            )
            >= five_years_ago
        )
        filter_condition = filter_condition & level_window_filter
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
            # print(f"Warning: No valid start datetime for aggregation window '{aggregation_window}' for {aggregation_name}. No games will be included.")
            return

    # Aggregate games played, goals allowed, and shots faced for each goalie using GoalieSaves table
    # Filter games by status upfront for performance (avoid CASE statements)
    # Only count games with these statuses: FINAL, FINAL_SO, FORFEIT, NOEVENTS
    query = (
        session.query(
            GoalieSaves.goalie_id.label("human_id"),
            func.count(GoalieSaves.game_id).label("games_played"),
            func.count(GoalieSaves.game_id).label(
                "games_participated"
            ),  # Same as games_played after filtering
            func.count(GoalieSaves.game_id).label(
                "games_with_stats"
            ),  # Same as games_played after filtering
            func.sum(GoalieSaves.goals_allowed).label("goals_allowed"),
            func.sum(GoalieSaves.shots_against).label("shots_faced"),
            func.array_agg(GoalieSaves.game_id).label("game_ids"),
        )
        .join(Game, GoalieSaves.game_id == Game.id)
        .filter(
            Game.status.in_(
                [FINAL_STATUS, FINAL_SO_STATUS, FORFEIT_STATUS, NOEVENTS_STATUS]
            )
        )
        .join(Division, Game.division_id == Division.id)
        .filter(filter_condition)
    )

    # Filter for specific human_id if provided
    if debug_human_id:
        query = query.filter(GoalieSaves.goalie_id == debug_human_id)

    goalie_stats = query.group_by(GoalieSaves.goalie_id).all()

    # Combine the results
    stats_dict = {}
    for stat in goalie_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                "games_played": 0,  # DEPRECATED - for backward compatibility
                "games_participated": 0,  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
                "games_with_stats": 0,  # Games with full stats: FINAL, FINAL_SO only
                "goals_allowed": 0,
                "shots_faced": 0,
                "goals_allowed_per_game": 0.0,
                "save_percentage": 0.0,
                "game_ids": [],
                "first_game_id": None,
                "last_game_id": None,
            }
        stats_dict[key]["games_played"] += stat.games_played
        stats_dict[key]["games_participated"] += stat.games_participated
        stats_dict[key]["games_with_stats"] += stat.games_with_stats
        stats_dict[key]["goals_allowed"] += (
            stat.goals_allowed if stat.goals_allowed is not None else 0
        )
        stats_dict[key]["shots_faced"] += (
            stat.shots_faced if stat.shots_faced is not None else 0
        )
        stats_dict[key]["game_ids"].extend(stat.game_ids)

    # Filter out entries with games_played less than min_games
    stats_dict = {
        key: value
        for key, value in stats_dict.items()
        if value["games_played"] >= min_games
    }

    # Calculate per game stats (using games_with_stats as denominator for accuracy)
    for key, stat in stats_dict.items():
        if stat["games_with_stats"] > 0:
            stat["goals_allowed_per_game"] = (
                stat["goals_allowed"] / stat["games_with_stats"]
            )
            stat["save_percentage"] = (
                (stat["shots_faced"] - stat["goals_allowed"]) / stat["shots_faced"]
                if stat["shots_faced"] > 0
                else 0.0
            )

    # Ensure all keys have valid human_id values
    stats_dict = {key: value for key, value in stats_dict.items() if key[1] is not None}

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

    # Assign ranks within each level
    assign_ranks(stats_dict, "games_played")
    assign_ranks(stats_dict, "games_participated")  # Rank by total participation
    assign_ranks(stats_dict, "games_with_stats")  # Rank by games with full stats
    assign_ranks(stats_dict, "goals_allowed", reverse_rank=True)
    assign_ranks(stats_dict, "shots_faced")
    assign_ranks(stats_dict, "goals_allowed_per_game", reverse_rank=True)
    assign_ranks(stats_dict, "save_percentage")

    # Calculate and insert percentile marker records
    insert_percentile_markers_goalie(
        session, stats_dict, aggregation_id, total_in_rank, StatsModel
    )

    # Debug output for specific human
    if debug_human_id:
        if any(key[1] == debug_human_id for key in stats_dict):
            human = session.query(Human).filter(Human.id == debug_human_id).first()
            human_name = f"{human.first_name} {human.last_name}" if human else "Unknown"
            print(
                f"For Human {debug_human_id} ({human_name}) for {aggregation_type} {aggregation_id} ({aggregation_name}) , total_in_rank {total_in_rank} and window {aggregation_window}:"
            )
            for key, stat in stats_dict.items():
                if key[1] == debug_human_id:
                    for k, v in stat.items():
                        print(f"{k}: {v}")

    # Insert aggregated stats into the appropriate table with progress output
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        goals_allowed_per_game = (
            stat["goals_allowed"] / stat["games_played"]
            if stat["games_played"] > 0
            else 0.0
        )
        save_percentage = (
            (stat["shots_faced"] - stat["goals_allowed"]) / stat["shots_faced"]
            if stat["shots_faced"] > 0
            else 0.0
        )
        goalie_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_played=stat[
                "games_played"
            ],  # DEPRECATED - for backward compatibility
            games_participated=stat[
                "games_participated"
            ],  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
            games_participated_rank=stat["games_participated_rank"],
            games_with_stats=stat[
                "games_with_stats"
            ],  # Games with full stats: FINAL, FINAL_SO only
            games_with_stats_rank=stat["games_with_stats_rank"],
            goals_allowed=stat["goals_allowed"],
            shots_faced=stat["shots_faced"],
            goals_allowed_per_game=goals_allowed_per_game,
            save_percentage=save_percentage,
            games_played_rank=stat["games_played_rank"],
            goals_allowed_rank=stat["goals_allowed_rank"],
            shots_faced_rank=stat["shots_faced_rank"],
            goals_allowed_per_game_rank=stat["goals_allowed_per_game_rank"],
            save_percentage_rank=stat["save_percentage_rank"],
            total_in_rank=total_in_rank,
            first_game_id=stat["first_game_id"],
            last_game_id=stat["last_game_id"],
        )
        session.add(goalie_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
    session.commit()


def run_aggregate_goalie_stats():
    session = create_session("boss")
    human_id_to_debug = None

    # Get all org_id present in the Organization table
    org_ids = session.query(Organization.id).all()
    org_ids = [org_id[0] for org_id in org_ids]

    for org_id in org_ids:
        division_ids = get_all_division_ids_for_org(session, org_id)
        org_name = (
            session.query(Organization.organization_name)
            .filter(Organization.id == org_id)
            .scalar()
            or f"org_id {org_id}"
        )

        if human_id_to_debug is None and division_ids:
            # Process divisions with progress tracking
            progress = create_progress_tracker(
                len(division_ids),
                f"Processing {len(division_ids)} divisions for {org_name}",
            )
            for i, division_id in enumerate(division_ids):
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                )
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Weekly",
                )
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Daily",
                )
                progress.update(i + 1)
        else:
            # Debug mode or no divisions - process without progress tracking
            for division_id in division_ids:
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                )
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Weekly",
                )
                aggregate_goalie_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Daily",
                )

        # Process org-level stats with progress tracking
        if human_id_to_debug is None:
            org_progress = create_progress_tracker(
                3, f"Processing org-level stats for {org_name}"
            )
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
            )
            org_progress.update(1)
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Weekly",
            )
            org_progress.update(2)
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Daily",
            )
            org_progress.update(3)
        else:
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
            )
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Weekly",
            )
            aggregate_goalie_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Daily",
            )

    # Aggregate by level
    level_ids = session.query(Division.level_id).distinct().all()
    level_ids = [level_id[0] for level_id in level_ids if level_id[0] is not None]

    if human_id_to_debug is None and level_ids:
        # Process levels with progress tracking
        level_progress = create_progress_tracker(
            len(level_ids), f"Processing {len(level_ids)} skill levels"
        )
        for i, level_id in enumerate(level_ids):
            aggregate_goalie_stats(
                session,
                aggregation_type="level",
                aggregation_id=level_id,
                debug_human_id=human_id_to_debug,
            )
            level_progress.update(i + 1)
    else:
        # Debug mode or no levels - process without progress tracking
        for level_id in level_ids:
            aggregate_goalie_stats(
                session,
                aggregation_type="level",
                aggregation_id=level_id,
                debug_human_id=human_id_to_debug,
            )


if __name__ == "__main__":
    run_aggregate_goalie_stats()

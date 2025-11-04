import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



import sqlalchemy
from sqlalchemy.sql import case, func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Game, Organization, Penalty
from hockey_blast_common_lib.options import (
    MIN_GAMES_FOR_DIVISION_STATS,
    MIN_GAMES_FOR_LEVEL_STATS,
    MIN_GAMES_FOR_ORG_STATS,
)
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    DivisionStatsDailyReferee,
    DivisionStatsReferee,
    DivisionStatsWeeklyReferee,
    LevelStatsReferee,
    OrgStatsDailyReferee,
    OrgStatsReferee,
    OrgStatsWeeklyReferee,
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


def insert_percentile_markers_referee(
    session, stats_dict, aggregation_id, total_in_rank, StatsModel
):
    """Insert percentile marker records for referee stats."""
    if not stats_dict:
        return

    stat_fields = [
        "games_reffed",
        "games_participated",
        "games_with_stats",
        "penalties_given",
        "penalties_per_game",
        "gm_given",
        "gm_per_game",
    ]

    percentiles = [25, 50, 75, 90, 95]

    for percentile in percentiles:
        percentile_human_id = get_percentile_human(session, "Ref", percentile)

        percentile_values = {}
        for field in stat_fields:
            values = [stat[field] for stat in stats_dict.values() if field in stat]
            if values:
                percentile_values[field] = calculate_percentile_value(values, percentile)
            else:
                percentile_values[field] = 0

        referee_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=percentile_human_id,
            games_reffed=int(percentile_values.get("games_reffed", 0)),
            games_participated=int(percentile_values.get("games_participated", 0)),
            games_participated_rank=0,
            games_with_stats=int(percentile_values.get("games_with_stats", 0)),
            games_with_stats_rank=0,
            penalties_given=int(percentile_values.get("penalties_given", 0)),
            penalties_per_game=percentile_values.get("penalties_per_game", 0.0),
            gm_given=int(percentile_values.get("gm_given", 0)),
            gm_per_game=percentile_values.get("gm_per_game", 0.0),
            games_reffed_rank=0,
            penalties_given_rank=0,
            penalties_per_game_rank=0,
            gm_given_rank=0,
            gm_per_game_rank=0,
            total_in_rank=total_in_rank,
            first_game_id=None,
            last_game_id=None,
        )
        session.add(referee_stat)

    session.commit()


def aggregate_referee_stats(
    session, aggregation_type, aggregation_id, aggregation_window=None
):
    human_ids_to_filter = get_non_human_ids(session)

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
            f"Aggregating referee stats for {aggregation_name} with window {aggregation_window}..."
        )
        if aggregation_window == "Daily":
            StatsModel = OrgStatsDailyReferee
        elif aggregation_window == "Weekly":
            StatsModel = OrgStatsWeeklyReferee
        else:
            StatsModel = OrgStatsReferee
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == "division":
        if aggregation_window == "Daily":
            StatsModel = DivisionStatsDailyReferee
        elif aggregation_window == "Weekly":
            StatsModel = DivisionStatsWeeklyReferee
        else:
            StatsModel = DivisionStatsReferee
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == "level":
        StatsModel = LevelStatsReferee
        min_games = MIN_GAMES_FOR_LEVEL_STATS
        filter_condition = Division.level_id == aggregation_id
        # Add filter to only include games for the last 5 years
        # five_years_ago = datetime.now() - timedelta(days=5*365)
        # level_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP) >= five_years_ago
        # filter_condition = filter_condition & level_window_filter
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

    filter_condition = filter_condition & (Division.id == Game.division_id)
    # Aggregate games reffed for each referee
    # games_participated: Count FINAL, FINAL_SO, FORFEIT, NOEVENTS
    # games_with_stats: Count only FINAL, FINAL_SO (for per-game averages)
    # Filter by game status upfront for performance
    status_filter = Game.status.in_(
        [FINAL_STATUS, FINAL_SO_STATUS, FORFEIT_STATUS, NOEVENTS_STATUS]
    )

    games_reffed_stats = (
        session.query(
            Game.referee_1_id.label("human_id"),
            func.count(Game.id).label("games_reffed"),
            func.count(Game.id).label(
                "games_participated"
            ),  # Same as games_reffed after filtering
            func.count(Game.id).label(
                "games_with_stats"
            ),  # Same as games_reffed after filtering
            func.array_agg(Game.id).label("game_ids"),
        )
        .filter(filter_condition, status_filter)
        .group_by(Game.referee_1_id)
        .all()
    )

    games_reffed_stats_2 = (
        session.query(
            Game.referee_2_id.label("human_id"),
            func.count(Game.id).label("games_reffed"),
            func.count(Game.id).label(
                "games_participated"
            ),  # Same as games_reffed after filtering
            func.count(Game.id).label(
                "games_with_stats"
            ),  # Same as games_reffed after filtering
            func.array_agg(Game.id).label("game_ids"),
        )
        .filter(filter_condition, status_filter)
        .group_by(Game.referee_2_id)
        .all()
    )

    # Aggregate penalties given for each referee
    penalties_given_stats = (
        session.query(
            Game.id.label("game_id"),
            Game.referee_1_id,
            Game.referee_2_id,
            func.count(Penalty.id).label("penalties_given"),
            func.sum(
                case((func.lower(Penalty.penalty_minutes) == "gm", 1), else_=0)
            ).label("gm_given"),
        )
        .join(Game, Game.id == Penalty.game_id)
        .filter(filter_condition)
        .group_by(Game.id, Game.referee_1_id, Game.referee_2_id)
        .all()
    )

    # Combine the results
    stats_dict = {}
    for stat in games_reffed_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                "games_reffed": 0,  # DEPRECATED - for backward compatibility
                "games_participated": 0,  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
                "games_with_stats": 0,  # Games with full stats: FINAL, FINAL_SO only
                "penalties_given": 0,
                "gm_given": 0,
                "penalties_per_game": 0.0,
                "gm_per_game": 0.0,
                "game_ids": [],
                "first_game_id": None,
                "last_game_id": None,
            }
        stats_dict[key]["games_reffed"] += stat.games_reffed
        stats_dict[key]["games_participated"] += stat.games_participated
        stats_dict[key]["games_with_stats"] += stat.games_with_stats
        stats_dict[key]["game_ids"].extend(stat.game_ids)

    for stat in games_reffed_stats_2:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                "games_reffed": 0,  # DEPRECATED - for backward compatibility
                "games_participated": 0,  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
                "games_with_stats": 0,  # Games with full stats: FINAL, FINAL_SO only
                "penalties_given": 0,
                "gm_given": 0,
                "penalties_per_game": 0.0,
                "gm_per_game": 0.0,
                "game_ids": [],
                "first_game_id": None,
                "last_game_id": None,
            }
        stats_dict[key]["games_reffed"] += stat.games_reffed
        stats_dict[key]["games_participated"] += stat.games_participated
        stats_dict[key]["games_with_stats"] += stat.games_with_stats
        stats_dict[key]["game_ids"].extend(stat.game_ids)

    # Filter out entries with games_reffed less than min_games
    stats_dict = {
        key: value
        for key, value in stats_dict.items()
        if value["games_reffed"] >= min_games
    }

    for stat in penalties_given_stats:
        if stat.referee_1_id and stat.referee_1_id not in human_ids_to_filter:
            key = (aggregation_id, stat.referee_1_id)
            if key in stats_dict:
                stats_dict[key]["penalties_given"] += stat.penalties_given / 2
                stats_dict[key]["gm_given"] += stat.gm_given / 2
                stats_dict[key]["game_ids"].append(stat.game_id)

        if stat.referee_2_id and stat.referee_2_id not in human_ids_to_filter:
            key = (aggregation_id, stat.referee_2_id)
            if key in stats_dict:
                stats_dict[key]["penalties_given"] += stat.penalties_given / 2
                stats_dict[key]["gm_given"] += stat.gm_given / 2
                stats_dict[key]["game_ids"].append(stat.game_id)

    # Calculate per game stats (using games_with_stats as denominator for accuracy)
    for key, stat in stats_dict.items():
        if stat["games_with_stats"] > 0:
            stat["penalties_per_game"] = (
                stat["penalties_given"] / stat["games_with_stats"]
            )
            stat["gm_per_game"] = stat["gm_given"] / stat["games_with_stats"]

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

    # Assign ranks
    assign_ranks(stats_dict, "games_reffed")
    assign_ranks(stats_dict, "games_participated")  # Rank by total participation
    assign_ranks(stats_dict, "games_with_stats")  # Rank by games with full stats
    assign_ranks(stats_dict, "penalties_given")
    assign_ranks(stats_dict, "penalties_per_game")
    assign_ranks(stats_dict, "gm_given")
    assign_ranks(stats_dict, "gm_per_game")

    # Calculate and insert percentile marker records
    insert_percentile_markers_referee(
        session, stats_dict, aggregation_id, total_in_rank, StatsModel
    )

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        referee_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_reffed=stat[
                "games_reffed"
            ],  # DEPRECATED - for backward compatibility
            games_participated=stat[
                "games_participated"
            ],  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
            games_participated_rank=stat["games_participated_rank"],
            games_with_stats=stat[
                "games_with_stats"
            ],  # Games with full stats: FINAL, FINAL_SO only
            games_with_stats_rank=stat["games_with_stats_rank"],
            penalties_given=stat["penalties_given"],
            penalties_per_game=stat["penalties_per_game"],
            gm_given=stat["gm_given"],
            gm_per_game=stat["gm_per_game"],
            games_reffed_rank=stat["games_reffed_rank"],
            penalties_given_rank=stat["penalties_given_rank"],
            penalties_per_game_rank=stat["penalties_per_game_rank"],
            gm_given_rank=stat["gm_given_rank"],
            gm_per_game_rank=stat["gm_per_game_rank"],
            total_in_rank=total_in_rank,
            first_game_id=stat["first_game_id"],
            last_game_id=stat["last_game_id"],
        )
        session.add(referee_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
    session.commit()


def run_aggregate_referee_stats():
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
                aggregate_referee_stats(
                    session, aggregation_type="division", aggregation_id=division_id
                )
                aggregate_referee_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    aggregation_window="Weekly",
                )
                aggregate_referee_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    aggregation_window="Daily",
                )
                progress.update(i + 1)
        else:
            # Debug mode or no divisions - process without progress tracking
            for division_id in division_ids:
                aggregate_referee_stats(
                    session, aggregation_type="division", aggregation_id=division_id
                )
                aggregate_referee_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    aggregation_window="Weekly",
                )
                aggregate_referee_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    aggregation_window="Daily",
                )

        # Process org-level stats with progress tracking
        if human_id_to_debug is None:
            org_progress = create_progress_tracker(
                3, f"Processing org-level stats for {org_name}"
            )
            aggregate_referee_stats(
                session, aggregation_type="org", aggregation_id=org_id
            )
            org_progress.update(1)
            aggregate_referee_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Weekly",
            )
            org_progress.update(2)
            aggregate_referee_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Daily",
            )
            org_progress.update(3)
        else:
            aggregate_referee_stats(
                session, aggregation_type="org", aggregation_id=org_id
            )
            aggregate_referee_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                aggregation_window="Weekly",
            )
            aggregate_referee_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
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
            aggregate_referee_stats(
                session, aggregation_type="level", aggregation_id=level_id
            )
            level_progress.update(i + 1)
    else:
        # Debug mode or no levels - process without progress tracking
        for level_id in level_ids:
            aggregate_referee_stats(
                session, aggregation_type="level", aggregation_id=level_id
            )


if __name__ == "__main__":
    run_aggregate_referee_stats()

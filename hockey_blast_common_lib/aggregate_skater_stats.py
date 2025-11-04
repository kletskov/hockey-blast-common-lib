import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import sqlalchemy
from sqlalchemy import and_, case, func
from sqlalchemy.sql import case, func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import (
    Division,
    Game,
    GameRoster,
    Goal,
    Human,
    Level,
    Organization,
    Penalty,
)
from hockey_blast_common_lib.options import (
    MIN_GAMES_FOR_DIVISION_STATS,
    MIN_GAMES_FOR_LEVEL_STATS,
    MIN_GAMES_FOR_ORG_STATS,
)
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    DivisionStatsDailySkater,
    DivisionStatsSkater,
    DivisionStatsWeeklySkater,
    LevelStatsSkater,
    OrgStatsDailySkater,
    OrgStatsSkater,
    OrgStatsWeeklySkater,
)
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID
from hockey_blast_common_lib.utils import (
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


def calculate_current_point_streak(session, human_id, filter_condition):
    """
    Calculate the current point streak for a player.
    A point streak is consecutive games (from the most recent game backward) where the player had at least one point.
    Returns a tuple: (streak_length, average_points_during_streak)

    Optimized to use CASE statements for conditional aggregation in a single query.
    """
    # Get all games with their point totals in ONE query using CASE for conditional counting
    game_points = (
        session.query(
            Game.id,
            Game.date,
            Game.time,
            func.sum(case((Goal.goal_scorer_id == human_id, 1), else_=0)).label(
                "goals"
            ),
            func.sum(
                case(
                    (
                        (Goal.assist_1_id == human_id) | (Goal.assist_2_id == human_id),
                        1,
                    ),
                    else_=0,
                )
            ).label("assists"),
        )
        .join(GameRoster, Game.id == GameRoster.game_id)
        .outerjoin(Goal, Game.id == Goal.game_id)
        .filter(
            GameRoster.human_id == human_id,
            ~GameRoster.role.ilike("g"),  # Exclude goalie games
            filter_condition,
            (Game.status.like("Final%"))
            | (Game.status == "NOEVENTS"),  # Include Final and NOEVENTS games
        )
        .group_by(Game.id, Game.date, Game.time)
        .order_by(Game.date.desc(), Game.time.desc())
        .all()
    )

    if not game_points:
        return 0, 0.0

    current_streak = 0
    total_points_in_streak = 0

    # Iterate through games from most recent to oldest
    for game in game_points:
        total_points = (game.goals or 0) + (game.assists or 0)

        if total_points > 0:
            current_streak += 1
            total_points_in_streak += total_points
        else:
            # Streak is broken, stop counting
            break

    # Calculate average points during streak
    avg_points_during_streak = (
        total_points_in_streak / current_streak if current_streak > 0 else 0.0
    )

    return current_streak, avg_points_during_streak


def insert_percentile_markers_skater(
    session, stats_dict, aggregation_id, total_in_rank, StatsModel, aggregation_window
):
    """Insert percentile marker records for skater stats.

    For each stat field, calculate the 25th, 50th, 75th, 90th, and 95th percentile values
    and insert marker records with fake human IDs.
    """
    if not stats_dict:
        return

    # Define the stat fields we want to calculate percentiles for
    # Each field has percentile calculated SEPARATELY
    stat_fields = [
        "games_played",
        "games_participated",
        "games_with_stats",
        "goals",
        "assists",
        "points",
        "penalties",
        "gm_penalties",
        "goals_per_game",
        "assists_per_game",
        "points_per_game",
        "penalties_per_game",
        "gm_penalties_per_game",
    ]

    # Add streak fields only for all-time stats
    if aggregation_window is None:
        stat_fields.extend(
            ["current_point_streak", "current_point_streak_avg_points"]
        )

    # For each percentile (25, 50, 75, 90, 95)
    percentiles = [25, 50, 75, 90, 95]

    for percentile in percentiles:
        # Get or create the percentile marker human
        percentile_human_id = get_percentile_human(session, "Skater", percentile)

        # Calculate percentile values for each stat field SEPARATELY
        percentile_values = {}
        for field in stat_fields:
            # Extract all values for this field
            values = [stat[field] for stat in stats_dict.values() if field in stat]
            if values:
                percentile_values[field] = calculate_percentile_value(values, percentile)
            else:
                percentile_values[field] = 0

        # Create the stats record for this percentile marker
        skater_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=percentile_human_id,
            games_played=int(percentile_values.get("games_played", 0)),
            games_participated=int(percentile_values.get("games_participated", 0)),
            games_participated_rank=0,  # Percentile markers don't have ranks
            games_with_stats=int(percentile_values.get("games_with_stats", 0)),
            games_with_stats_rank=0,
            goals=int(percentile_values.get("goals", 0)),
            assists=int(percentile_values.get("assists", 0)),
            points=int(percentile_values.get("points", 0)),
            penalties=int(percentile_values.get("penalties", 0)),
            gm_penalties=int(percentile_values.get("gm_penalties", 0)),
            goals_per_game=percentile_values.get("goals_per_game", 0.0),
            points_per_game=percentile_values.get("points_per_game", 0.0),
            assists_per_game=percentile_values.get("assists_per_game", 0.0),
            penalties_per_game=percentile_values.get("penalties_per_game", 0.0),
            gm_penalties_per_game=percentile_values.get("gm_penalties_per_game", 0.0),
            games_played_rank=0,
            goals_rank=0,
            assists_rank=0,
            points_rank=0,
            penalties_rank=0,
            gm_penalties_rank=0,
            goals_per_game_rank=0,
            points_per_game_rank=0,
            assists_per_game_rank=0,
            penalties_per_game_rank=0,
            gm_penalties_per_game_rank=0,
            total_in_rank=total_in_rank,
            current_point_streak=int(
                percentile_values.get("current_point_streak", 0)
            ),
            current_point_streak_rank=0,
            current_point_streak_avg_points=percentile_values.get(
                "current_point_streak_avg_points", 0.0
            ),
            current_point_streak_avg_points_rank=0,
            first_game_id=None,  # Percentile markers don't have game references
            last_game_id=None,
        )
        session.add(skater_stat)

    session.commit()


def aggregate_skater_stats(
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
            f"Aggregating skater stats for {aggregation_name} with window {aggregation_window}..."
        )

    elif aggregation_type == "division":
        aggregation_name = (
            session.query(Division).filter(Division.id == aggregation_id).first().level
        )
    elif aggregation_type == "level":
        aggregation_name = (
            session.query(Level).filter(Level.id == aggregation_id).first().level_name
        )
    else:
        aggregation_name = "Unknown"

    if aggregation_type == "org":
        if aggregation_window == "Daily":
            StatsModel = OrgStatsDailySkater
        elif aggregation_window == "Weekly":
            StatsModel = OrgStatsWeeklySkater
        else:
            StatsModel = OrgStatsSkater
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == "division":
        if aggregation_window == "Daily":
            StatsModel = DivisionStatsDailySkater
        elif aggregation_window == "Weekly":
            StatsModel = DivisionStatsWeeklySkater
        else:
            StatsModel = DivisionStatsSkater
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == "level":
        StatsModel = LevelStatsSkater
        min_games = MIN_GAMES_FOR_LEVEL_STATS
        # Get division IDs for this level to avoid cartesian product
        division_ids = (
            session.query(Division.id).filter(Division.level_id == aggregation_id).all()
        )
        division_ids = [div_id[0] for div_id in division_ids]
        if not division_ids:
            return  # No divisions for this level
        filter_condition = Game.division_id.in_(division_ids)
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
            .filter(
                filter_condition,
                (Game.status.like("Final%")) | (Game.status == "NOEVENTS"),
            )
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

    # Filter for specific human_id if provided
    human_filter = []
    # if debug_human_id:
    #     human_filter = [GameRoster.human_id == debug_human_id]

    # Aggregate games played for each human in each division, excluding goalies
    # Filter games by status upfront for performance (avoid CASE statements on 200K+ rows)
    # Only count games with these statuses: FINAL, FINAL_SO, FORFEIT, NOEVENTS
    games_played_query = (
        session.query(
            GameRoster.human_id,
            func.count(Game.id).label("games_played"),
            func.count(Game.id).label(
                "games_participated"
            ),  # Same as games_played after filtering
            func.count(Game.id).label(
                "games_with_stats"
            ),  # Same as games_played after filtering
            func.array_agg(Game.id).label("game_ids"),
        )
        .join(Game, Game.id == GameRoster.game_id)
        .filter(
            Game.status.in_(
                [FINAL_STATUS, FINAL_SO_STATUS, FORFEIT_STATUS, NOEVENTS_STATUS]
            )
        )
    )

    # Only join Division if not level aggregation (since we filter on Game.division_id directly for levels)
    if aggregation_type != "level":
        games_played_query = games_played_query.join(
            Division, Game.division_id == Division.id
        )

    games_played_stats = (
        games_played_query.filter(
            filter_condition, ~GameRoster.role.ilike("g"), *human_filter
        )
        .group_by(GameRoster.human_id)
        .all()
    )

    # Aggregate goals for each human in each division, excluding goalies
    goals_query = (
        session.query(
            Goal.goal_scorer_id.label("human_id"),
            func.count(Goal.id).label("goals"),
            func.array_agg(Goal.game_id).label("goal_game_ids"),
        )
        .join(Game, Game.id == Goal.game_id)
        .join(
            GameRoster,
            and_(
                Game.id == GameRoster.game_id,
                Goal.goal_scorer_id == GameRoster.human_id,
            ),
        )
    )

    if aggregation_type != "level":
        goals_query = goals_query.join(Division, Game.division_id == Division.id)

    goals_stats = (
        goals_query.filter(filter_condition, ~GameRoster.role.ilike("g"), *human_filter)
        .group_by(Goal.goal_scorer_id)
        .all()
    )

    # Aggregate assists for each human in each division, excluding goalies
    assists_query = (
        session.query(
            Goal.assist_1_id.label("human_id"),
            func.count(Goal.id).label("assists"),
            func.array_agg(Goal.game_id).label("assist_game_ids"),
        )
        .join(Game, Game.id == Goal.game_id)
        .join(
            GameRoster,
            and_(
                Game.id == GameRoster.game_id, Goal.assist_1_id == GameRoster.human_id
            ),
        )
    )

    if aggregation_type != "level":
        assists_query = assists_query.join(Division, Game.division_id == Division.id)

    assists_stats = (
        assists_query.filter(
            filter_condition, ~GameRoster.role.ilike("g"), *human_filter
        )
        .group_by(Goal.assist_1_id)
        .all()
    )

    assists_query_2 = (
        session.query(
            Goal.assist_2_id.label("human_id"),
            func.count(Goal.id).label("assists"),
            func.array_agg(Goal.game_id).label("assist_2_game_ids"),
        )
        .join(Game, Game.id == Goal.game_id)
        .join(
            GameRoster,
            and_(
                Game.id == GameRoster.game_id, Goal.assist_2_id == GameRoster.human_id
            ),
        )
    )

    if aggregation_type != "level":
        assists_query_2 = assists_query_2.join(
            Division, Game.division_id == Division.id
        )

    assists_stats_2 = (
        assists_query_2.filter(
            filter_condition, ~GameRoster.role.ilike("g"), *human_filter
        )
        .group_by(Goal.assist_2_id)
        .all()
    )

    # Aggregate penalties for each human in each division, excluding goalies
    penalties_query = (
        session.query(
            Penalty.penalized_player_id.label("human_id"),
            func.count(Penalty.id).label("penalties"),
            func.sum(case((Penalty.penalty_minutes == "GM", 1), else_=0)).label(
                "gm_penalties"
            ),  # New aggregation for GM penalties
            func.array_agg(Penalty.game_id).label("penalty_game_ids"),
        )
        .join(Game, Game.id == Penalty.game_id)
        .join(
            GameRoster,
            and_(
                Game.id == GameRoster.game_id,
                Penalty.penalized_player_id == GameRoster.human_id,
            ),
        )
    )

    if aggregation_type != "level":
        penalties_query = penalties_query.join(
            Division, Game.division_id == Division.id
        )

    penalties_stats = (
        penalties_query.filter(
            filter_condition, ~GameRoster.role.ilike("g"), *human_filter
        )
        .group_by(Penalty.penalized_player_id)
        .all()
    )

    # Combine the results
    stats_dict = {}
    for stat in games_played_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                "games_played": 0,  # DEPRECATED - for backward compatibility
                "games_participated": 0,  # Total games: FINAL, FINAL_SO, FORFEIT, NOEVENTS
                "games_with_stats": 0,  # Games with full stats: FINAL, FINAL_SO only
                "goals": 0,
                "assists": 0,
                "penalties": 0,
                "gm_penalties": 0,  # Initialize GM penalties
                "points": 0,  # Initialize points
                "goals_per_game": 0.0,
                "points_per_game": 0.0,
                "assists_per_game": 0.0,
                "penalties_per_game": 0.0,
                "gm_penalties_per_game": 0.0,  # Initialize GM penalties per game
                "current_point_streak": 0,  # Initialize current point streak
                "current_point_streak_avg_points": 0.0,  # Initialize current point streak average points
                "game_ids": [],
                "first_game_id": None,
                "last_game_id": None,
            }
        stats_dict[key]["games_played"] += stat.games_played
        stats_dict[key]["games_participated"] += stat.games_participated
        stats_dict[key]["games_with_stats"] += stat.games_with_stats
        stats_dict[key]["game_ids"].extend(stat.game_ids)

    # Filter out entries with games_played less than min_games
    stats_dict = {
        key: value
        for key, value in stats_dict.items()
        if value["games_played"] >= min_games
    }

    for stat in goals_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]["goals"] += stat.goals
            stats_dict[key]["points"] += stat.goals  # Update points

    for stat in assists_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]["assists"] += stat.assists
            stats_dict[key]["points"] += stat.assists  # Update points

    for stat in assists_stats_2:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]["assists"] += stat.assists
            stats_dict[key]["points"] += stat.assists  # Update points

    for stat in penalties_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]["penalties"] += stat.penalties
            stats_dict[key]["gm_penalties"] += stat.gm_penalties  # Update GM penalties

    # Calculate per game stats (using games_with_stats as denominator for accuracy)
    for key, stat in stats_dict.items():
        if stat["games_with_stats"] > 0:
            stat["goals_per_game"] = stat["goals"] / stat["games_with_stats"]
            stat["points_per_game"] = stat["points"] / stat["games_with_stats"]
            stat["assists_per_game"] = stat["assists"] / stat["games_with_stats"]
            stat["penalties_per_game"] = stat["penalties"] / stat["games_with_stats"]
            stat["gm_penalties_per_game"] = (
                stat["gm_penalties"] / stat["games_with_stats"]
            )  # Calculate GM penalties per game

    # Ensure all keys have valid human_id values
    stats_dict = {key: value for key, value in stats_dict.items() if key[1] is not None}

    # Populate first_game_id and last_game_id
    # Only show progress for "All Orgs" with no window (all-time stats) - the slowest case
    total_players = len(stats_dict)
    if (
        aggregation_type == "org"
        and aggregation_id == ALL_ORGS_ID
        and aggregation_window is None
        and total_players > 1000
    ):
        progress = create_progress_tracker(
            total_players, f"Processing {total_players} players for {aggregation_name}"
        )
        for idx, (key, stat) in enumerate(stats_dict.items()):
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
            if (idx + 1) % 100 == 0 or (
                idx + 1
            ) == total_players:  # Update every 100 players
                progress.update(idx + 1)
    else:
        # No progress tracking for all other cases
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

    # Calculate current point streak (only for all-time stats)
    if aggregation_window is None:
        total_players = len(stats_dict)
        # Show progress for All Orgs - this is the slowest part
        if (
            aggregation_type == "org"
            and aggregation_id == ALL_ORGS_ID
            and total_players > 1000
        ):
            progress = create_progress_tracker(
                total_players, f"Calculating point streaks for {total_players} players"
            )
            for idx, (key, stat) in enumerate(stats_dict.items()):
                agg_id, human_id = key
                streak_length, avg_points = calculate_current_point_streak(
                    session, human_id, filter_condition
                )
                stat["current_point_streak"] = streak_length
                stat["current_point_streak_avg_points"] = avg_points
                if (idx + 1) % 100 == 0 or (idx + 1) == total_players:
                    progress.update(idx + 1)
        else:
            for key, stat in stats_dict.items():
                agg_id, human_id = key
                streak_length, avg_points = calculate_current_point_streak(
                    session, human_id, filter_condition
                )
                stat["current_point_streak"] = streak_length
                stat["current_point_streak_avg_points"] = avg_points

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Assign ranks within each level
    def assign_ranks(stats_dict, field):
        sorted_stats = sorted(
            stats_dict.items(), key=lambda x: x[1][field], reverse=True
        )
        for rank, (key, stat) in enumerate(sorted_stats, start=1):
            stats_dict[key][f"{field}_rank"] = rank

    assign_ranks(stats_dict, "games_played")
    assign_ranks(stats_dict, "games_participated")  # Rank by total participation
    assign_ranks(stats_dict, "games_with_stats")  # Rank by games with full stats
    assign_ranks(stats_dict, "goals")
    assign_ranks(stats_dict, "assists")
    assign_ranks(stats_dict, "points")
    assign_ranks(stats_dict, "penalties")
    assign_ranks(stats_dict, "gm_penalties")  # Assign ranks for GM penalties
    assign_ranks(stats_dict, "goals_per_game")
    assign_ranks(stats_dict, "points_per_game")
    assign_ranks(stats_dict, "assists_per_game")
    assign_ranks(stats_dict, "penalties_per_game")
    assign_ranks(
        stats_dict, "gm_penalties_per_game"
    )  # Assign ranks for GM penalties per game
    if (
        aggregation_window is None
    ):  # Only assign current_point_streak ranks for all-time stats
        assign_ranks(stats_dict, "current_point_streak")
        assign_ranks(stats_dict, "current_point_streak_avg_points")

    # Calculate and insert percentile marker records
    insert_percentile_markers_skater(
        session, stats_dict, aggregation_id, total_in_rank, StatsModel, aggregation_window
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
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        goals_per_game = (
            stat["goals"] / stat["games_played"] if stat["games_played"] > 0 else 0.0
        )
        points_per_game = (
            (stat["goals"] + stat["assists"]) / stat["games_played"]
            if stat["games_played"] > 0
            else 0.0
        )
        assists_per_game = (
            stat["assists"] / stat["games_played"] if stat["games_played"] > 0 else 0.0
        )
        penalties_per_game = (
            stat["penalties"] / stat["games_played"]
            if stat["games_played"] > 0
            else 0.0
        )
        gm_penalties_per_game = (
            stat["gm_penalties"] / stat["games_played"]
            if stat["games_played"] > 0
            else 0.0
        )  # Calculate GM penalties per game
        skater_stat = StatsModel(
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
            goals=stat["goals"],
            assists=stat["assists"],
            points=stat["goals"] + stat["assists"],
            penalties=stat["penalties"],
            gm_penalties=stat["gm_penalties"],  # Include GM penalties
            goals_per_game=goals_per_game,
            points_per_game=points_per_game,
            assists_per_game=assists_per_game,
            penalties_per_game=penalties_per_game,
            gm_penalties_per_game=gm_penalties_per_game,  # Include GM penalties per game
            games_played_rank=stat["games_played_rank"],
            goals_rank=stat["goals_rank"],
            assists_rank=stat["assists_rank"],
            points_rank=stat["points_rank"],
            penalties_rank=stat["penalties_rank"],
            gm_penalties_rank=stat["gm_penalties_rank"],  # Include GM penalties rank
            goals_per_game_rank=stat["goals_per_game_rank"],
            points_per_game_rank=stat["points_per_game_rank"],
            assists_per_game_rank=stat["assists_per_game_rank"],
            penalties_per_game_rank=stat["penalties_per_game_rank"],
            gm_penalties_per_game_rank=stat[
                "gm_penalties_per_game_rank"
            ],  # Include GM penalties per game rank
            total_in_rank=total_in_rank,
            current_point_streak=stat.get("current_point_streak", 0),
            current_point_streak_rank=stat.get("current_point_streak_rank", 0),
            current_point_streak_avg_points=stat.get(
                "current_point_streak_avg_points", 0.0
            ),
            current_point_streak_avg_points_rank=stat.get(
                "current_point_streak_avg_points_rank", 0
            ),
            first_game_id=stat["first_game_id"],
            last_game_id=stat["last_game_id"],
        )
        session.add(skater_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
    session.commit()


def run_aggregate_skater_stats():
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
                aggregate_skater_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                )
                aggregate_skater_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Weekly",
                )
                aggregate_skater_stats(
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
                aggregate_skater_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                )
                aggregate_skater_stats(
                    session,
                    aggregation_type="division",
                    aggregation_id=division_id,
                    debug_human_id=human_id_to_debug,
                    aggregation_window="Weekly",
                )
                aggregate_skater_stats(
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
            aggregate_skater_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
            )
            org_progress.update(1)
            aggregate_skater_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Weekly",
            )
            org_progress.update(2)
            aggregate_skater_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Daily",
            )
            org_progress.update(3)
        else:
            aggregate_skater_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
            )
            aggregate_skater_stats(
                session,
                aggregation_type="org",
                aggregation_id=org_id,
                debug_human_id=human_id_to_debug,
                aggregation_window="Weekly",
            )
            aggregate_skater_stats(
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
            aggregate_skater_stats(
                session,
                aggregation_type="level",
                aggregation_id=level_id,
                debug_human_id=human_id_to_debug,
            )
            level_progress.update(i + 1)
    else:
        # Debug mode or no levels - process without progress tracking
        for level_id in level_ids:
            aggregate_skater_stats(
                session,
                aggregation_type="level",
                aggregation_id=level_id,
                debug_human_id=human_id_to_debug,
            )


if __name__ == "__main__":
    run_aggregate_skater_stats()

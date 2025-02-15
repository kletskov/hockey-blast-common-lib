import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import sqlalchemy

from hockey_blast_common_lib.models import Game, Goal, Penalty, GameRoster, Organization, Division, Human, Level
from hockey_blast_common_lib.stats_models import OrgStatsSkater, DivisionStatsSkater, OrgStatsWeeklySkater, OrgStatsDailySkater, DivisionStatsWeeklySkater, DivisionStatsDailySkater, LevelStatsSkater
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import not_human_names, parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, MIN_GAMES_FOR_LEVEL_STATS
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org
from hockey_blast_common_lib.utils import get_start_datetime
from sqlalchemy import func, case, and_
from collections import defaultdict
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID

def aggregate_skater_stats(session, aggregation_type, aggregation_id, names_to_filter_out, debug_human_id=None, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    # Get the name of the aggregation, for debug purposes
    if aggregation_type == 'org':
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = session.query(Organization).filter(Organization.id == aggregation_id).first().organization_name
            filter_condition = Game.org_id == aggregation_id
        print(f"Aggregating skater stats for {aggregation_name} with window {aggregation_window}...")

    elif aggregation_type == 'division':
        aggregation_name = session.query(Division).filter(Division.id == aggregation_id).first().level
    elif aggregation_type == 'level':
        aggregation_name = session.query(Level).filter(Level.id == aggregation_id).first().level_name
    else:
        aggregation_name = "Unknown"

    if aggregation_type == 'org':
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailySkater
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklySkater
        else:
            StatsModel = OrgStatsSkater
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailySkater
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklySkater
        else:
            StatsModel = DivisionStatsSkater
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == 'level':
        StatsModel = LevelStatsSkater
        min_games = MIN_GAMES_FOR_LEVEL_STATS
        filter_condition = Division.level_id == aggregation_id
        # Add filter to only include games for the last 5 years
        # five_years_ago = datetime.now() - timedelta(days=5*365)
        # level_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP) >= five_years_ago
        # filter_condition = filter_condition & level_window_filter
    else:
        raise ValueError("Invalid aggregation type")

    # Apply aggregation window filter
    if aggregation_window:
        last_game_datetime_str = session.query(func.max(func.concat(Game.date, ' ', Game.time))).filter(filter_condition, Game.status.like('Final%')).scalar()
        start_datetime = get_start_datetime(last_game_datetime_str, aggregation_window)
        if start_datetime:
            game_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP).between(start_datetime, last_game_datetime_str)
            filter_condition = filter_condition & game_window_filter

    # Delete existing items from the stats table
    session.query(StatsModel).filter(StatsModel.aggregation_id == aggregation_id).delete()
    session.commit()

    # Filter for specific human_id if provided
    human_filter = []
    # if debug_human_id:
    #     human_filter = [GameRoster.human_id == debug_human_id]

    # Aggregate games played for each human in each division, excluding goalies
    games_played_stats = session.query(
        GameRoster.human_id,
        func.count(Game.id).label('games_played'),
        func.array_agg(Game.id).label('game_ids')
    ).join(Game, Game.id == GameRoster.game_id).join(Division, Game.division_id == Division.id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(GameRoster.human_id).all()

    # Aggregate goals for each human in each division, excluding goalies
    goals_stats = session.query(
        Goal.goal_scorer_id.label('human_id'),
        func.count(Goal.id).label('goals'),
        func.array_agg(Goal.game_id).label('goal_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.goal_scorer_id == GameRoster.human_id)).join(Division, Game.division_id == Division.id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Goal.goal_scorer_id).all()

    # Aggregate assists for each human in each division, excluding goalies
    assists_stats = session.query(
        Goal.assist_1_id.label('human_id'),
        func.count(Goal.id).label('assists'),
        func.array_agg(Goal.game_id).label('assist_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.assist_1_id == GameRoster.human_id)).join(Division, Game.division_id == Division.id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Goal.assist_1_id).all()

    assists_stats_2 = session.query(
        Goal.assist_2_id.label('human_id'),
        func.count(Goal.id).label('assists'),
        func.array_agg(Goal.game_id).label('assist_2_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.assist_2_id == GameRoster.human_id)).join(Division, Game.division_id == Division.id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Goal.assist_2_id).all()

    # Aggregate penalties for each human in each division, excluding goalies
    penalties_stats = session.query(
        Penalty.penalized_player_id.label('human_id'),
        func.count(Penalty.id).label('penalties'),
        func.sum(case((Penalty.penalty_minutes == 'GM', 1), else_=0)).label('gm_penalties'),  # New aggregation for GM penalties
        func.array_agg(Penalty.game_id).label('penalty_game_ids')
    ).join(Game, Game.id == Penalty.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Penalty.penalized_player_id == GameRoster.human_id)).join(Division, Game.division_id == Division.id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Penalty.penalized_player_id).all()

    # Combine the results
    stats_dict = {}
    for stat in games_played_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals': 0,
                'assists': 0,
                'penalties': 0,
                'gm_penalties': 0,  # Initialize GM penalties
                'points': 0,  # Initialize points
                'goals_per_game': 0.0,
                'points_per_game': 0.0,
                'assists_per_game': 0.0,
                'penalties_per_game': 0.0,
                'gm_penalties_per_game': 0.0,  # Initialize GM penalties per game
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        stats_dict[key]['games_played'] += stat.games_played
        stats_dict[key]['game_ids'].extend(stat.game_ids)

    # Filter out entries with games_played less than min_games
    stats_dict = {key: value for key, value in stats_dict.items() if value['games_played'] >= min_games}

    for stat in goals_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]['goals'] += stat.goals
            stats_dict[key]['points'] += stat.goals  # Update points

    for stat in assists_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]['assists'] += stat.assists
            stats_dict[key]['points'] += stat.assists  # Update points

    for stat in assists_stats_2:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]['assists'] += stat.assists
            stats_dict[key]['points'] += stat.assists  # Update points

    for stat in penalties_stats:
        key = (aggregation_id, stat.human_id)
        if key in stats_dict:
            stats_dict[key]['penalties'] += stat.penalties
            stats_dict[key]['gm_penalties'] += stat.gm_penalties  # Update GM penalties

    # Calculate per game stats
    for key, stat in stats_dict.items():
        if stat['games_played'] > 0:
            stat['goals_per_game'] = stat['goals'] / stat['games_played']
            stat['points_per_game'] = stat['points'] / stat['games_played']
            stat['assists_per_game'] = stat['assists'] / stat['games_played']
            stat['penalties_per_game'] = stat['penalties'] / stat['games_played']
            stat['gm_penalties_per_game'] = stat['gm_penalties'] / stat['games_played']  # Calculate GM penalties per game

    # Ensure all keys have valid human_id values
    stats_dict = {key: value for key, value in stats_dict.items() if key[1] is not None}

    # Populate first_game_id and last_game_id
    for key, stat in stats_dict.items():
        all_game_ids = stat['game_ids']
        if all_game_ids:
            first_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date, Game.time).first()
            last_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id'] = first_game.id if first_game else None
            stat['last_game_id'] = last_game.id if last_game else None

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Assign ranks within each level
    def assign_ranks(stats_dict, field):
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1][field], reverse=True)
        for rank, (key, stat) in enumerate(sorted_stats, start=1):
            stats_dict[key][f'{field}_rank'] = rank

    assign_ranks(stats_dict, 'games_played')
    assign_ranks(stats_dict, 'goals')
    assign_ranks(stats_dict, 'assists')
    assign_ranks(stats_dict, 'points')
    assign_ranks(stats_dict, 'penalties')
    assign_ranks(stats_dict, 'gm_penalties')  # Assign ranks for GM penalties
    assign_ranks(stats_dict, 'goals_per_game')
    assign_ranks(stats_dict, 'points_per_game')
    assign_ranks(stats_dict, 'assists_per_game')
    assign_ranks(stats_dict, 'penalties_per_game')
    assign_ranks(stats_dict, 'gm_penalties_per_game')  # Assign ranks for GM penalties per game

    # Debug output for specific human
    if debug_human_id:
        if any(key[1] == debug_human_id for key in stats_dict):
            human = session.query(Human).filter(Human.id == debug_human_id).first()
            human_name = f"{human.first_name} {human.last_name}" if human else "Unknown"
            print(f"For Human {debug_human_id} ({human_name}) for {aggregation_type} {aggregation_id} ({aggregation_name}) , total_in_rank {total_in_rank} and window {aggregation_window}:")
            for key, stat in stats_dict.items():
                if key[1] == debug_human_id:
                    for k, v in stat.items():
                        print(f"{k}: {v}")

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        goals_per_game = stat['goals'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        points_per_game = (stat['goals'] + stat['assists']) / stat['games_played'] if stat['games_played'] > 0 else 0.0
        assists_per_game = stat['assists'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        penalties_per_game = stat['penalties'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        gm_penalties_per_game = stat['gm_penalties'] / stat['games_played'] if stat['games_played'] > 0 else 0.0  # Calculate GM penalties per game
        skater_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_played=stat['games_played'],
            goals=stat['goals'],
            assists=stat['assists'],
            points=stat['goals'] + stat['assists'],
            penalties=stat['penalties'],
            gm_penalties=stat['gm_penalties'],  # Include GM penalties
            goals_per_game=goals_per_game,
            points_per_game=points_per_game,
            assists_per_game=assists_per_game,
            penalties_per_game=penalties_per_game,
            gm_penalties_per_game=gm_penalties_per_game,  # Include GM penalties per game
            games_played_rank=stat['games_played_rank'],
            goals_rank=stat['goals_rank'],
            assists_rank=stat['assists_rank'],
            points_rank=stat['points_rank'],
            penalties_rank=stat['penalties_rank'],
            gm_penalties_rank=stat['gm_penalties_rank'],  # Include GM penalties rank
            goals_per_game_rank=stat['goals_per_game_rank'],
            points_per_game_rank=stat['points_per_game_rank'],
            assists_per_game_rank=stat['assists_per_game_rank'],
            penalties_per_game_rank=stat['penalties_per_game_rank'],
            gm_penalties_per_game_rank=stat['gm_penalties_per_game_rank'],  # Include GM penalties per game rank
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
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
        print(f"Aggregating skater stats for {len(division_ids)} divisions in org_id {org_id}...")
        total_divisions = len(division_ids)
        processed_divisions = 0
        for division_id in division_ids:
            aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)
            aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Weekly')
            aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Daily')
            processed_divisions += 1
            if human_id_to_debug is None:
                print(f"\rProcessed {processed_divisions}/{total_divisions} divisions ({(processed_divisions/total_divisions)*100:.2f}%)", end="")

        aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)
        aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Weekly')
        aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Daily')
        
    # Aggregate by level
    level_ids = session.query(Division.level_id).distinct().all()
    level_ids = [level_id[0] for level_id in level_ids]
    total_levels = len(level_ids)
    processed_levels = 0
    for level_id in level_ids:
        if level_id is None:
            continue
        if human_id_to_debug is None:
            print(f"\rProcessed {processed_levels}/{total_levels} levels ({(processed_levels/total_levels)*100:.2f}%)", end="")
        processed_levels += 1
        aggregate_skater_stats(session, aggregation_type='level', aggregation_id=level_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)

if __name__ == "__main__":
    run_aggregate_skater_stats()

import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import sqlalchemy

from hockey_blast_common_lib.models import Game, Goal, Penalty, GameRoster
from hockey_blast_common_lib.stats_models import OrgStatsSkater, DivisionStatsSkater, OrgStatsWeeklySkater, OrgStatsDailySkater, DivisionStatsWeeklySkater, DivisionStatsDailySkater
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import not_human_names, parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues
from sqlalchemy import func, case, and_

def aggregate_skater_stats(session, aggregation_type, aggregation_id, names_to_filter_out, filter_human_id=None, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailySkater
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklySkater
        else:
            StatsModel = OrgStatsSkater
        min_games = MIN_GAMES_FOR_ORG_STATS
        filter_condition = Game.org_id == aggregation_id
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailySkater
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklySkater
        else:
            StatsModel = DivisionStatsSkater
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    else:
        raise ValueError("Invalid aggregation type")

    # Apply aggregation window filter
    if aggregation_window:
        last_game_datetime = session.query(func.max(func.concat(Game.date, ' ', Game.time))).filter(filter_condition, Game.status.like('Final%')).scalar()
        if last_game_datetime:
            last_game_datetime = datetime.strptime(last_game_datetime, '%Y-%m-%d %H:%M:%S')
            if aggregation_window == 'Daily':
                start_datetime = last_game_datetime - timedelta(days=1)
            elif aggregation_window == 'Weekly':
                start_datetime = last_game_datetime - timedelta(weeks=1)
            else:
                start_datetime = None
            if start_datetime:
                game_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP).between(start_datetime, last_game_datetime)
                filter_condition = filter_condition & game_window_filter

    # Delete existing items from the stats table
    session.query(StatsModel).filter(StatsModel.aggregation_id == aggregation_id).delete()
    session.commit()

    # Filter for specific human_id if provided
    human_filter = []
    if filter_human_id:
        human_filter = [GameRoster.human_id == filter_human_id]

    # Aggregate games played for each human in each division, excluding goalies
    games_played_stats = session.query(
        Game.org_id,
        GameRoster.human_id,
        func.count(Game.id).label('games_played'),
        func.array_agg(Game.id).label('game_ids')
    ).join(GameRoster, Game.id == GameRoster.game_id).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Game.org_id, GameRoster.human_id).all()

    # Aggregate goals for each human in each division, excluding goalies
    goals_stats = session.query(
        Game.org_id,
        Goal.goal_scorer_id.label('human_id'),
        func.count(Goal.id).label('goals'),
        func.array_agg(Goal.game_id).label('goal_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.goal_scorer_id == GameRoster.human_id)).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Game.org_id, Goal.goal_scorer_id).all()

    # Aggregate assists for each human in each division, excluding goalies
    assists_stats = session.query(
        Game.org_id,
        Goal.assist_1_id.label('human_id'),
        func.count(Goal.id).label('assists'),
        func.array_agg(Goal.game_id).label('assist_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.assist_1_id == GameRoster.human_id)).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Game.org_id, Goal.assist_1_id).all()

    assists_stats_2 = session.query(
        Game.org_id,
        Goal.assist_2_id.label('human_id'),
        func.count(Goal.id).label('assists'),
        func.array_agg(Goal.game_id).label('assist_2_game_ids')
    ).join(Game, Game.id == Goal.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Goal.assist_2_id == GameRoster.human_id)).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Game.org_id, Goal.assist_2_id).all()

    # Aggregate penalties for each human in each division, excluding goalies
    penalties_stats = session.query(
        Game.org_id,
        Penalty.penalized_player_id.label('human_id'),
        func.count(Penalty.id).label('penalties'),
        func.array_agg(Penalty.game_id).label('penalty_game_ids')
    ).join(Game, Game.id == Penalty.game_id).join(GameRoster, and_(Game.id == GameRoster.game_id, Penalty.penalized_player_id == GameRoster.human_id)).filter(filter_condition, ~GameRoster.role.ilike('g'), *human_filter).group_by(Game.org_id, Penalty.penalized_player_id).all()

    # Combine the results
    stats_dict = {}
    for stat in games_played_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        stats_dict[key] = {
            'games_played': stat.games_played,
            'goals': 0,
            'assists': 0,
            'penalties': 0,
            'points': 0,  # Initialize points
            'goals_per_game': 0.0,
            'points_per_game': 0.0,
            'assists_per_game': 0.0,
            'penalties_per_game': 0.0,
            'game_ids': stat.game_ids,
            'first_game_id': None,
            'last_game_id': None
        }

    for stat in goals_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals': stat.goals,
                'assists': 0,
                'penalties': 0,
                'points': stat.goals,  # Initialize points with goals
                'goals_per_game': 0.0,
                'points_per_game': 0.0,
                'assists_per_game': 0.0,
                'penalties_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        else:
            stats_dict[key]['goals'] += stat.goals
            stats_dict[key]['points'] += stat.goals  # Update points

    for stat in assists_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals': 0,
                'assists': stat.assists,
                'penalties': 0,
                'points': stat.assists,  # Initialize points with assists
                'goals_per_game': 0.0,
                'points_per_game': 0.0,
                'assists_per_game': 0.0,
                'penalties_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        else:
            stats_dict[key]['assists'] += stat.assists
            stats_dict[key]['points'] += stat.assists  # Update points

    for stat in assists_stats_2:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals': 0,
                'assists': stat.assists,
                'penalties': 0,
                'points': stat.assists,  # Initialize points with assists
                'goals_per_game': 0.0,
                'points_per_game': 0.0,
                'assists_per_game': 0.0,
                'penalties_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        else:
            stats_dict[key]['assists'] += stat.assists
            stats_dict[key]['points'] += stat.assists  # Update points

    for stat in penalties_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals': 0,
                'assists': 0,
                'penalties': stat.penalties,
                'points': 0,  # Initialize points
                'goals_per_game': 0.0,
                'points_per_game': 0.0,
                'assists_per_game': 0.0,
                'penalties_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        else:
            stats_dict[key]['penalties'] += stat.penalties

    # Calculate per game stats
    for key, stat in stats_dict.items():
        if stat['games_played'] > 0:
            stat['goals_per_game'] = stat['goals'] / stat['games_played']
            stat['points_per_game'] = stat['points'] / stat['games_played']
            stat['assists_per_game'] = stat['assists'] / stat['games_played']
            stat['penalties_per_game'] = stat['penalties'] / stat['games_played']

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

    # Debug output for totals if filter_human_id is provided
    if filter_human_id:
        for key, stat in stats_dict.items():
            if key[1] == filter_human_id:
                print(f"Human ID: {filter_human_id}")
                print(f"Total Games Played: {stat['games_played']}")
                print(f"Total Goals: {stat['goals']}")
                print(f"Total Assists: {stat['assists']}")
                print(f"Total Penalties: {stat['penalties']}")

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Assign ranks
    def assign_ranks(stats_dict, field):
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1][field], reverse=True)
        for rank, (key, stat) in enumerate(sorted_stats, start=1):
            stats_dict[key][f'{field}_rank'] = rank

    assign_ranks(stats_dict, 'games_played')
    assign_ranks(stats_dict, 'goals')
    assign_ranks(stats_dict, 'assists')
    assign_ranks(stats_dict, 'points')
    assign_ranks(stats_dict, 'penalties')
    assign_ranks(stats_dict, 'goals_per_game')
    assign_ranks(stats_dict, 'points_per_game')
    assign_ranks(stats_dict, 'assists_per_game')
    assign_ranks(stats_dict, 'penalties_per_game')

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        if stat['games_played'] < min_games:
            continue
        goals_per_game = stat['goals'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        points_per_game = (stat['goals'] + stat['assists']) / stat['games_played'] if stat['games_played'] > 0 else 0.0
        assists_per_game = stat['assists'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        penalties_per_game = stat['penalties'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        skater_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_played=stat['games_played'],
            goals=stat['goals'],
            assists=stat['assists'],
            points=stat['goals'] + stat['assists'],
            penalties=stat['penalties'],
            goals_per_game=goals_per_game,
            points_per_game=points_per_game,
            assists_per_game=assists_per_game,
            penalties_per_game=penalties_per_game,
            games_played_rank=stat['games_played_rank'],
            goals_rank=stat['goals_rank'],
            assists_rank=stat['assists_rank'],
            points_rank=stat['points_rank'],
            penalties_rank=stat['penalties_rank'],
            goals_per_game_rank=stat['goals_per_game_rank'],
            points_per_game_rank=stat['points_per_game_rank'],
            assists_per_game_rank=stat['assists_per_game_rank'],
            penalties_per_game_rank=stat['penalties_per_game_rank'],
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
        )
        session.add(skater_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
            print(f"\r{i}/{total_items} ({(i/total_items)*100:.2f}%)", end="")
    session.commit()
    print(f"\r{total_items}/{total_items} (100.00%)")
    print("\nDone.")

# Example usage
if __name__ == "__main__":
    args = parse_args()
    org_alias = args.org
    session = create_session("boss")
    org_id = get_org_id_from_alias(session, org_alias)

    division_ids = get_division_ids_for_last_season_in_all_leagues(session, org_id)
    print(f"Aggregating skater stats for {len(division_ids)} divisions in {org_alias}...")
    for division_id in division_ids:
        aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, filter_human_id=None)
        aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, filter_human_id=None, aggregation_window='Weekly')
        aggregate_skater_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, filter_human_id=None, aggregation_window='Daily')

    aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, filter_human_id=None)
    aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, filter_human_id=None, aggregation_window='Weekly')
    aggregate_skater_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, filter_human_id=None, aggregation_window='Daily')

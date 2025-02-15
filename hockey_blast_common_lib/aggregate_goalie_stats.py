import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import sqlalchemy

from hockey_blast_common_lib.models import Game, Goal, Penalty, GameRoster, Organization, Division, Human, Level
from hockey_blast_common_lib.stats_models import OrgStatsGoalie, DivisionStatsGoalie, OrgStatsWeeklyGoalie, OrgStatsDailyGoalie, DivisionStatsWeeklyGoalie, DivisionStatsDailyGoalie, LevelStatsGoalie
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import not_human_names, parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, MIN_GAMES_FOR_LEVEL_STATS
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org, get_start_datetime
from hockey_blast_common_lib.utils import assign_ranks
from sqlalchemy import func, case, and_
from collections import defaultdict
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID

def aggregate_goalie_stats(session, aggregation_type, aggregation_id, names_to_filter_out, debug_human_id=None, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    # Get the name of the aggregation, for debug purposes
    if aggregation_type == 'org':
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = session.query(Organization).filter(Organization.id == aggregation_id).first().organization_name
            filter_condition = Game.org_id == aggregation_id
        print(f"Aggregating goalie stats for {aggregation_name} with window {aggregation_window}...")
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyGoalie
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyGoalie
        else:
            StatsModel = OrgStatsGoalie
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyGoalie
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyGoalie
        else:
            StatsModel = DivisionStatsGoalie
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == 'level':
        StatsModel = LevelStatsGoalie
        min_games = MIN_GAMES_FOR_LEVEL_STATS
        filter_condition = Division.level_id == aggregation_id
        # Add filter to only include games for the last 5 years
        five_years_ago = datetime.now() - timedelta(days=5*365)
        level_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP) >= five_years_ago
        filter_condition = filter_condition & level_window_filter
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

    # Aggregate games played, goals allowed, and shots faced for each goalie
    goalie_stats = session.query(
        GameRoster.human_id,
        func.count(Game.id).label('games_played'),
        func.sum(case((GameRoster.team_id == Game.home_team_id, Game.visitor_final_score), else_=Game.home_final_score)).label('goals_allowed'),
        func.sum(case((GameRoster.team_id == Game.home_team_id, Game.visitor_period_1_shots + Game.visitor_period_2_shots + Game.visitor_period_3_shots + Game.visitor_ot_shots + Game.visitor_so_shots), else_=Game.home_period_1_shots + Game.home_period_2_shots + Game.home_period_3_shots + Game.home_ot_shots + Game.home_so_shots)).label('shots_faced'),
        func.array_agg(Game.id).label('game_ids')
    ).join(Game, GameRoster.game_id == Game.id).join(Division, Game.division_id == Division.id).filter(filter_condition, GameRoster.role.ilike('g')).group_by(GameRoster.human_id).all()

    # Combine the results
    stats_dict = {}
    for stat in goalie_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_played': 0,
                'goals_allowed': 0,
                'shots_faced': 0,
                'goals_allowed_per_game': 0.0,
                'save_percentage': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        stats_dict[key]['games_played'] += stat.games_played
        stats_dict[key]['goals_allowed'] += stat.goals_allowed if stat.goals_allowed is not None else 0
        stats_dict[key]['shots_faced'] += stat.shots_faced if stat.shots_faced is not None else 0
        stats_dict[key]['game_ids'].extend(stat.game_ids)

    # Filter out entries with games_played less than min_games
    stats_dict = {key: value for key, value in stats_dict.items() if value['games_played'] >= min_games}

    # Calculate per game stats
    for key, stat in stats_dict.items():
        if stat['games_played'] > 0:
            stat['goals_allowed_per_game'] = stat['goals_allowed'] / stat['games_played']
            stat['save_percentage'] = (stat['shots_faced'] - stat['goals_allowed']) / stat['shots_faced'] if stat['shots_faced'] > 0 else 0.0

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
    assign_ranks(stats_dict, 'games_played')
    assign_ranks(stats_dict, 'goals_allowed', reverse_rank=True)
    assign_ranks(stats_dict, 'shots_faced')
    assign_ranks(stats_dict, 'goals_allowed_per_game', reverse_rank=True)
    assign_ranks(stats_dict, 'save_percentage')

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
        goals_allowed_per_game = stat['goals_allowed'] / stat['games_played'] if stat['games_played'] > 0 else 0.0
        save_percentage = (stat['shots_faced'] - stat['goals_allowed']) / stat['shots_faced'] if stat['shots_faced'] > 0 else 0.0
        goalie_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_played=stat['games_played'],
            goals_allowed=stat['goals_allowed'],
            shots_faced=stat['shots_faced'],
            goals_allowed_per_game=goals_allowed_per_game,
            save_percentage=save_percentage,
            games_played_rank=stat['games_played_rank'],
            goals_allowed_rank=stat['goals_allowed_rank'],
            shots_faced_rank=stat['shots_faced_rank'],
            goals_allowed_per_game_rank=stat['goals_allowed_per_game_rank'],
            save_percentage_rank=stat['save_percentage_rank'],
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
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
        print(f"Aggregating goalie stats for {len(division_ids)} divisions in org_id {org_id}...")
        total_divisions = len(division_ids)
        processed_divisions = 0
        for division_id in division_ids:
            aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)
            aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Weekly')
            aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Daily')
            processed_divisions += 1
            if human_id_to_debug is None:
                print(f"\rProcessed {processed_divisions}/{total_divisions} divisions ({(processed_divisions/total_divisions)*100:.2f}%)", end="")

        aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)
        aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Weekly')
        aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug, aggregation_window='Daily')
        
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
        aggregate_goalie_stats(session, aggregation_type='level', aggregation_id=level_id, names_to_filter_out=not_human_names, debug_human_id=human_id_to_debug)

if __name__ == "__main__":
    run_aggregate_goalie_stats()
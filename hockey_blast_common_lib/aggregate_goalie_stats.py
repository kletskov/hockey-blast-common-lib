import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import sqlalchemy
from hockey_blast_common_lib.models import  Game, GameRoster
from hockey_blast_common_lib.stats_models import OrgStatsGoalie, DivisionStatsGoalie, OrgStatsWeeklyGoalie, OrgStatsDailyGoalie, DivisionStatsWeeklyGoalie, DivisionStatsDailyGoalie
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import not_human_names, parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org

def aggregate_goalie_stats(session, aggregation_type, aggregation_id, names_to_filter_out, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyGoalie
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyGoalie
        else:
            StatsModel = OrgStatsGoalie
        min_games = MIN_GAMES_FOR_ORG_STATS
        filter_condition = Game.org_id == aggregation_id
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyGoalie
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyGoalie
        else:
            StatsModel = DivisionStatsGoalie
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

    # Aggregate games played, goals allowed, and shots faced for each goalie
    goalie_stats = session.query(
        GameRoster.human_id,
        func.count(Game.id).label('games_played'),
        func.sum(case((GameRoster.team_id == Game.home_team_id, Game.visitor_final_score), else_=Game.home_final_score)).label('goals_allowed'),
        func.sum(case((GameRoster.team_id == Game.home_team_id, Game.visitor_period_1_shots + Game.visitor_period_2_shots + Game.visitor_period_3_shots + Game.visitor_ot_shots + Game.visitor_so_shots), else_=Game.home_period_1_shots + Game.home_period_2_shots + Game.home_period_3_shots + Game.home_ot_shots + Game.home_so_shots)).label('shots_faced'),
        func.array_agg(Game.id).label('game_ids')
    ).join(Game, GameRoster.game_id == Game.id).filter(filter_condition, GameRoster.role == 'G').group_by(GameRoster.human_id).all()

    # Combine the results
    stats_dict = {}
    for stat in goalie_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        stats_dict[key] = {
            'games_played': stat.games_played,
            'goals_allowed': stat.goals_allowed if stat.goals_allowed is not None else 0,
            'shots_faced': stat.shots_faced if stat.shots_faced is not None else 0,
            'goals_allowed_per_game': 0.0,
            'save_percentage': 0.0,
            'game_ids': stat.game_ids,
            'first_game_id': None,
            'last_game_id': None
        }

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

    # Assign ranks
    def assign_ranks(stats_dict, field):
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1][field], reverse=True)
        for rank, (key, stat) in enumerate(sorted_stats, start=1):
            stats_dict[key][f'{field}_rank'] = rank

    assign_ranks(stats_dict, 'games_played')
    assign_ranks(stats_dict, 'goals_allowed')
    assign_ranks(stats_dict, 'goals_allowed_per_game')
    assign_ranks(stats_dict, 'shots_faced')
    assign_ranks(stats_dict, 'save_percentage')

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        if stat['games_played'] < min_games:
            continue
        goalie_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_played=stat['games_played'],
            goals_allowed=stat['goals_allowed'],
            goals_allowed_per_game=stat['goals_allowed_per_game'],
            shots_faced=stat['shots_faced'],
            save_percentage=stat['save_percentage'],
            games_played_rank=stat['games_played_rank'],
            goals_allowed_rank=stat['goals_allowed_rank'],
            goals_allowed_per_game_rank=stat['goals_allowed_per_game_rank'],
            shots_faced_rank=stat['shots_faced_rank'],
            save_percentage_rank=stat['save_percentage_rank'],
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
        )
        session.add(goalie_stat)
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
    print(f"Aggregating goalie stats for {len(division_ids)} divisions in {org_alias}...")
    for division_id in division_ids:
        aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names)
        aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
        aggregate_goalie_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
    aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names)
    aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
    aggregate_goalie_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
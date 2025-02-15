import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from datetime import datetime, timedelta
import sqlalchemy
from hockey_blast_common_lib.models import Game, Penalty, Organization, Division
from hockey_blast_common_lib.stats_models import OrgStatsReferee, DivisionStatsReferee, OrgStatsWeeklyReferee, OrgStatsDailyReferee, DivisionStatsWeeklyReferee, DivisionStatsDailyReferee, LevelStatsReferee
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, MIN_GAMES_FOR_LEVEL_STATS, not_human_names
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org
from hockey_blast_common_lib.utils import assign_ranks
from hockey_blast_common_lib.utils import get_start_datetime
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID

def aggregate_referee_stats(session, aggregation_type, aggregation_id, names_to_filter_out, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = session.query(Organization).filter(Organization.id == aggregation_id).first().organization_name
            filter_condition = Game.org_id == aggregation_id
        print(f"Aggregating referee stats for {aggregation_name} with window {aggregation_window}...")
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyReferee
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyReferee
        else:
            StatsModel = OrgStatsReferee
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyReferee
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyReferee
        else:
            StatsModel = DivisionStatsReferee
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == 'level':
        StatsModel = LevelStatsReferee
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

    # Aggregate games reffed for each referee
    games_reffed_stats = session.query(
        Game.referee_1_id.label('human_id'),
        func.count(Game.id).label('games_reffed'),
        func.array_agg(Game.id).label('game_ids')
    ).filter(filter_condition).group_by(Game.referee_1_id).all()

    games_reffed_stats_2 = session.query(
        Game.referee_2_id.label('human_id'),
        func.count(Game.id).label('games_reffed'),
        func.array_agg(Game.id).label('game_ids')
    ).filter(filter_condition).group_by(Game.referee_2_id).all()

    # Aggregate penalties given for each referee
    penalties_given_stats = session.query(
        Game.id.label('game_id'),
        Game.referee_1_id,
        Game.referee_2_id,
        func.count(Penalty.id).label('penalties_given'),
        func.sum(case((func.lower(Penalty.penalty_minutes) == 'gm', 1), else_=0)).label('gm_given')
    ).join(Game, Game.id == Penalty.game_id).filter(filter_condition).group_by(Game.id, Game.referee_1_id, Game.referee_2_id).all()

    # Combine the results
    stats_dict = {}
    for stat in games_reffed_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_reffed': 0,
                'penalties_given': 0,
                'gm_given': 0,
                'penalties_per_game': 0.0,
                'gm_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        stats_dict[key]['games_reffed'] += stat.games_reffed
        stats_dict[key]['game_ids'].extend(stat.game_ids)

    for stat in games_reffed_stats_2:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_reffed': 0,
                'penalties_given': 0,
                'gm_given': 0,
                'penalties_per_game': 0.0,
                'gm_per_game': 0.0,
                'game_ids': [],
                'first_game_id': None,
                'last_game_id': None
            }
        stats_dict[key]['games_reffed'] += stat.games_reffed
        stats_dict[key]['game_ids'].extend(stat.game_ids)

    # Filter out entries with games_reffed less than min_games
    stats_dict = {key: value for key, value in stats_dict.items() if value['games_reffed'] >= min_games}

    for stat in penalties_given_stats:
        if stat.referee_1_id and stat.referee_1_id not in human_ids_to_filter:
            key = (aggregation_id, stat.referee_1_id)
            if key in stats_dict:
                stats_dict[key]['penalties_given'] += stat.penalties_given / 2
                stats_dict[key]['gm_given'] += stat.gm_given / 2
                stats_dict[key]['game_ids'].append(stat.game_id)

        if stat.referee_2_id and stat.referee_2_id not in human_ids_to_filter:
            key = (aggregation_id, stat.referee_2_id)
            if key in stats_dict:
                stats_dict[key]['penalties_given'] += stat.penalties_given / 2
                stats_dict[key]['gm_given'] += stat.gm_given / 2
                stats_dict[key]['game_ids'].append(stat.game_id)

    # Calculate per game stats
    for key, stat in stats_dict.items():
        if stat['games_reffed'] > 0:
            stat['penalties_per_game'] = stat['penalties_given'] / stat['games_reffed']
            stat['gm_per_game'] = stat['gm_given'] / stat['games_reffed']

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
    assign_ranks(stats_dict, 'games_reffed')
    assign_ranks(stats_dict, 'penalties_given')
    assign_ranks(stats_dict, 'penalties_per_game')
    assign_ranks(stats_dict, 'gm_given')
    assign_ranks(stats_dict, 'gm_per_game')

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        referee_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_reffed=stat['games_reffed'],
            penalties_given=stat['penalties_given'],
            penalties_per_game=stat['penalties_per_game'],
            gm_given=stat['gm_given'],
            gm_per_game=stat['gm_per_game'],
            games_reffed_rank=stat['games_reffed_rank'],
            penalties_given_rank=stat['penalties_given_rank'],
            penalties_per_game_rank=stat['penalties_per_game_rank'],
            gm_given_rank=stat['gm_given_rank'],
            gm_per_game_rank=stat['gm_per_game_rank'],
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
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
        print(f"Aggregating referee stats for {len(division_ids)} divisions in org_id {org_id}...")
        total_divisions = len(division_ids)
        processed_divisions = 0
        for division_id in division_ids:
            aggregate_referee_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names)
            aggregate_referee_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
            aggregate_referee_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
            processed_divisions += 1
            if human_id_to_debug is None:
                print(f"\rProcessed {processed_divisions}/{total_divisions} divisions ({(processed_divisions/total_divisions)*100:.2f}%)", end="")

        aggregate_referee_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names)
        aggregate_referee_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
        aggregate_referee_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
        
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
        aggregate_referee_stats(session, aggregation_type='level', aggregation_id=level_id, names_to_filter_out=not_human_names)

if __name__ == "__main__":
    run_aggregate_referee_stats()
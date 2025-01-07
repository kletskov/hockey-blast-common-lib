import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from datetime import datetime, timedelta
import sqlalchemy
from hockey_blast_common_lib.models import Game, GameRoster
from hockey_blast_common_lib.stats_models import OrgStatsHuman, DivisionStatsHuman, OrgStatsDailyHuman, OrgStatsWeeklyHuman, DivisionStatsDailyHuman, DivisionStatsWeeklyHuman
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, not_human_names
from hockey_blast_common_lib.utils import get_fake_human_for_stats, get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues

def aggregate_human_stats(session, aggregation_type, aggregation_id, names_to_filter_out, human_id_filter=None, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyHuman
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyHuman
        else:
            StatsModel = OrgStatsHuman
        min_games = MIN_GAMES_FOR_ORG_STATS
        filter_condition = Game.org_id == aggregation_id
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyHuman
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyHuman
        else:
            StatsModel = DivisionStatsHuman
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    else:
        raise ValueError("Invalid aggregation type")

    # Delete existing items from the stats table
    session.query(StatsModel).filter(StatsModel.aggregation_id == aggregation_id).delete()
    session.commit()

    # Filter for specific human_id if provided
    human_filter = []
    if human_id_filter:
        human_filter = [GameRoster.human_id == human_id_filter]

    # Filter games by status
    game_status_filter = Game.status.like('Final%')

    # Apply aggregation window filter
    if aggregation_window:
        last_game_datetime = session.query(func.max(func.concat(Game.date, ' ', Game.time))).filter(filter_condition, game_status_filter).scalar()
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

    # Aggregate games played for each human in each role
    human_stats = session.query(
        GameRoster.human_id,
        func.count(func.distinct(case((GameRoster.role != 'G', Game.id), else_=None))).label('games_skater'),
        func.count(func.distinct(case((GameRoster.role == 'G', Game.id), else_=None))).label('games_goalie'),
        func.array_agg(func.distinct(Game.id)).label('game_ids')
    ).join(Game, GameRoster.game_id == Game.id).filter(filter_condition, game_status_filter, *human_filter).group_by(GameRoster.human_id).all()

    # Aggregate referee and scorekeeper games from Game table
    referee_stats = session.query(
        Game.referee_1_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_referee'),
        func.array_agg(func.distinct(Game.id)).label('referee_game_ids')
    ).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.referee_1_id).all()

    referee_stats_2 = session.query(
        Game.referee_2_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_referee'),
        func.array_agg(func.distinct(Game.id)).label('referee_game_ids')
    ).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.referee_2_id).all()

    scorekeeper_stats = session.query(
        Game.scorekeeper_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_scorekeeper'),
        func.array_agg(func.distinct(Game.id)).label('scorekeeper_game_ids')
    ).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.scorekeeper_id).all()

    # Combine the results
    stats_dict = {}
    for stat in human_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        stats_dict[key] = {
            'games_total': stat.games_skater + stat.games_goalie,
            'games_skater': stat.games_skater,
            'games_goalie': stat.games_goalie,
            'games_referee': 0,
            'games_scorekeeper': 0,
            'game_ids': stat.game_ids,
            'referee_game_ids': [],
            'scorekeeper_game_ids': []
        }

    for stat in referee_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': stat.games_referee,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': stat.games_referee,
                'games_scorekeeper': 0,
                'game_ids': [],
                'referee_game_ids': stat.referee_game_ids,
                'scorekeeper_game_ids': []
            }
        else:
            stats_dict[key]['games_referee'] += stat.games_referee
            stats_dict[key]['games_total'] += stat.games_referee
            stats_dict[key]['referee_game_ids'] += stat.referee_game_ids

    for stat in referee_stats_2:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': stat.games_referee,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': stat.games_referee,
                'games_scorekeeper': 0,
                'game_ids': [],
                'referee_game_ids': stat.referee_game_ids,
                'scorekeeper_game_ids': []
            }
        else:
            stats_dict[key]['games_referee'] += stat.games_referee
            stats_dict[key]['games_total'] += stat.games_referee
            stats_dict[key]['referee_game_ids'] += stat.referee_game_ids

    for stat in scorekeeper_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': stat.games_scorekeeper,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': stat.games_scorekeeper,
                'game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': stat.scorekeeper_game_ids
            }
        else:
            stats_dict[key]['games_scorekeeper'] += stat.games_scorekeeper
            stats_dict[key]['games_total'] += stat.games_scorekeeper
            stats_dict[key]['scorekeeper_game_ids'] += stat.scorekeeper_game_ids

    # Ensure all keys have valid human_id values
    stats_dict = {key: value for key, value in stats_dict.items() if key[1] is not None}

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Assign ranks
    def assign_ranks(stats_dict, field):
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1][field], reverse=True)
        for rank, (key, stat) in enumerate(sorted_stats, start=1):
            stats_dict[key][f'{field}_rank'] = rank

    assign_ranks(stats_dict, 'games_total')
    assign_ranks(stats_dict, 'games_skater')
    assign_ranks(stats_dict, 'games_goalie')
    assign_ranks(stats_dict, 'games_referee')
    assign_ranks(stats_dict, 'games_scorekeeper')

    # Populate first_game_id and last_game_id
    for key, stat in stats_dict.items():
        all_game_ids = stat['game_ids'] + stat['referee_game_ids'] + stat['scorekeeper_game_ids']
        if all_game_ids:
            first_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date, Game.time).first()
            last_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id'] = first_game.id if first_game else None
            stat['last_game_id'] = last_game.id if last_game else None

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        if human_id_filter and human_id != human_id_filter:
            continue
        if stat['games_total'] < min_games:
            continue

        human_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_total=stat['games_total'],
            games_total_rank=stat['games_total_rank'],
            games_skater=stat['games_skater'],
            games_skater_rank=stat['games_skater_rank'],
            games_goalie=stat['games_goalie'],
            games_goalie_rank=stat['games_goalie_rank'],
            games_referee=stat['games_referee'],
            games_referee_rank=stat['games_referee_rank'],
            games_scorekeeper=stat['games_scorekeeper'],
            games_scorekeeper_rank=stat['games_scorekeeper_rank'],
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
        )
        session.add(human_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
            print(f"\r{i}/{total_items} ({(i/total_items)*100:.2f}%)", end="")
    session.commit()

    # Fetch fake human ID for overall stats
    fake_human_id = get_fake_human_for_stats(session)

    # Calculate overall stats
    overall_stats = {
        'games_total': sum(stat['games_total'] for stat in stats_dict.values()),
        'games_skater': sum(stat['games_skater'] for stat in stats_dict.values()),
        'games_goalie': sum(stat['games_goalie'] for stat in stats_dict.values()),
        'games_referee': sum(stat['games_referee'] for stat in stats_dict.values()),
        'games_scorekeeper': sum(stat['games_scorekeeper'] for stat in stats_dict.values()),
        'total_in_rank': total_in_rank,
        'first_game_id': None,
        'last_game_id': None
    }

    # Populate first_game_id and last_game_id for overall stats
    all_game_ids = [game_id for stat in stats_dict.values() for game_id in stat['game_ids'] + stat['referee_game_ids'] + stat['scorekeeper_game_ids']]
    if all_game_ids:
        first_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date, Game.time).first()
        last_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date.desc(), Game.time.desc()).first()
        overall_stats['first_game_id'] = first_game.id if first_game else None
        overall_stats['last_game_id'] = last_game.id if last_game else None

    # Insert overall stats for the fake human
    overall_human_stat = StatsModel(
        aggregation_id=aggregation_id,
        human_id=fake_human_id,
        games_total=overall_stats['games_total'],
        games_total_rank=0,  # Overall stats do not need a rank
        games_skater=overall_stats['games_skater'],
        games_skater_rank=0,  # Overall stats do not need a rank
        games_goalie=overall_stats['games_goalie'],
        games_goalie_rank=0,  # Overall stats do not need a rank
        games_referee=overall_stats['games_referee'],
        games_referee_rank=0,  # Overall stats do not need a rank
        games_scorekeeper=overall_stats['games_scorekeeper'],
        games_scorekeeper_rank=0,  # Overall stats do not need a rank
        total_in_rank=overall_stats['total_in_rank'],
        first_game_id=overall_stats['first_game_id'],
        last_game_id=overall_stats['last_game_id']
    )
    session.add(overall_human_stat)
    session.commit()

    print(f"\r{total_items}/{total_items} (100.00%)")
    print("\nDone.")

# Example usage
if __name__ == "__main__":
    args = parse_args()
    org_alias=args.org
    session = create_session("boss")
    org_id = get_org_id_from_alias(session, org_alias)

    division_ids = get_division_ids_for_last_season_in_all_leagues(session, org_id)
    print(f"Aggregating human stats for {len(division_ids)} divisions in {org_alias}...")
    for division_id in division_ids:
        aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=None)
        aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=None, aggregation_window='Daily')
        aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=None, aggregation_window='Weekly')

    aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=None)
    aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=None, aggregation_window='Daily')
    aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=None, aggregation_window='Weekly')
import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from datetime import datetime, timedelta
import sqlalchemy
from hockey_blast_common_lib.models import Game, GameRoster, Organization, Division
from hockey_blast_common_lib.stats_models import OrgStatsHuman, DivisionStatsHuman, OrgStatsDailyHuman, OrgStatsWeeklyHuman, DivisionStatsDailyHuman, DivisionStatsWeeklyHuman, LevelStatsHuman
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, MIN_GAMES_FOR_LEVEL_STATS, not_human_names
from hockey_blast_common_lib.utils import get_fake_human_for_stats, get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org
from hockey_blast_common_lib.utils import assign_ranks
from hockey_blast_common_lib.utils import get_start_datetime
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID

def aggregate_human_stats(session, aggregation_type, aggregation_id, names_to_filter_out, human_id_filter=None, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = session.query(Organization).filter(Organization.id == aggregation_id).first().organization_name
            filter_condition = Game.org_id == aggregation_id
        print(f"Aggregating human stats for {aggregation_name} with window {aggregation_window}...")
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyHuman
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyHuman
        else:
            StatsModel = OrgStatsHuman
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyHuman
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyHuman
        else:
            StatsModel = DivisionStatsHuman
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    elif aggregation_type == 'level':
        StatsModel = LevelStatsHuman
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
    if human_id_filter:
        human_filter = [GameRoster.human_id == human_id_filter]

    # Filter games by status
    game_status_filter = Game.status.like('Final%')

    # Aggregate skater games played
    skater_stats = session.query(
        GameRoster.human_id,
        func.count(func.distinct(Game.id)).label('games_skater'),
        func.array_agg(func.distinct(Game.id)).label('skater_game_ids')
    ).join(Game, GameRoster.game_id == Game.id).join(Division, Game.division_id == Division.id).filter(filter_condition, game_status_filter, ~GameRoster.role.ilike('G'), *human_filter).group_by(GameRoster.human_id).all()

    # Aggregate goalie games played
    goalie_stats = session.query(
        GameRoster.human_id,
        func.count(func.distinct(Game.id)).label('games_goalie'),
        func.array_agg(func.distinct(Game.id)).label('goalie_game_ids')
    ).join(Game, GameRoster.game_id == Game.id).join(Division, Game.division_id == Division.id).filter(filter_condition, game_status_filter, GameRoster.role.ilike('G'), *human_filter).group_by(GameRoster.human_id).all()

    # Aggregate referee and scorekeeper games from Game table
    referee_stats = session.query(
        Game.referee_1_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_referee'),
        func.array_agg(func.distinct(Game.id)).label('referee_game_ids')
    ).join(Division, Game.division_id == Division.id).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.referee_1_id).all()

    referee_stats_2 = session.query(
        Game.referee_2_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_referee'),
        func.array_agg(func.distinct(Game.id)).label('referee_game_ids')
    ).join(Division, Game.division_id == Division.id).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.referee_2_id).all()

    scorekeeper_stats = session.query(
        Game.scorekeeper_id.label('human_id'),
        func.count(func.distinct(Game.id)).label('games_scorekeeper'),
        func.array_agg(func.distinct(Game.id)).label('scorekeeper_game_ids')
    ).join(Division, Game.division_id == Division.id).filter(filter_condition, game_status_filter, *human_filter).group_by(Game.scorekeeper_id).all()

    # Combine the results
    stats_dict = {}
    for stat in skater_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': 0,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': 0,
                'skater_game_ids': [],
                'goalie_game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': [],
                'first_game_id_skater': None,
                'last_game_id_skater': None,
                'first_game_id_goalie': None,
                'last_game_id_goalie': None,
                'first_game_id_referee': None,
                'last_game_id_referee': None,
                'first_game_id_scorekeeper': None,
                'last_game_id_scorekeeper': None
            }
        stats_dict[key]['games_total'] += stat.games_skater
        stats_dict[key]['games_skater'] += stat.games_skater
        stats_dict[key]['skater_game_ids'].extend(stat.skater_game_ids)

    for stat in goalie_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': 0,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': 0,
                'skater_game_ids': [],
                'goalie_game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': [],
                'first_game_id_skater': None,
                'last_game_id_skater': None,
                'first_game_id_goalie': None,
                'last_game_id_goalie': None,
                'first_game_id_referee': None,
                'last_game_id_referee': None,
                'first_game_id_scorekeeper': None,
                'last_game_id_scorekeeper': None
            }
        stats_dict[key]['games_total'] += stat.games_goalie
        stats_dict[key]['games_goalie'] += stat.games_goalie
        stats_dict[key]['goalie_game_ids'].extend(stat.goalie_game_ids)

    for stat in referee_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': 0,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': 0,
                'skater_game_ids': [],
                'goalie_game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': [],
                'first_game_id_skater': None,
                'last_game_id_skater': None,
                'first_game_id_goalie': None,
                'last_game_id_goalie': None,
                'first_game_id_referee': None,
                'last_game_id_referee': None,
                'first_game_id_scorekeeper': None,
                'last_game_id_scorekeeper': None
            }
        stats_dict[key]['games_total'] += stat.games_referee
        stats_dict[key]['games_referee'] += stat.games_referee
        stats_dict[key]['referee_game_ids'].extend(stat.referee_game_ids)

    for stat in referee_stats_2:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': 0,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': 0,
                'skater_game_ids': [],
                'goalie_game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': [],
                'first_game_id_skater': None,
                'last_game_id_skater': None,
                'first_game_id_goalie': None,
                'last_game_id_goalie': None,
                'first_game_id_referee': None,
                'last_game_id_referee': None,
                'first_game_id_scorekeeper': None,
                'last_game_id_scorekeeper': None
            }
        stats_dict[key]['games_total'] += stat.games_referee
        stats_dict[key]['games_referee'] += stat.games_referee
        stats_dict[key]['referee_game_ids'].extend(stat.referee_game_ids)

    for stat in scorekeeper_stats:
        if stat.human_id in human_ids_to_filter:
            continue
        key = (aggregation_id, stat.human_id)
        if key not in stats_dict:
            stats_dict[key] = {
                'games_total': 0,
                'games_skater': 0,
                'games_goalie': 0,
                'games_referee': 0,
                'games_scorekeeper': 0,
                'skater_game_ids': [],
                'goalie_game_ids': [],
                'referee_game_ids': [],
                'scorekeeper_game_ids': [],
                'first_game_id_skater': None,
                'last_game_id_skater': None,
                'first_game_id_goalie': None,
                'last_game_id_goalie': None,
                'first_game_id_referee': None,
                'last_game_id_referee': None,
                'first_game_id_scorekeeper': None,
                'last_game_id_scorekeeper': None
            }
        stats_dict[key]['games_total'] += stat.games_scorekeeper
        stats_dict[key]['games_scorekeeper'] += stat.games_scorekeeper
        stats_dict[key]['scorekeeper_game_ids'].extend(stat.scorekeeper_game_ids)

    # Ensure all keys have valid human_id values
    stats_dict = {key: value for key, value in stats_dict.items() if key[1] is not None}

    # Calculate total_in_rank
    total_in_rank = len(stats_dict)

    # Calculate number of items in rank per role
    skaters_in_rank = len([stat for stat in stats_dict.values() if stat['games_skater'] > 0])
    goalies_in_rank = len([stat for stat in stats_dict.values() if stat['games_goalie'] > 0])
    referees_in_rank = len([stat for stat in stats_dict.values() if stat['games_referee'] > 0])
    scorekeepers_in_rank = len([stat for stat in stats_dict.values() if stat['games_scorekeeper'] > 0])

    # Filter out humans with less than min_games
    stats_dict = {key: value for key, value in stats_dict.items() if value['games_total'] >= min_games}

    # Assign ranks
    assign_ranks(stats_dict, 'games_total')
    assign_ranks(stats_dict, 'games_skater')
    assign_ranks(stats_dict, 'games_goalie')
    assign_ranks(stats_dict, 'games_referee')
    assign_ranks(stats_dict, 'games_scorekeeper')

    # Populate first_game_id and last_game_id for each role
    for key, stat in stats_dict.items():
        all_game_ids = stat['skater_game_ids'] + stat['goalie_game_ids'] + stat['referee_game_ids'] + stat['scorekeeper_game_ids']
        if all_game_ids:
            first_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date, Game.time).first()
            last_game = session.query(Game).filter(Game.id.in_(all_game_ids)).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id'] = first_game.id if first_game else None
            stat['last_game_id'] = last_game.id if last_game else None

        if stat['skater_game_ids']:
            first_game_skater = session.query(Game).filter(Game.id.in_(stat['skater_game_ids'])).order_by(Game.date, Game.time).first()
            last_game_skater = session.query(Game).filter(Game.id.in_(stat['skater_game_ids'])).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id_skater'] = first_game_skater.id if first_game_skater else None
            stat['last_game_id_skater'] = last_game_skater.id if last_game_skater else None

        if stat['goalie_game_ids']:
            first_game_goalie = session.query(Game).filter(Game.id.in_(stat['goalie_game_ids'])).order_by(Game.date, Game.time).first()
            last_game_goalie = session.query(Game).filter(Game.id.in_(stat['goalie_game_ids'])).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id_goalie'] = first_game_goalie.id if first_game_goalie else None
            stat['last_game_id_goalie'] = last_game_goalie.id if last_game_goalie else None

        if stat['referee_game_ids']:
            first_game_referee = session.query(Game).filter(Game.id.in_(stat['referee_game_ids'])).order_by(Game.date, Game.time).first()
            last_game_referee = session.query(Game).filter(Game.id.in_(stat['referee_game_ids'])).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id_referee'] = first_game_referee.id if first_game_referee else None
            stat['last_game_id_referee'] = last_game_referee.id if last_game_referee else None

        if stat['scorekeeper_game_ids']:
            first_game_scorekeeper = session.query(Game).filter(Game.id.in_(stat['scorekeeper_game_ids'])).order_by(Game.date, Game.time).first()
            last_game_scorekeeper = session.query(Game).filter(Game.id.in_(stat['scorekeeper_game_ids'])).order_by(Game.date.desc(), Game.time.desc()).first()
            stat['first_game_id_scorekeeper'] = first_game_scorekeeper.id if first_game_scorekeeper else None
            stat['last_game_id_scorekeeper'] = last_game_scorekeeper.id if last_game_scorekeeper else None

    # Insert aggregated stats into the appropriate table with progress output
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        if human_id_filter and human_id != human_id_filter:
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
            skaters_in_rank=skaters_in_rank,
            goalies_in_rank=goalies_in_rank,
            referees_in_rank=referees_in_rank,
            scorekeepers_in_rank=scorekeepers_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id'],
            first_game_id_skater=stat['first_game_id_skater'],
            last_game_id_skater=stat['last_game_id_skater'],
            first_game_id_goalie=stat['first_game_id_goalie'],
            last_game_id_goalie=stat['last_game_id_goalie'],
            first_game_id_referee=stat['first_game_id_referee'],
            last_game_id_referee=stat['last_game_id_referee'],
            first_game_id_scorekeeper=stat['first_game_id_scorekeeper'],
            last_game_id_scorekeeper=stat['last_game_id_scorekeeper']
        )
        session.add(human_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
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
        'skaters_in_rank': skaters_in_rank,
        'goalies_in_rank': goalies_in_rank,
        'referees_in_rank': referees_in_rank,
        'scorekeepers_in_rank': scorekeepers_in_rank,
        'first_game_id': None,
        'last_game_id': None,
        'first_game_id_skater': None,
        'last_game_id_skater': None,
        'first_game_id_goalie': None,
        'last_game_id_goalie': None,
        'first_game_id_referee': None,
        'last_game_id_referee': None,
        'first_game_id_scorekeeper': None,
        'last_game_id_scorekeeper': None
    }

    # Populate first_game_id and last_game_id for overall stats
    all_game_ids = [game_id for stat in stats_dict.values() for game_id in stat['skater_game_ids'] + stat['goalie_game_ids'] + stat['referee_game_ids'] + stat['scorekeeper_game_ids']]
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
        skaters_in_rank=overall_stats['skaters_in_rank'],
        goalies_in_rank=overall_stats['goalies_in_rank'],
        referees_in_rank=overall_stats['referees_in_rank'],
        scorekeepers_in_rank=overall_stats['scorekeepers_in_rank'],
        first_game_id=overall_stats['first_game_id'],
        last_game_id=overall_stats['last_game_id'],
        first_game_id_skater=overall_stats['first_game_id_skater'],
        last_game_id_skater=overall_stats['last_game_id_skater'],
        first_game_id_goalie=overall_stats['first_game_id_goalie'],
        last_game_id_goalie=overall_stats['last_game_id_goalie'],
        first_game_id_referee=overall_stats['first_game_id_referee'],
        last_game_id_referee=overall_stats['last_game_id_referee'],
        first_game_id_scorekeeper=overall_stats['first_game_id_scorekeeper'],
        last_game_id_scorekeeper=overall_stats['last_game_id_scorekeeper']
    )
    session.add(overall_human_stat)
    session.commit()

def run_aggregate_human_stats():
    session = create_session("boss")
    human_id_to_debug = None

    # Aggregate by Org and Division inside Org
    org_ids = session.query(Organization.id).all()
    org_ids = [org_id[0] for org_id in org_ids]

    for org_id in [-1]:#org_ids:
        division_ids = get_all_division_ids_for_org(session, org_id)
        print(f"Aggregating human stats for {len(division_ids)} divisions in org_id {org_id}...")
        total_divisions = len(division_ids)
        processed_divisions = 0
        for division_id in division_ids:
            aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug)
            aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug, aggregation_window='Weekly')
            aggregate_human_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug, aggregation_window='Daily')
            processed_divisions += 1
            if human_id_to_debug is None:
                print(f"\rProcessed {processed_divisions}/{total_divisions} divisions ({(processed_divisions/total_divisions)*100:.2f}%)", end="")
        print("")
        aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug)
        aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug, aggregation_window='Weekly')
        aggregate_human_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug, aggregation_window='Daily')
        
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
        aggregate_human_stats(session, aggregation_type='level', aggregation_id=level_id, names_to_filter_out=not_human_names, human_id_filter=human_id_to_debug)

if __name__ == "__main__":
    run_aggregate_human_stats()
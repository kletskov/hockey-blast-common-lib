import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import sqlalchemy

from hockey_blast_common_lib.models import Game, Organization, Division, ScorekeeperSaveQuality
from hockey_blast_common_lib.stats_models import OrgStatsScorekeeper, DivisionStatsScorekeeper, OrgStatsWeeklyScorekeeper, OrgStatsDailyScorekeeper, DivisionStatsWeeklyScorekeeper, DivisionStatsDailyScorekeeper
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func, case
from hockey_blast_common_lib.options import parse_args, MIN_GAMES_FOR_ORG_STATS, MIN_GAMES_FOR_DIVISION_STATS, not_human_names
from hockey_blast_common_lib.utils import get_org_id_from_alias, get_human_ids_by_names, get_division_ids_for_last_season_in_all_leagues, get_all_division_ids_for_org
from hockey_blast_common_lib.utils import assign_ranks
from hockey_blast_common_lib.utils import get_start_datetime
from hockey_blast_common_lib.stats_utils import ALL_ORGS_ID
from hockey_blast_common_lib.progress_utils import create_progress_tracker

def calculate_quality_score(avg_max_saves_5sec, avg_max_saves_20sec, peak_max_saves_5sec, peak_max_saves_20sec):
    """
    Calculate a quality score based on excessive clicking patterns.
    Lower scores are better (less problematic clicking).

    Logic:
    - Penalize high average clicking rates in windows
    - Heavily penalize peak clicking incidents
    - Score ranges from 0 (perfect) to higher values (problematic)
    """
    # Convert to float to handle Decimal types from database
    avg_max_saves_5sec = float(avg_max_saves_5sec or 0.0)
    avg_max_saves_20sec = float(avg_max_saves_20sec or 0.0)
    peak_max_saves_5sec = float(peak_max_saves_5sec or 0)
    peak_max_saves_20sec = float(peak_max_saves_20sec or 0)

    if avg_max_saves_5sec == 0 and avg_max_saves_20sec == 0:
        return 0.0

    # Weight factors (can be tuned based on analysis)
    avg_5sec_weight = 2.0    # Average clicking in 5sec windows
    avg_20sec_weight = 1.0   # Average clicking in 20sec windows
    peak_5sec_weight = 5.0   # Peak 5sec incidents are heavily penalized
    peak_20sec_weight = 3.0  # Peak 20sec incidents are moderately penalized

    score = (
        (avg_max_saves_5sec * avg_5sec_weight) +
        (avg_max_saves_20sec * avg_20sec_weight) +
        (peak_max_saves_5sec * peak_5sec_weight) +
        (peak_max_saves_20sec * peak_20sec_weight)
    )

    return round(score, 2)

def aggregate_scorekeeper_stats(session, aggregation_type, aggregation_id, names_to_filter_out, aggregation_window=None):
    human_ids_to_filter = get_human_ids_by_names(session, names_to_filter_out)

    if aggregation_type == 'org':
        if aggregation_id == ALL_ORGS_ID:
            aggregation_name = "All Orgs"
            filter_condition = sqlalchemy.true()  # No filter for organization
        else:
            aggregation_name = session.query(Organization).filter(Organization.id == aggregation_id).first().organization_name
            filter_condition = Game.org_id == aggregation_id
        print(f"Aggregating scorekeeper stats for {aggregation_name} with window {aggregation_window}...")
        if aggregation_window == 'Daily':
            StatsModel = OrgStatsDailyScorekeeper
        elif aggregation_window == 'Weekly':
            StatsModel = OrgStatsWeeklyScorekeeper
        else:
            StatsModel = OrgStatsScorekeeper
        min_games = MIN_GAMES_FOR_ORG_STATS
    elif aggregation_type == 'division':
        if aggregation_window == 'Daily':
            StatsModel = DivisionStatsDailyScorekeeper
        elif aggregation_window == 'Weekly':
            StatsModel = DivisionStatsWeeklyScorekeeper
        else:
            StatsModel = DivisionStatsScorekeeper
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        filter_condition = Game.division_id == aggregation_id
    else:
        raise ValueError("Invalid aggregation type")

    # Delete existing items from the stats table
    session.query(StatsModel).filter(StatsModel.aggregation_id == aggregation_id).delete()
    session.commit()

    # Apply aggregation window filter
    if aggregation_window:
        last_game_datetime_str = session.query(func.max(func.concat(Game.date, ' ', Game.time))).filter(filter_condition, Game.status.like('Final%')).scalar()
        start_datetime = get_start_datetime(last_game_datetime_str, aggregation_window)
        if start_datetime:
            game_window_filter = func.cast(func.concat(Game.date, ' ', Game.time), sqlalchemy.types.TIMESTAMP).between(start_datetime, last_game_datetime_str)
            filter_condition = filter_condition & game_window_filter
        else:
            return

    if aggregation_type == 'division':
        filter_condition = filter_condition & (Division.id == Game.division_id)

    # Aggregate scorekeeper quality data for each human
    scorekeeper_quality_stats = session.query(
        ScorekeeperSaveQuality.scorekeeper_id.label('human_id'),
        func.count(ScorekeeperSaveQuality.game_id).label('games_recorded'),
        func.sum(ScorekeeperSaveQuality.total_saves_recorded).label('total_saves_recorded'),
        func.avg(ScorekeeperSaveQuality.total_saves_recorded).label('avg_saves_per_game'),
        func.avg(ScorekeeperSaveQuality.max_saves_per_5sec).label('avg_max_saves_per_5sec'),
        func.avg(ScorekeeperSaveQuality.max_saves_per_20sec).label('avg_max_saves_per_20sec'),
        func.max(ScorekeeperSaveQuality.max_saves_per_5sec).label('peak_max_saves_per_5sec'),
        func.max(ScorekeeperSaveQuality.max_saves_per_20sec).label('peak_max_saves_per_20sec'),
        func.array_agg(ScorekeeperSaveQuality.game_id).label('game_ids')
    ).join(Game, Game.id == ScorekeeperSaveQuality.game_id)

    if aggregation_type == 'division':
        scorekeeper_quality_stats = scorekeeper_quality_stats.join(Division, Game.division_id == Division.id)

    scorekeeper_quality_stats = scorekeeper_quality_stats.filter(filter_condition).group_by(ScorekeeperSaveQuality.scorekeeper_id).all()

    # Combine the results
    stats_dict = {}
    for stat in scorekeeper_quality_stats:
        if stat.human_id in human_ids_to_filter or stat.human_id is None:
            continue
        key = (aggregation_id, stat.human_id)

        # Calculate quality score
        quality_score = calculate_quality_score(
            stat.avg_max_saves_per_5sec or 0.0,
            stat.avg_max_saves_per_20sec or 0.0,
            stat.peak_max_saves_per_5sec or 0,
            stat.peak_max_saves_per_20sec or 0
        )

        stats_dict[key] = {
            'games_recorded': stat.games_recorded,
            'sog_given': stat.total_saves_recorded,  # Legacy field name mapping
            'sog_per_game': stat.avg_saves_per_game or 0.0,  # Legacy field name mapping
            'total_saves_recorded': stat.total_saves_recorded,
            'avg_saves_per_game': stat.avg_saves_per_game or 0.0,
            'avg_max_saves_per_5sec': stat.avg_max_saves_per_5sec or 0.0,
            'avg_max_saves_per_20sec': stat.avg_max_saves_per_20sec or 0.0,
            'peak_max_saves_per_5sec': stat.peak_max_saves_per_5sec or 0,
            'peak_max_saves_per_20sec': stat.peak_max_saves_per_20sec or 0,
            'quality_score': quality_score,
            'game_ids': stat.game_ids,
            'first_game_id': None,
            'last_game_id': None
        }

    # Filter out entries with games_recorded less than min_games
    stats_dict = {key: value for key, value in stats_dict.items() if value['games_recorded'] >= min_games}

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

    # Assign ranks - note: for quality metrics, lower values are better (reverse_rank=True for avg and peak clicking)
    assign_ranks(stats_dict, 'games_recorded')
    assign_ranks(stats_dict, 'sog_given')  # Legacy field
    assign_ranks(stats_dict, 'sog_per_game')  # Legacy field
    assign_ranks(stats_dict, 'total_saves_recorded')
    assign_ranks(stats_dict, 'avg_saves_per_game')
    assign_ranks(stats_dict, 'avg_max_saves_per_5sec', reverse_rank=True)  # Lower is better (less clicking)
    assign_ranks(stats_dict, 'avg_max_saves_per_20sec', reverse_rank=True)  # Lower is better
    assign_ranks(stats_dict, 'peak_max_saves_per_5sec', reverse_rank=True)  # Lower is better
    assign_ranks(stats_dict, 'peak_max_saves_per_20sec', reverse_rank=True)  # Lower is better
    assign_ranks(stats_dict, 'quality_score', reverse_rank=True)  # Lower is better (less problematic)

    # Insert aggregated stats into the appropriate table with progress output
    total_items = len(stats_dict)
    batch_size = 1000
    for i, (key, stat) in enumerate(stats_dict.items(), 1):
        aggregation_id, human_id = key
        scorekeeper_stat = StatsModel(
            aggregation_id=aggregation_id,
            human_id=human_id,
            games_recorded=stat['games_recorded'],
            sog_given=stat['sog_given'],  # Legacy field mapping
            sog_per_game=stat['sog_per_game'],  # Legacy field mapping
            total_saves_recorded=stat['total_saves_recorded'],
            total_saves_recorded_rank=stat['total_saves_recorded_rank'],
            avg_saves_per_game=stat['avg_saves_per_game'],
            avg_saves_per_game_rank=stat['avg_saves_per_game_rank'],
            avg_max_saves_per_5sec=stat['avg_max_saves_per_5sec'],
            avg_max_saves_per_5sec_rank=stat['avg_max_saves_per_5sec_rank'],
            avg_max_saves_per_20sec=stat['avg_max_saves_per_20sec'],
            avg_max_saves_per_20sec_rank=stat['avg_max_saves_per_20sec_rank'],
            peak_max_saves_per_5sec=stat['peak_max_saves_per_5sec'],
            peak_max_saves_per_5sec_rank=stat['peak_max_saves_per_5sec_rank'],
            peak_max_saves_per_20sec=stat['peak_max_saves_per_20sec'],
            peak_max_saves_per_20sec_rank=stat['peak_max_saves_per_20sec_rank'],
            quality_score=stat['quality_score'],
            quality_score_rank=stat['quality_score_rank'],
            games_recorded_rank=stat['games_recorded_rank'],
            sog_given_rank=stat['sog_given_rank'],  # Legacy field
            sog_per_game_rank=stat['sog_per_game_rank'],  # Legacy field
            total_in_rank=total_in_rank,
            first_game_id=stat['first_game_id'],
            last_game_id=stat['last_game_id']
        )
        session.add(scorekeeper_stat)
        # Commit in batches
        if i % batch_size == 0:
            session.commit()
    session.commit()

def run_aggregate_scorekeeper_stats():
    session = create_session("boss")
    human_id_to_debug = None

    # Get all org_id present in the Organization table
    org_ids = session.query(Organization.id).all()
    org_ids = [org_id[0] for org_id in org_ids]

    for org_id in org_ids:
        division_ids = get_all_division_ids_for_org(session, org_id)
        org_name = session.query(Organization.organization_name).filter(Organization.id == org_id).scalar() or f"org_id {org_id}"

        if human_id_to_debug is None and division_ids:
            # Process divisions with progress tracking
            progress = create_progress_tracker(len(division_ids), f"Processing {len(division_ids)} divisions for {org_name}")
            for i, division_id in enumerate(division_ids):
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names)
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
                progress.update(i + 1)
        else:
            # Debug mode or no divisions - process without progress tracking
            for division_id in division_ids:
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names)
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
                aggregate_scorekeeper_stats(session, aggregation_type='division', aggregation_id=division_id, names_to_filter_out=not_human_names, aggregation_window='Daily')

        # Process org-level stats with progress tracking
        if human_id_to_debug is None:
            org_progress = create_progress_tracker(3, f"Processing org-level stats for {org_name}")
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names)
            org_progress.update(1)
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
            org_progress.update(2)
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Daily')
            org_progress.update(3)
        else:
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names)
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Weekly')
            aggregate_scorekeeper_stats(session, aggregation_type='org', aggregation_id=org_id, names_to_filter_out=not_human_names, aggregation_window='Daily')

if __name__ == "__main__":
    run_aggregate_scorekeeper_stats()
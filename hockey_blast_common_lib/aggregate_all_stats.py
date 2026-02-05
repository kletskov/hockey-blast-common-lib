import os
import sys
from datetime import datetime

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.aggregate_goalie_stats import run_aggregate_goalie_stats
from hockey_blast_common_lib.aggregate_human_stats import run_aggregate_human_stats
from hockey_blast_common_lib.aggregate_referee_stats import run_aggregate_referee_stats
from hockey_blast_common_lib.aggregate_scorekeeper_stats import (
    run_aggregate_scorekeeper_stats,
)
from hockey_blast_common_lib.aggregate_skater_stats import run_aggregate_skater_stats
from hockey_blast_common_lib.aggregate_team_goalie_stats import (
    run_aggregate_team_goalie_stats,
)
from hockey_blast_common_lib.aggregate_team_skater_stats import (
    run_aggregate_team_skater_stats,
)
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy import text


def populate_human_games_fresh(session):
    """
    Populate human_games table from scratch before stats aggregation.
    Ensures it's always in sync with GameRoster.
    """
    print("\n" + "=" * 80, flush=True)
    print("POPULATING HUMAN_GAMES TABLE FROM SCRATCH", flush=True)
    print("=" * 80, flush=True)

    start_time = datetime.now()

    # Truncate and repopulate in one transaction
    populate_query = text("""
        -- First, truncate the table
        TRUNCATE TABLE human_games;

        -- Then populate fresh from GameRoster
        INSERT INTO human_games (human_id, game_ids, games_count, last_updated_at, last_processed_games_count)
        SELECT
            gr.human_id,
            ARRAY_AGG(DISTINCT gr.game_id ORDER BY gr.game_id) as game_ids,
            COUNT(DISTINCT gr.game_id) as games_count,
            NOW() as last_updated_at,
            0 as last_processed_games_count
        FROM game_rosters gr
        JOIN games g ON gr.game_id = g.id
        WHERE g.status LIKE 'Final%' OR g.status = 'NOEVENTS'
        GROUP BY gr.human_id;
    """)

    session.execute(populate_query)
    session.commit()

    # Get statistics
    stats_query = text("""
        SELECT
            COUNT(*) as total_humans,
            SUM(games_count) as total_game_entries,
            AVG(games_count) as avg_games_per_human
        FROM human_games
    """)

    stats = session.execute(stats_query).fetchone()

    duration = (datetime.now() - start_time).total_seconds()

    print(f"✓ Populated {stats.total_humans:,} humans in {duration:.2f} seconds", flush=True)
    print(f"  Total game entries: {stats.total_game_entries:,}", flush=True)
    print(f"  Avg games per human: {stats.avg_games_per_human:.1f}", flush=True)
    print("=" * 80, flush=True)
    print()


if __name__ == "__main__":
    # Step 0: Populate human_games table fresh from GameRoster
    # This ensures it's always in sync before stats aggregation
    session = create_session("boss")
    try:
        populate_human_games_fresh(session)
    except Exception as e:
        print(f"ERROR: Failed to populate human_games: {e}", flush=True)
        # Continue anyway - stats will still work, just slower
    finally:
        session.close()

    print("Running aggregate_skater_stats...", flush=True)
    run_aggregate_skater_stats()
    print("Finished running aggregate_skater_stats\n")

    print("Running aggregate_goalie_stats...", flush=True)
    run_aggregate_goalie_stats()
    print("Finished running aggregate_goalie_stats\n")

    print("Running aggregate_referee_stats...", flush=True)
    run_aggregate_referee_stats()
    print("Finished running aggregate_referee_stats\n")

    print("Running aggregate_scorekeeper_stats...", flush=True)
    run_aggregate_scorekeeper_stats()
    print("Finished running aggregate_scorekeeper_stats\n")

    print("Running aggregate_human_stats...", flush=True)
    run_aggregate_human_stats()
    print("Finished running aggregate_human_stats\n")

    print("Running aggregate_team_skater_stats...", flush=True)
    run_aggregate_team_skater_stats()
    print("Finished running aggregate_team_skater_stats\n")

    print("Running aggregate_team_goalie_stats...", flush=True)
    run_aggregate_team_goalie_stats()
    print("Finished running aggregate_team_goalie_stats\n")

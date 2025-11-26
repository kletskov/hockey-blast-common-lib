import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Game, GameRoster, GoalieSaves, Human
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import GameStatsGoalie
from hockey_blast_common_lib.utils import get_non_human_ids

# Import status constants for game filtering
FINAL_STATUS = "Final"
FINAL_SO_STATUS = "Final(SO)"


def aggregate_game_stats_goalie(session, mode="full", human_id=None):
    """Aggregate per-game goalie statistics.

    Args:
        session: Database session
        mode: "full" to regenerate all records, "append" to process new games only
        human_id: Optional human_id to process only one goalie (for testing/debugging)

    The function stores individual game performance for each goalie with non-zero stats.
    Only games where the goalie faced at least one shot are saved.
    This sparse storage is optimized for RAG system queries.

    Uses Incognito Human sentinel record (game_id=-1) to track last processed timestamp
    for append mode with 1-day overlap to catch data corrections.

    Note: Uses GameStatsGoalie table but shares sentinel tracking with GameStatsSkater
    since both are per-game stats that should be processed together.
    """

    # Get Incognito Human for sentinel tracking (first_name="Incognito", middle_name="", last_name="Human")
    incognito_human = session.query(Human).filter_by(
        first_name="Incognito", middle_name="", last_name="Human"
    ).first()
    if not incognito_human:
        raise RuntimeError("Incognito Human not found in database - required for sentinel tracking")
    incognito_human_id = incognito_human.id

    non_human_ids = get_non_human_ids(session)

    # Add human_id to filter if specified
    if human_id:
        human = session.query(Human).filter_by(id=human_id).first()
        if not human:
            print(f"ERROR: Human ID {human_id} not found in database")
            return
        print(f"Limiting to human_id={human_id}: {human.first_name} {human.last_name}\n")

    print(f"\n{'='*80}")
    print(f"Aggregating per-game goalie statistics (mode: {mode})")
    print(f"{'='*80}\n")

    # Determine game filtering based on mode
    # Note: We check GameStatsSkater for sentinel since they're processed together
    if mode == "append":
        # Import here to avoid circular dependency
        from hockey_blast_common_lib.stats_models import GameStatsSkater

        # Query sentinel record for last processed timestamp
        sentinel = (
            session.query(GameStatsSkater)
            .filter(
                GameStatsSkater.human_id == incognito_human_id,
                GameStatsSkater.game_id == -1,
            )
            .first()
        )

        if sentinel:
            last_processed = datetime.combine(sentinel.game_date, sentinel.game_time)
            # Subtract 1 day for overlap to catch data corrections
            start_datetime = last_processed - timedelta(days=1)
            print(f"Append mode: Processing games after {start_datetime}")
            print(f"(1-day overlap from last processed: {last_processed})\n")

            # Delete records for games in the overlap window
            delete_count = (
                session.query(GameStatsGoalie)
                .filter(
                    GameStatsGoalie.human_id != incognito_human_id,
                    func.cast(
                        func.concat(GameStatsGoalie.game_date, " ", GameStatsGoalie.game_time),
                        func.TIMESTAMP,
                    ) >= start_datetime,
                )
                .delete(synchronize_session=False)
            )
            session.commit()
            print(f"Deleted {delete_count} existing records in overlap window\n")
        else:
            # No sentinel found, treat as full mode
            print("No sentinel record found - treating as full mode\n")
            mode = "full"
            start_datetime = None
    else:
        start_datetime = None

    if mode == "full":
        # Delete all existing records (no sentinel for goalie table)
        delete_count = session.query(GameStatsGoalie).delete(synchronize_session=False)
        session.commit()
        print(f"Full mode: Deleted {delete_count} existing records\n")

    # Build game filter for eligible games
    game_filter = Game.status.in_([FINAL_STATUS, FINAL_SO_STATUS])
    if mode == "append" and start_datetime:
        game_filter = and_(
            game_filter,
            func.cast(
                func.concat(Game.date, " ", Game.time),
                func.TIMESTAMP,
            ) >= start_datetime,
        )

    # Count total GoalieSaves records to process for progress tracking
    total_saves_records = (
        session.query(GoalieSaves)
        .join(Game, GoalieSaves.game_id == Game.id)
        .filter(game_filter)
        .count()
    )
    print(f"Processing {total_saves_records} goalie save records...\n")

    if total_saves_records == 0:
        print("No goalie records to process.\n")
        return

    # Query goalie saves joined with game metadata and roster
    # GoalieSaves already has per-game goalie data
    goalie_query = (
        session.query(
            GoalieSaves.game_id,
            GoalieSaves.goalie_id.label("human_id"),
            GameRoster.team_id,
            Game.org_id,
            Division.level_id,
            Game.date.label("game_date"),
            Game.time.label("game_time"),
            GoalieSaves.goals_allowed,
            GoalieSaves.shots_against.label("shots_faced"),
            GoalieSaves.saves_count.label("saves"),
        )
        .join(Game, GoalieSaves.game_id == Game.id)
        .join(Division, Game.division_id == Division.id)
        .join(
            GameRoster,
            and_(
                GameRoster.game_id == GoalieSaves.game_id,
                GameRoster.human_id == GoalieSaves.goalie_id,
            ),
        )
        .filter(
            game_filter,
            GoalieSaves.goalie_id.notin_(non_human_ids),  # Filter placeholder humans
        )
    )

    # Add human_id filter if specified
    if human_id:
        goalie_query = goalie_query.filter(GoalieSaves.goalie_id == human_id)

    goalie_records = goalie_query.all()

    print(f"Found {len(goalie_records)} goalie save records\n")

    # Filter to only non-zero stats (CRITICAL for RAG efficiency)
    # Only save records where goalie faced at least one shot
    print("Filtering to non-zero records...")
    nonzero_records = [record for record in goalie_records if record.shots_faced > 0]

    print(f"Filtered: {len(nonzero_records)} non-zero records (from {len(goalie_records)} total)\n")

    # Insert records in batches with progress tracking
    batch_size = 1000
    total_records = len(nonzero_records)

    if total_records == 0:
        print("No non-zero records to insert.\n")
    else:
        progress = create_progress_tracker(total_records, "Inserting per-game goalie stats")

        records_to_insert = []
        for i, record in enumerate(nonzero_records, 1):
            # Calculate save percentage
            if record.shots_faced > 0:
                save_percentage = (record.shots_faced - record.goals_allowed) / record.shots_faced
            else:
                save_percentage = 0.0

            game_stats_record = GameStatsGoalie(
                game_id=record.game_id,
                human_id=record.human_id,
                team_id=record.team_id,
                org_id=record.org_id,
                level_id=record.level_id,
                game_date=record.game_date,
                game_time=record.game_time,
                goals_allowed=record.goals_allowed,
                shots_faced=record.shots_faced,
                saves=record.saves,
                save_percentage=save_percentage,
                created_at=datetime.utcnow(),
            )

            records_to_insert.append(game_stats_record)

            # Commit in batches
            if i % batch_size == 0 or i == total_records:
                session.bulk_save_objects(records_to_insert)
                session.commit()
                records_to_insert = []
                progress.update(i)

        print("\nInsert complete.\n")

    print(f"\n{'='*80}")
    print("Per-game goalie statistics aggregation complete")
    print(f"{'='*80}\n")


def run_aggregate_game_stats_goalie():
    """Main entry point for goalie per-game aggregation."""
    import argparse

    parser = argparse.ArgumentParser(description="Aggregate per-game goalie statistics")
    parser.add_argument(
        "--mode",
        choices=["full", "append"],
        default="full",
        help="Aggregation mode: 'full' to regenerate all, 'append' to add new games only",
    )
    parser.add_argument(
        "--human-id",
        type=int,
        default=None,
        help="Optional: Limit processing to specific human_id (for testing)",
    )

    args = parser.parse_args()

    session = create_session("boss")
    aggregate_game_stats_goalie(session, mode=args.mode, human_id=args.human_id)


if __name__ == "__main__":
    run_aggregate_game_stats_goalie()

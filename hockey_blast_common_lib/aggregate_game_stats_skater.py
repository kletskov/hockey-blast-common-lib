import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from sqlalchemy import and_, case, func
from sqlalchemy.exc import IntegrityError

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Game, GameRoster, Goal, Human, Penalty
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import GameStatsSkater
from hockey_blast_common_lib.utils import get_non_human_ids

# Import status constants for game filtering
FINAL_STATUS = "Final"
FINAL_SO_STATUS = "Final(SO)"


def aggregate_game_stats_skater(session, mode="full", human_id=None):
    """Aggregate per-game skater statistics.

    Args:
        session: Database session
        mode: "full" to regenerate all records, "append" to process new games only
        human_id: Optional human_id to process only one player (for testing/debugging)

    The function stores individual game performance for each skater with non-zero stats.
    Only games where the player recorded at least one goal, assist, or penalty minute are saved.
    This sparse storage is optimized for RAG system queries.

    Uses Incognito Human sentinel record (game_id=-1) to track last processed timestamp
    for append mode with 1-day overlap to catch data corrections.
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
    print(f"Aggregating per-game skater statistics (mode: {mode})")
    print(f"{'='*80}\n")

    # Determine game filtering based on mode
    if mode == "append":
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
                session.query(GameStatsSkater)
                .filter(
                    GameStatsSkater.human_id != incognito_human_id,
                    func.cast(
                        func.concat(GameStatsSkater.game_date, " ", GameStatsSkater.game_time),
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
        # Delete all existing records except sentinel
        delete_count = (
            session.query(GameStatsSkater)
            .filter(GameStatsSkater.human_id != incognito_human_id)
            .delete(synchronize_session=False)
        )
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

    # Count total games to process for progress tracking
    total_games = session.query(Game).filter(game_filter).count()
    print(f"Processing {total_games} games...\n")

    if total_games == 0:
        print("No games to process.\n")
        return

    # Query game roster entries for skaters (exclude goalies)
    # Join with games to get metadata, filter by game status and date window
    roster_query = (
        session.query(
            GameRoster.game_id,
            GameRoster.human_id,
            GameRoster.team_id,
            Game.org_id,
            Division.level_id,
            Game.date.label("game_date"),
            Game.time.label("game_time"),
        )
        .join(Game, GameRoster.game_id == Game.id)
        .join(Division, Game.division_id == Division.id)
        .filter(
            ~GameRoster.role.ilike("g"),  # Exclude goalies
            GameRoster.human_id.notin_(non_human_ids),  # Filter placeholder humans
            game_filter,
        )
    )

    # Add human_id filter if specified
    if human_id:
        roster_query = roster_query.filter(GameRoster.human_id == human_id)

    roster_entries = roster_query.all()

    # Build dict of roster entries by (game_id, human_id) for fast lookup
    roster_dict = {}
    for entry in roster_entries:
        key = (entry.game_id, entry.human_id)
        roster_dict[key] = {
            "team_id": entry.team_id,
            "org_id": entry.org_id,
            "level_id": entry.level_id,
            "game_date": entry.game_date,
            "game_time": entry.game_time,
            "goals": 0,
            "assists": 0,
            "points": 0,
            "penalty_minutes": 0,
        }

    print(f"Found {len(roster_dict)} skater roster entries\n")

    # Query goals and count by scorer and assisters
    print("Aggregating goals and assists...")
    goals = (
        session.query(Goal)
        .join(Game, Goal.game_id == Game.id)
        .filter(game_filter)
        .all()
    )

    for goal in goals:
        # Count goal for scorer
        key = (goal.game_id, goal.goal_scorer_id)
        if key in roster_dict:
            roster_dict[key]["goals"] += 1
            roster_dict[key]["points"] += 1

        # Count assists
        if goal.assist_1_id:
            key = (goal.game_id, goal.assist_1_id)
            if key in roster_dict:
                roster_dict[key]["assists"] += 1
                roster_dict[key]["points"] += 1

        if goal.assist_2_id:
            key = (goal.game_id, goal.assist_2_id)
            if key in roster_dict:
                roster_dict[key]["assists"] += 1
                roster_dict[key]["points"] += 1

    print(f"Processed {len(goals)} goals\n")

    # Query penalties and aggregate by penalized player
    print("Aggregating penalties...")
    penalties = (
        session.query(Penalty)
        .join(Game, Penalty.game_id == Game.id)
        .filter(game_filter)
        .all()
    )

    for penalty in penalties:
        key = (penalty.game_id, penalty.penalized_player_id)
        if key in roster_dict:
            # Convert penalty minutes: "GM" (game misconduct) = 10, else parse integer
            if penalty.penalty_minutes and penalty.penalty_minutes.upper() == "GM":
                roster_dict[key]["penalty_minutes"] += 10
            else:
                try:
                    minutes = int(penalty.penalty_minutes) if penalty.penalty_minutes else 0
                    roster_dict[key]["penalty_minutes"] += minutes
                except (ValueError, TypeError):
                    # Log unconvertible values but don't crash
                    print(f"Warning: Could not convert penalty_minutes '{penalty.penalty_minutes}' for penalty {penalty.id}")

    print(f"Processed {len(penalties)} penalties\n")

    # Filter to only non-zero stats (CRITICAL for RAG efficiency)
    print("Filtering to non-zero records...")
    nonzero_dict = {
        key: stats
        for key, stats in roster_dict.items()
        if stats["goals"] > 0 or stats["assists"] > 0 or stats["penalty_minutes"] > 0
    }

    print(f"Filtered: {len(nonzero_dict)} non-zero records (from {len(roster_dict)} total)\n")

    # Insert records in batches with progress tracking
    batch_size = 1000
    total_records = len(nonzero_dict)

    if total_records == 0:
        print("No non-zero records to insert.\n")
    else:
        progress = create_progress_tracker(total_records, "Inserting per-game skater stats")

        records_to_insert = []
        for i, (key, stats) in enumerate(nonzero_dict.items(), 1):
            game_id, human_id = key

            record = GameStatsSkater(
                game_id=game_id,
                human_id=human_id,
                team_id=stats["team_id"],
                org_id=stats["org_id"],
                level_id=stats["level_id"],
                game_date=stats["game_date"],
                game_time=stats["game_time"],
                goals=stats["goals"],
                assists=stats["assists"],
                points=stats["points"],
                penalty_minutes=stats["penalty_minutes"],
                created_at=datetime.utcnow(),
            )

            records_to_insert.append(record)

            # Commit in batches
            if i % batch_size == 0 or i == total_records:
                session.bulk_save_objects(records_to_insert)
                session.commit()
                records_to_insert = []
                progress.update(i)

        print("\nInsert complete.\n")

    # Update or create sentinel record with max game timestamp (skip if filtering by human_id)
    if not human_id:
        max_game = (
            session.query(
                Game.date.label("game_date"),
                Game.time.label("game_time"),
            )
            .filter(game_filter)
            .order_by(Game.date.desc(), Game.time.desc())
            .first()
        )

        if max_game:
            # Try to update existing sentinel
            sentinel = (
                session.query(GameStatsSkater)
                .filter(
                    GameStatsSkater.human_id == incognito_human_id,
                    GameStatsSkater.game_id == -1,
                )
                .first()
            )

            if sentinel:
                sentinel.game_date = max_game.game_date
                sentinel.game_time = max_game.game_time
                print(f"Updated sentinel record: {max_game.game_date} {max_game.game_time}")
            else:
                # Create new sentinel
                sentinel = GameStatsSkater(
                    game_id=-1,
                    human_id=incognito_human_id,
                    team_id=-1,  # Dummy value
                    org_id=-1,  # Dummy value
                    level_id=-1,  # Dummy value
                    game_date=max_game.game_date,
                    game_time=max_game.game_time,
                    goals=0,
                    assists=0,
                    points=0,
                    penalty_minutes=0,
                    created_at=datetime.utcnow(),
                )
                session.add(sentinel)
                print(f"Created sentinel record: {max_game.game_date} {max_game.game_time}")

            session.commit()
    else:
        print("Skipping sentinel record creation (human_id filter active)")

    print(f"\n{'='*80}")
    print("Per-game skater statistics aggregation complete")
    print(f"{'='*80}\n")


def run_aggregate_game_stats_skater():
    """Main entry point for skater per-game aggregation."""
    import argparse

    parser = argparse.ArgumentParser(description="Aggregate per-game skater statistics")
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
    aggregate_game_stats_skater(session, mode=args.mode, human_id=args.human_id)


if __name__ == "__main__":
    run_aggregate_game_stats_skater()

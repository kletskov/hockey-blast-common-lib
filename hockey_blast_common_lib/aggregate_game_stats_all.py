#!/usr/bin/env python3
"""
Orchestrator for per-game statistics aggregation.

This script provides a unified interface for running both skater and goalie
per-game statistics aggregation. It supports full and append modes and can
run aggregations for specific roles or all roles together.

Usage examples:
    # Full regeneration of all per-game stats
    python aggregate_game_stats_all.py --mode full --role all

    # Append new games for skaters only
    python aggregate_game_stats_all.py --mode append --role skater

    # Append new games for goalies only
    python aggregate_game_stats_all.py --mode append --role goalie

The script automatically manages sentinel record tracking across both stat types
to ensure consistent append mode behavior.
"""

import argparse
import os
import sys
from datetime import datetime

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.aggregate_game_stats_goalie import aggregate_game_stats_goalie
from hockey_blast_common_lib.aggregate_game_stats_skater import aggregate_game_stats_skater
from hockey_blast_common_lib.db_connection import create_session


def run_aggregation(mode="full", role="all", human_id=None):
    """Run per-game statistics aggregation.

    Args:
        mode: "full" to regenerate all records, "append" to process new games only
        role: "skater", "goalie", or "all" to specify which stats to aggregate
        human_id: Optional human_id to process only one player (for testing/debugging)
    """
    session = create_session("boss")

    start_time = datetime.now()
    print(f"\n{'='*80}")
    print(f"PER-GAME STATISTICS AGGREGATION")
    print(f"Mode: {mode.upper()}")
    print(f"Role: {role.upper()}")
    if human_id:
        print(f"Human ID Filter: {human_id}")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    # Run skater aggregation
    if role in ["skater", "all"]:
        try:
            aggregate_game_stats_skater(session, mode=mode, human_id=human_id)
        except Exception as e:
            print(f"\nERROR: Skater aggregation failed: {e}")
            import traceback
            traceback.print_exc()
            if role == "skater":
                sys.exit(1)
            # If running all, continue to goalie even if skater fails
            print("\nContinuing to goalie aggregation...\n")

    # Run goalie aggregation
    if role in ["goalie", "all"]:
        try:
            aggregate_game_stats_goalie(session, mode=mode, human_id=human_id)
        except Exception as e:
            print(f"\nERROR: Goalie aggregation failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n{'='*80}")
    print(f"AGGREGATION COMPLETE")
    print(f"Duration: {duration}")
    print(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Aggregate per-game statistics for skaters and goalies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full regeneration of all stats
  %(prog)s --mode full --role all

  # Append new games for skaters only
  %(prog)s --mode append --role skater

  # Append new games for goalies only
  %(prog)s --mode append --role goalie

Notes:
  - Full mode deletes and regenerates all records
  - Append mode uses sentinel tracking with 1-day overlap
  - Only saves non-zero records (RAG optimization)
  - Skater stats: saves games with goals, assists, or penalties
  - Goalie stats: saves games where goalie faced shots
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["full", "append"],
        default="full",
        help="Aggregation mode (default: full)",
    )

    parser.add_argument(
        "--role",
        choices=["skater", "goalie", "all"],
        default="all",
        help="Which role stats to aggregate (default: all)",
    )

    parser.add_argument(
        "--human-id",
        type=int,
        default=None,
        help="Optional: Limit processing to specific human_id (for testing)",
    )

    args = parser.parse_args()

    try:
        run_aggregation(mode=args.mode, role=args.role, human_id=args.human_id)
    except KeyboardInterrupt:
        print("\n\nAggregation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

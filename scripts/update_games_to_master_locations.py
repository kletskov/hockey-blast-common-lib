"""
Script to update all games to use master location IDs.

This script updates Game.location_id to point to the master location
for any games currently pointing to location variations.
"""

import sys
import os
from pathlib import Path

# Add the pipeline directory to path to access db_connection
pipeline_path = '/Users/pavelkletskov/hockey-blast-prod/hockey-blast-pipeline'
sys.path.insert(0, pipeline_path)

from hockey_blast_common_lib.models import Location, Game
from db_utils.db_connection import create_pipeline_session


def update_games_to_master_locations(org_alias='sharksice', dry_run=False):
    """Update all games to use master location IDs."""
    session = create_pipeline_session("boss")

    print(f"Updating games to use master locations for {org_alias}...")
    if dry_run:
        print("DRY RUN MODE - No changes will be committed\n")

    # Find all games that have a location pointing to a variation (not a master)
    games_to_update = session.query(Game).join(
        Location, Game.location_id == Location.id
    ).filter(
        Location.master_location_id != Location.id,
        Location.master_location_id.isnot(None)
    ).all()

    print(f"Found {len(games_to_update)} games to update\n")

    if len(games_to_update) == 0:
        print("No games need updating!")
        session.close()
        return

    # Group by current location for reporting
    location_stats = {}
    updated_count = 0

    for game in games_to_update:
        current_location = session.query(Location).filter(
            Location.id == game.location_id
        ).first()

        if not current_location or not current_location.master_location_id:
            continue

        master_id = current_location.master_location_id
        current_name = current_location.location_in_game_source

        # Track stats
        if current_name not in location_stats:
            location_stats[current_name] = {
                'current_id': current_location.id,
                'master_id': master_id,
                'count': 0
            }
        location_stats[current_name]['count'] += 1

        # Update the game
        if not dry_run:
            game.location_id = master_id
            updated_count += 1

    # Commit changes
    if not dry_run:
        session.commit()
        print(f"✓ Updated {updated_count} games\n")
    else:
        print(f"Would update {len(games_to_update)} games\n")

    # Print statistics
    print("Update summary by location variation:")
    print("-" * 80)

    for location_name, stats in sorted(location_stats.items()):
        master_location = session.query(Location).filter(
            Location.id == stats['master_id']
        ).first()
        master_name = master_location.location_in_game_source if master_location else "Unknown"

        print(f"\n  {location_name}")
        print(f"    ID {stats['current_id']} -> {stats['master_id']}")
        print(f"    Master: {master_name}")
        print(f"    Games affected: {stats['count']}")

    # Final verification
    if not dry_run:
        print("\n" + "="*80)
        print("Verification:")

        remaining = session.query(Game).join(
            Location, Game.location_id == Location.id
        ).filter(
            Location.master_location_id != Location.id,
            Location.master_location_id.isnot(None)
        ).count()

        if remaining == 0:
            print("✓ All games now point to master locations!")
        else:
            print(f"⚠ Warning: {remaining} games still point to variations")

    session.close()
    print("\n✓ Update complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Update games to use master location IDs')
    parser.add_argument('--org', default='sharksice', help='Organization alias (default: sharksice)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    update_games_to_master_locations(args.org, dry_run=args.dry_run)

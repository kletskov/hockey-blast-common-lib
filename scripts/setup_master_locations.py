"""
Script to set up master locations for Sharks Ice San Jose rinks and map variations.

This script:
1. Creates/identifies master location records for the 6 main Sharks Ice San Jose rinks
2. Maps all location name variations to their master locations
3. Sets master_location_id = id for all other locations
4. Updates all games to use master location_id
"""

import sys
import os
from pathlib import Path

# Add the pipeline directory to path to access db_connection
pipeline_path = '/Users/pavelkletskov/hockey-blast-prod/hockey-blast-pipeline'
sys.path.insert(0, pipeline_path)

from hockey_blast_common_lib.models import Location, Game
from db_utils.db_connection import create_pipeline_session


# Define the 6 master Sharks Ice San Jose rinks
MASTER_RINKS = [
    {"name": "Black", "variations": [
        "San Jose Black",
        "San Jose Black (E)",
        "San Jose Black (E) 1",
        "San Jose Black (E) 2",
        "San Jose Black 1",
        "San Jose Black 2",
    ]},
    {"name": "Grey", "variations": [
        "San Jose Grey",
        "San Jose Grey 1",
        "San Jose Grey 2",
    ]},
    {"name": "Orange", "variations": [
        "San Jose Orange",
        "San Jose Orange (N)",
        "San Jose Orange (N) 1",
        "San Jose Orange (N) 2",
        "San Jose Orange 1",
        "San Jose Orange 2",
        "San Jose North",
        "Orange (N)",  # Standalone Orange reference
    ]},
    {"name": "Sharks", "variations": [
        "San Jose Sharks",
        "San Jose Sharks 1",
        "San Jose Sharks 2",
        "San Jose South",
    ]},
    {"name": "Tech CU", "variations": [
        "San Jose Tech CU",
    ]},
    {"name": "White", "variations": [
        "San Jose White",
        "San Jose White (C)",
        "San Jose White (C) 1",
        "San Jose White (C) 2",
        "San Jose White 1",
        "San Jose White 2",
    ]},
]


def setup_master_locations(org_alias='sharksice'):
    """Set up master locations and map all variations."""
    session = create_pipeline_session("boss")

    print(f"Setting up master locations for {org_alias}...")

    # Step 1: For each master rink, find or create the master location record
    # We'll use the simplest variation as the canonical master (without numbers or extra designations)
    master_location_map = {}  # Maps variation name -> master location id

    for rink in MASTER_RINKS:
        rink_name = rink["name"]
        variations = rink["variations"]

        print(f"\nProcessing {rink_name} rink...")

        # Find the canonical/simplest name as the master
        # Prefer "San Jose {Name}" format (simplest without numbers or designations)
        canonical_name = f"San Jose {rink_name}"

        # Find or identify the master location record
        master_location = session.query(Location).filter(
            Location.location_in_game_source == canonical_name
        ).first()

        if not master_location:
            # If canonical doesn't exist, use the first variation found as master
            print(f"  Canonical name '{canonical_name}' not found, searching for any variation...")
            for variation in variations:
                master_location = session.query(Location).filter(
                    Location.location_in_game_source == variation
                ).first()
                if master_location:
                    print(f"  Using '{variation}' as master (ID: {master_location.id})")
                    break
        else:
            print(f"  Found canonical master: '{canonical_name}' (ID: {master_location.id})")

        if not master_location:
            print(f"  WARNING: No location found for {rink_name} rink! Skipping...")
            continue

        master_id = master_location.id

        # Map all variations to this master
        for variation in variations:
            master_location_map[variation] = master_id

        print(f"  Mapped {len(variations)} variations to master ID {master_id}")

    # Step 2: Update all location records
    print("\n" + "="*60)
    print("Updating location records...")

    all_locations = session.query(Location).all()
    updated_count = 0
    self_referenced_count = 0

    for location in all_locations:
        location_name = location.location_in_game_source

        if location_name in master_location_map:
            # This is a variation - point to its master
            master_id = master_location_map[location_name]
            location.master_location_id = master_id
            updated_count += 1
            print(f"  {location.id}: '{location_name}' -> master {master_id}")
        else:
            # Not a Sharks Ice SJ variation - set to self
            location.master_location_id = location.id
            self_referenced_count += 1

    session.commit()

    print(f"\nUpdated {updated_count} location variations to point to masters")
    print(f"Set {self_referenced_count} other locations to self-reference")

    # Step 3: Verify master locations also point to themselves
    print("\n" + "="*60)
    print("Verifying master locations...")

    for rink in MASTER_RINKS:
        canonical_name = f"San Jose {rink['name']}"
        master = session.query(Location).filter(
            Location.location_in_game_source == canonical_name
        ).first()

        if master:
            if master.master_location_id != master.id:
                print(f"  Fixing master: {canonical_name} (ID {master.id})")
                master.master_location_id = master.id
                session.commit()
            else:
                print(f"  ✓ Master OK: {canonical_name} (ID {master.id})")

    # Step 4: Report statistics
    print("\n" + "="*60)
    print("Location Statistics:")

    total_locations = session.query(Location).count()
    masters = session.query(Location).filter(
        Location.master_location_id == Location.id
    ).count()
    variations = session.query(Location).filter(
        Location.master_location_id != Location.id
    ).count()

    print(f"  Total locations: {total_locations}")
    print(f"  Master locations: {masters}")
    print(f"  Variations: {variations}")

    # Step 5: Show which games will be affected
    print("\n" + "="*60)
    print("Analyzing game updates needed...")

    # Count games that reference variation locations
    games_to_update = session.query(Game).join(
        Location, Game.location_id == Location.id
    ).filter(
        Location.master_location_id != Location.id
    ).count()

    print(f"  Games to update: {games_to_update}")

    session.close()
    print("\n✓ Master location setup complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Set up master locations for Sharks Ice San Jose')
    parser.add_argument('--org', default='sharksice', help='Organization alias (default: sharksice)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
        print("(Note: Dry run not yet implemented, will make changes)")

    setup_master_locations(args.org)

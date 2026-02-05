#!/usr/bin/env python3
"""
Test script to compare old vs new point streak calculation.
This validates that the batched version produces identical results.
"""

import os
import sys

# Add both common lib and pipeline to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
pipeline_root = os.path.join(os.path.dirname(project_root), "hockey-blast-pipeline")
sys.path.append(pipeline_root)

from hockey_blast_common_lib.models import Division, Game, GameRoster, Organization
from hockey_blast_common_lib.aggregate_skater_stats import (
    calculate_current_point_streak,
    calculate_all_point_streaks_batch
)
from sqlalchemy import func

# Use pipeline's db_connection for role-based access
try:
    from db_utils.db_connection import create_pipeline_session
    create_session = lambda role: create_pipeline_session(role)
except ImportError:
    # Fallback to common lib's session creation
    from hockey_blast_common_lib.db_connection import create_session


def test_single_division(session, division_id):
    """
    Test point streak calculation for a single division.
    Compares old (N queries) vs new (1 query) implementation.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing Division ID: {division_id}")
    print(f"{'=' * 80}")

    # Get division info
    division = session.query(Division).filter_by(id=division_id).first()
    if not division:
        print(f"❌ Division {division_id} not found")
        return False

    print(f"Division: {division.org_id} / League {division.league_number} / Season {division.season_number}")

    # Get all human_ids in this division (skaters only)
    human_ids = (
        session.query(func.distinct(GameRoster.human_id))
        .join(Game, GameRoster.game_id == Game.id)
        .join(Division, Game.division_id == Division.id)
        .filter(
            Division.id == division_id,
            ~GameRoster.role.ilike("g")  # Exclude goalies
        )
        .all()
    )
    human_ids = [h[0] for h in human_ids]

    print(f"Found {len(human_ids)} skaters in this division")

    if not human_ids:
        print("⚠️  No players found in division")
        return True

    # Test with a sample of players (to save time)
    sample_size = min(20, len(human_ids))
    test_human_ids = human_ids[:sample_size]

    print(f"\nTesting with {sample_size} players...")

    # Define filter condition for this division
    filter_condition = Division.id == division_id

    # Method 1: OLD - Call calculate_current_point_streak for each player
    print(f"\n1. OLD method (N queries): Testing {sample_size} players...")
    old_results = {}
    for human_id in test_human_ids:
        streak_length, avg_points = calculate_current_point_streak(
            session, human_id, filter_condition
        )
        old_results[human_id] = (streak_length, avg_points)
    print(f"   ✓ Calculated {len(old_results)} streaks using old method")

    # Method 2: NEW - Call calculate_all_point_streaks_batch once
    print(f"\n2. NEW method (1 query): Testing {sample_size} players...")
    new_results = calculate_all_point_streaks_batch(
        session, test_human_ids, filter_condition
    )
    print(f"   ✓ Calculated {len(new_results)} streaks using new method")

    # Compare results
    print(f"\n3. Comparing results...")
    mismatches = []
    for human_id in test_human_ids:
        old = old_results.get(human_id, (0, 0.0))
        new = new_results.get(human_id, (0, 0.0))

        if old != new:
            mismatches.append({
                'human_id': human_id,
                'old': old,
                'new': new
            })

    if mismatches:
        print(f"\n❌ FAILED: Found {len(mismatches)} mismatches!")
        for m in mismatches[:5]:  # Show first 5
            print(f"   Human {m['human_id']}: old={m['old']}, new={m['new']}")
        return False
    else:
        print(f"✓ SUCCESS: All {sample_size} players match perfectly!")
        # Show a few examples
        print(f"\nSample results:")
        for human_id in test_human_ids[:5]:
            streak = old_results[human_id]
            print(f"   Human {human_id}: streak={streak[0]} games, avg={streak[1]:.2f} ppg")
        return True


def test_multiple_divisions(session, org_id, count=5):
    """
    Test multiple divisions from an organization.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing {count} divisions from organization {org_id}")
    print(f"{'=' * 80}")

    # Get divisions
    divisions = (
        session.query(Division)
        .filter(Division.org_id == org_id)
        .order_by(Division.id.desc())
        .limit(count)
        .all()
    )

    if not divisions:
        print(f"❌ No divisions found for org {org_id}")
        return False

    print(f"Found {len(divisions)} divisions to test")

    success_count = 0
    for division in divisions:
        result = test_single_division(session, division.id)
        if result:
            success_count += 1

    print(f"\n{'=' * 80}")
    print(f"SUMMARY: {success_count}/{len(divisions)} divisions passed")
    print(f"{'=' * 80}")

    return success_count == len(divisions)


def main():
    """Main test function"""
    session = create_session("read_only")

    print("=" * 80)
    print("POINT STREAK BATCH CALCULATION TEST")
    print("=" * 80)
    print("This script validates that the new batched calculation")
    print("produces identical results to the old implementation.")
    print("=" * 80)

    # Test with different organizations
    # Organization 1 = CAHA, 2 = Sharks Ice (check your actual org_ids)

    # Test 1: Single division
    print("\n\n" + "=" * 80)
    print("TEST 1: Single Division (detailed)")
    print("=" * 80)

    # Get a recent division with data
    recent_division = (
        session.query(Division)
        .join(Game, Game.division_id == Division.id)
        .join(GameRoster, GameRoster.game_id == Game.id)
        .filter(Division.org_id == 1)  # CAHA
        .group_by(Division.id)
        .having(func.count(func.distinct(Game.id)) > 10)  # Has at least 10 games
        .order_by(Division.id.desc())
        .first()
    )

    if recent_division:
        test1_result = test_single_division(session, recent_division.id)
    else:
        print("❌ Could not find suitable test division")
        test1_result = False

    # Test 2: Multiple divisions
    print("\n\n" + "=" * 80)
    print("TEST 2: Multiple Divisions")
    print("=" * 80)
    test2_result = test_multiple_divisions(session, org_id=1, count=5)

    # Final summary
    print("\n\n" + "=" * 80)
    print("FINAL TEST RESULTS")
    print("=" * 80)
    print(f"Test 1 (Single Division): {'✓ PASS' if test1_result else '❌ FAIL'}")
    print(f"Test 2 (Multiple Divisions): {'✓ PASS' if test2_result else '❌ FAIL'}")
    print("=" * 80)

    if test1_result and test2_result:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("The batched implementation produces identical results.")
        print("Safe to deploy to production.")
        return 0
    else:
        print("\n❌❌❌ SOME TESTS FAILED! ❌❌❌")
        print("DO NOT deploy until all tests pass.")
        return 1

    session.close()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

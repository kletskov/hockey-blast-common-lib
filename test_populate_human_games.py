#!/usr/bin/env python3
"""
Quick test of populate_human_games_fresh() function
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hockey_blast_common_lib.aggregate_all_stats import populate_human_games_fresh
from hockey_blast_common_lib.db_connection import create_session

if __name__ == "__main__":
    print("Testing populate_human_games_fresh() function...\n")

    session = create_session("boss")
    try:
        populate_human_games_fresh(session)
        print("\n✓ Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

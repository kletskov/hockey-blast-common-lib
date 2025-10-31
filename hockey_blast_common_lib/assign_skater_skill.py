import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Human, Level
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import LevelStatsSkater


def calculate_skater_skill_value(session, level_stats):
    min_skill_value = float("inf")  # Start with infinity since we want the minimum

    for stat in level_stats:
        level = session.query(Level).filter(Level.id == stat.level_id).first()
        if not level or level.skill_value < 0:
            continue
        level_skill_value = level.skill_value

        # Fix critical bug: Invert rank ratios so better players (lower ranks) get higher skill values
        # Rank 1 (best) should get factor close to 1.0, worst rank should get factor close to 0.0
        if stat.total_in_rank > 1:
            ppg_skill_factor = 1 - (stat.points_per_game_rank - 1) / (
                stat.total_in_rank - 1
            )
        else:
            ppg_skill_factor = 1.0  # Only one player in level

        # Apply skill adjustment: range from 0.8 to 1.2 of level base skill
        # Since lower skill_value is better: Best player gets 0.8x (closer to better levels), worst gets 1.2x
        skill_adjustment = 1.3 - 0.2 * ppg_skill_factor
        skill_value = level_skill_value * skill_adjustment

        # Take the minimum skill value across all levels the player has played in (lower is better)
        min_skill_value = min(min_skill_value, skill_value)

    return min_skill_value if min_skill_value != float("inf") else 0


def assign_skater_skill_values():
    session = create_session("boss")

    humans = session.query(Human).all()
    total_humans = len(humans)

    # Create progress tracker
    progress = create_progress_tracker(total_humans, "Assigning skater skill values")

    batch_size = 1000
    updates_count = 0

    for i, human in enumerate(humans):
        level_stats = (
            session.query(LevelStatsSkater)
            .filter(LevelStatsSkater.human_id == human.id)
            .all()
        )
        if level_stats:
            skater_skill_value = calculate_skater_skill_value(session, level_stats)
            human.skater_skill_value = skater_skill_value
            updates_count += 1

        # Commit in batches
        if updates_count % batch_size == 0:
            session.commit()

        progress.update(i + 1)

    # Commit any remaining updates
    if updates_count % batch_size != 0:
        session.commit()

    print("Skater skill values have been assigned to all humans.")


if __name__ == "__main__":
    assign_skater_skill_values()

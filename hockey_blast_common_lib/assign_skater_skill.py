import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.models import Human, Level
from hockey_blast_common_lib.stats_models import LevelStatsSkater
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy.sql import func

def calculate_skater_skill_value(session, human_id, level_stats):
    max_skill_value = 0

    for stat in level_stats:
        level = session.query(Level).filter(Level.id == stat.level_id).first()
        if not level or level.skill_value < 0:
            continue
        level_skill_value = level.skill_value
        ppg_ratio = stat.points_per_game_rank / stat.total_in_rank
        games_played_ratio = stat.games_played_rank / stat.total_in_rank

        # Take the maximum of the two ratios
        skill_value = level_skill_value * max(ppg_ratio, games_played_ratio)
        max_skill_value = max(max_skill_value, skill_value)

    return max_skill_value

def assign_skater_skill_values():
    session = create_session("boss")

    humans = session.query(Human).all()
    total_humans = len(humans)
    processed_humans = 0

    for human in humans:
        level_stats = session.query(LevelStatsSkater).filter(LevelStatsSkater.human_id == human.id).all()
        if level_stats:
            skater_skill_value = calculate_skater_skill_value(session, human.id, level_stats)
            human.skater_skill_value = skater_skill_value
            session.commit()

        processed_humans += 1
        print(f"\rProcessed {processed_humans}/{total_humans} humans ({(processed_humans/total_humans)*100:.2f}%)", end="")

    print("\nSkater skill values have been assigned to all humans.")

if __name__ == "__main__":
    assign_skater_skill_values()

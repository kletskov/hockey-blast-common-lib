import sys
import os
from collections import defaultdict
import numpy as np

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.models import Level, Season
from hockey_blast_common_lib.stats_models import LevelsGraphEdge, LevelStatsSkater, SkillPropagationCorrelation
from hockey_blast_common_lib.db_connection import create_session
from sqlalchemy import func

import numpy as np

class Config:
    MIN_GAMES_PLAYED = 10
    MIN_PPG = 0.3
    MIN_HUMANS_FOR_EDGE = 5
    MAX_START_DATE_DIFF_MONTHS = 15
    MAX_PROPAGATION_SEQUENCE = 0
    MIN_CONNECTIONS_FOR_CORRELATION = 40
    MIN_CONNECTIONS_FOR_PROPAGATION = 3

    @staticmethod
    def discard_outliers(data, m=2):
        """
        Discard outliers from the data using the modified Z-score method.
        :param data: List of data points
        :param m: Threshold for the modified Z-score
        :return: List of data points with outliers removed
        """
        if len(data) == 0:
            return data
        median = np.median(data)
        diff = np.abs(data - median)
        med_abs_deviation = np.median(diff)
        if med_abs_deviation == 0:
            return data
        modified_z_score = 0.6745 * diff / med_abs_deviation
        return data[modified_z_score < m]


def build_levels_graph_edges():
    session = create_session("boss")

    # Delete all existing edges
    session.query(LevelsGraphEdge).delete()
    session.commit()

    # Query to get all level stats
    level_stats = session.query(LevelStatsSkater).all()

    # Dictionary to store stats by level and human
    level_human_stats = defaultdict(lambda: defaultdict(dict))

    for stat in level_stats:
        if stat.games_played >= Config.MIN_GAMES_PLAYED and stat.points_per_game >= Config.MIN_PPG:
            level_human_stats[stat.aggregation_id][stat.human_id] = {
                'games_played': stat.games_played,
                'points_per_game': stat.points_per_game
            }

    # Dictionary to store edges
    edges = {}

    # Build edges
    total_levels = len(level_human_stats)
    processed_levels = 0
    for from_level_id, from_humans in level_human_stats.items():
        from_level = session.query(Level).filter_by(id=from_level_id).first()
        from_season = session.query(Season).filter_by(id=from_level.season_id).first()
        for to_level_id, to_humans in level_human_stats.items():
            to_level = session.query(Level).filter_by(id=to_level_id).first()
            to_season = session.query(Season).filter_by(id=to_level.season_id).first()

            if from_level.skill_value >= to_level.skill_value:
                continue

            # TMP DEBUG HACK
            if from_level.skill_value != 10 and to_level.skill_value != 30:
                continue

            # Check if the start dates are within the allowed difference
            if abs((from_season.start_date - to_season.start_date).days) > Config.MAX_START_DATE_DIFF_MONTHS * 30:
                continue

            common_humans = set(from_humans.keys()) & set(to_humans.keys())
            n_connections = len(common_humans)

            if n_connections < Config.MIN_HUMANS_FOR_EDGE:
                continue

            ppg_ratios = []
            for human_id in common_humans:
                from_ppg = from_humans[human_id]['points_per_game']
                to_ppg = to_humans[human_id]['points_per_game']
                if from_level.skill_value == 10 and to_level.skill_value == 30:
                    print(f"Human {human_id} From PPG: {from_ppg}, To PPG: {to_ppg}")
                if from_ppg > 0 and to_ppg > 0:
                    ppg_ratios.append(to_ppg / from_ppg)

            if not ppg_ratios:
                continue

            # Discard outliers
            ppg_ratios = Config.discard_outliers(np.array(ppg_ratios))

            if len(ppg_ratios) == 0:
                continue

            avg_ppg_ratio = float(sum(ppg_ratios) / len(ppg_ratios))
            if avg_ppg_ratio < 1.0:
                avg_ppg_ratio = 1 / avg_ppg_ratio
                from_level_id, to_level_id = to_level_id, from_level_id

            edge = LevelsGraphEdge(
                from_level_id=from_level_id,
                to_level_id=to_level_id,
                n_connections=n_connections,
                ppg_ratio=avg_ppg_ratio
            )
            edges[(from_level_id, to_level_id)] = edge

        processed_levels += 1
        print(f"\rProcessed {processed_levels}/{total_levels} levels ({(processed_levels/total_levels)*100:.2f}%)", end="")

    # Insert edges into the database
    for edge in edges.values():
        session.add(edge)
    session.commit()

    print("\nLevels graph edges have been populated into the database.")

def propagate_skill_levels(propagation_sequence):
    session = create_session("boss")

    if propagation_sequence == 0:
        # Delete all existing correlation data
        session.query(SkillPropagationCorrelation).delete()
        session.commit()

        # Build and save the correlation data
        levels = session.query(Level).filter(Level.skill_propagation_sequence == 0).all()
        level_ids = {level.id for level in levels}
        correlation_data = defaultdict(list)

        for level in levels:
            if level.skill_value == -1:
                continue

            edges = session.query(LevelsGraphEdge).filter(
                (LevelsGraphEdge.from_level_id == level.id) |
                (LevelsGraphEdge.to_level_id == level.id)
            ).all()

            for edge in edges:
                if edge.n_connections < Config.MIN_CONNECTIONS_FOR_CORRELATION:
                    continue

                if edge.from_level_id == level.id:
                    target_level_id = edge.to_level_id
                    ppg_ratio = edge.ppg_ratio
                else:
                    target_level_id = edge.from_level_id
                    ppg_ratio = 1 / edge.ppg_ratio

                if target_level_id not in level_ids:
                    continue

                target_level = session.query(Level).filter_by(id=target_level_id).first()
                if target_level:
                    skill_value_from = level.skill_value
                    skill_value_to = target_level.skill_value

                    # Since we go over all levels in the sequence 0, we will see each edge twice
                    # This condition eliminates duplicates
                    if skill_value_from >= skill_value_to:
                        continue

                    # Debug prints
                    print(f"From Skill  {level.skill_value} to {target_level.skill_value} ratio: {ppg_ratio}")

                    correlation_data[(skill_value_from, skill_value_to)].append(
                        ppg_ratio
                    )

        # Save correlation data to the database
        for (skill_value_from, skill_value_to), ppg_ratios in correlation_data.items():
            ppg_ratios = Config.discard_outliers(np.array(ppg_ratios))
            if len(ppg_ratios) > 0:
                avg_ppg_ratio = float(sum(ppg_ratios) / len(ppg_ratios))
                correlation = SkillPropagationCorrelation(
                    skill_value_from=skill_value_from,
                    skill_value_to=skill_value_to,
                    ppg_ratio=avg_ppg_ratio
                )
                session.add(correlation)
                session.commit()

    return
    # Propagate skill levels
    levels = session.query(Level).filter(Level.skill_propagation_sequence == propagation_sequence).all()
    suggested_skill_values = defaultdict(list)

    for level in levels:
        edges = session.query(LevelsGraphEdge).filter(
            (LevelsGraphEdge.from_level_id == level.id) |
            (LevelsGraphEdge.to_level_id == level.id)
        ).all()

        for edge in edges:
            if edge.n_connections < Config.MIN_CONNECTIONS_FOR_PROPAGATION:
                continue

            if edge.from_level_id == level.id:
                target_level_id = edge.to_level_id
                ppg_ratio = edge.ppg_ratio
            else:
                target_level_id = edge.from_level_id
                ppg_ratio = 1 / edge.ppg_ratio

            target_level = session.query(Level).filter_by(id=target_level_id).first()
            if target_level and target_level.skill_propagation_sequence == -1:
                correlation = session.query(SkillPropagationCorrelation).filter_by(
                    skill_value_from=min(level.skill_value, target_level.skill_value),
                    skill_value_to=max(level.skill_value, target_level.skill_value),
                    ppg_ratio=ppg_ratio if level.skill_value < target_level.skill_value else 1 / ppg_ratio
                ).first()

                if correlation:
                    suggested_skill_values[target_level_id].append(correlation.skill_value_to)

    # Update skill values for target levels
    for target_level_id, skill_values in suggested_skill_values.items():
        skill_values = Config.discard_outliers(np.array(skill_values))
        if len(skill_values) > 0:
            avg_skill_value = float(sum(skill_values) / len(skill_values))
            session.query(Level).filter_by(id=target_level_id).update({
                'skill_value': avg_skill_value,
                'skill_propagation_sequence': propagation_sequence + 1
            })
    session.commit()

    print(f"Skill levels have been propagated for sequence {propagation_sequence}.")

if __name__ == "__main__":
    build_levels_graph_edges()

    for sequence in range(Config.MAX_PROPAGATION_SEQUENCE + 1):
        propagate_skill_levels(sequence)

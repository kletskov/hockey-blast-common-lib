import os
import sys
from collections import defaultdict

import numpy as np

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.exc import IntegrityError

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Level
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    LevelsGraphEdge,
    LevelStatsSkater,
    SkillValuePPGRatio,
)


class Config:
    MIN_GAMES_PLAYED_FOR_EDGE = 10
    MIN_PPG_FOR_EDGE = 0.5
    MIN_HUMANS_FOR_EDGE = 2
    MAX_PROPAGATION_SEQUENCE = 4
    MIN_CONNECTIONS_FOR_CORRELATION = 20
    MIN_CONNECTIONS_FOR_PROPAGATION = 5
    MAX_SKILL_DIFF_IN_EDGE = 30

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


def reset_skill_values_in_divisions():
    session = create_session("boss")

    # Fetch all records from the Division table
    divisions = session.query(Division).all()

    for division in divisions:
        # Look up the Skill table using the level from Division
        div_level = division.level
        # Query to find the matching Skill
        level = (
            session.query(Level)
            .filter(Level.org_id == division.org_id, Level.level_name == div_level)
            .one_or_none()
        )

        if not level:
            # If no match found, check each alternative name individually
            skills = session.query(Level).filter(Level.org_id == division.org_id).all()
            for s in skills:
                if s.level_alternative_name:  # Check if not None
                    alternative_names = s.level_alternative_name.split(",")
                    if div_level in alternative_names:
                        level = s
                        break

        if level:
            # Assign the skill_value and set skill_propagation_sequence to 0
            division.level_id = level.id
            if level.is_seed:
                level.skill_propagation_sequence = 0
            else:
                level.skill_propagation_sequence = -1
                level.skill_value = -1
        else:
            # Check if level already exists with this org_id/level_name combination
            existing_level = (
                session.query(Level)
                .filter(
                    Level.org_id == division.org_id, Level.level_name == division.level
                )
                .first()
            )

            if existing_level:
                # Use existing level
                division.level_id = existing_level.id
                print(f"Using existing Level for Division {division.level}")
            else:
                # Add new Skill with values previously used for division
                new_level = Level(
                    org_id=division.org_id,
                    skill_value=-1,
                    level_name=division.level,
                    level_alternative_name="",
                    is_seed=False,
                    skill_propagation_sequence=-1,
                )
                session.add(new_level)
                try:
                    session.commit()
                    division.level_id = new_level.id
                    print(f"Created new Level for Division {division.level}")
                except IntegrityError:
                    session.rollback()
                    # Another process created this level, query for it
                    existing_level = (
                        session.query(Level)
                        .filter(
                            Level.org_id == division.org_id,
                            Level.level_name == division.level,
                        )
                        .first()
                    )
                    if existing_level:
                        division.level_id = existing_level.id
                        print(
                            f"Race condition resolved - using existing Level for Division {division.level}"
                        )
                    else:
                        raise RuntimeError(
                            f"Unable to create or find level: {division.level} for org_id: {division.org_id}"
                        )

        # Commit the changes to the Division
        session.commit()

    print(
        "Level values and propagation sequences have been populated into the Division table."
    )


def build_levels_graph_edges():
    # Creates unique edges from levelA to levelB (there is no reverse edge levelB to levelA)
    session = create_session("boss")

    # Delete all existing edges
    session.query(LevelsGraphEdge).delete()
    session.commit()

    # Query to get all level stats
    level_stats = session.query(LevelStatsSkater).all()

    # Dictionary to store stats by level and human
    level_human_stats = defaultdict(lambda: defaultdict(dict))

    for stat in level_stats:
        if (
            stat.games_played >= Config.MIN_GAMES_PLAYED_FOR_EDGE
            and stat.points_per_game >= Config.MIN_PPG_FOR_EDGE
        ):
            level_human_stats[stat.level_id][stat.human_id] = {
                "games_played": stat.games_played,
                "points_per_game": stat.points_per_game,
            }

    # Dictionary to store edges
    edges = {}

    # Build edges - batch load all levels first for performance
    all_level_ids = list(level_human_stats.keys())
    levels_dict = {
        level.id: level
        for level in session.query(Level).filter(Level.id.in_(all_level_ids)).all()
    }

    total_levels = len(level_human_stats)
    progress = create_progress_tracker(total_levels, "Building level graph edges")
    processed_levels = 0
    for from_level_id, from_humans in level_human_stats.items():
        from_level = levels_dict.get(from_level_id)
        if not from_level:
            continue
        for to_level_id, to_humans in level_human_stats.items():
            to_level = levels_dict.get(to_level_id)
            if not to_level or from_level.id >= to_level.id:
                continue

            common_humans = set(from_humans.keys()) & set(to_humans.keys())
            n_connections = len(common_humans)
            n_games = 0

            if n_connections < Config.MIN_HUMANS_FOR_EDGE:
                continue

            ppg_ratios = []
            # if from_level.id == 223 and to_level.id == 219: #216
            #     print(f"Debug: From Level ID: {from_level.id}, To Level ID: {to_level.id}")
            for human_id in common_humans:
                from_ppg = from_humans[human_id]["points_per_game"]
                to_ppg = to_humans[human_id]["points_per_game"]
                from_games = from_humans[human_id]["games_played"]
                to_games = to_humans[human_id]["games_played"]
                min_games = min(from_games, to_games)
                n_games += min_games

                # if from_level.id == 223 and to_level.id == 219: #216
                #     print(f"Human {human_id} From PPG: {from_ppg}, To PPG: {to_ppg}, Min Games: {min_games} n_games: {n_games}")

                if from_ppg > 0 and to_ppg > 0:
                    ppg_ratios.append(to_ppg / from_ppg)

            if not ppg_ratios:
                continue

            # Discard outliers
            ppg_ratios = Config.discard_outliers(np.array(ppg_ratios))

            if len(ppg_ratios) == 0:
                continue

            avg_ppg_ratio = float(sum(ppg_ratios) / len(ppg_ratios))

            # if sorted([from_level.id, to_level.id]) == [219, 223]:
            #     print(f"From {from_level_id} to {to_level_id} n_connections {n_connections} n_games: {n_games}")

            edge = LevelsGraphEdge(
                from_level_id=from_level_id,
                to_level_id=to_level_id,
                n_connections=n_connections,
                ppg_ratio=avg_ppg_ratio,
                n_games=n_games,  # Store the number of games
            )
            edges[(from_level_id, to_level_id)] = edge

        processed_levels += 1
        progress.update(processed_levels)

    # Insert edges into the database
    for edge in edges.values():
        session.add(edge)
    session.commit()

    print("\nLevels graph edges have been populated into the database.")


def propagate_skill_levels(propagation_sequence):
    min_skill_value = float("inf")
    max_skill_value = float("-inf")

    session = create_session("boss")

    if propagation_sequence == 0:
        # Delete all existing correlation data
        session.query(SkillValuePPGRatio).delete()
        session.commit()

        # Build and save the correlation data
        levels = (
            session.query(Level).filter(Level.skill_propagation_sequence == 0).all()
        )
        level_ids = {level.id for level in levels}
        correlation_data = defaultdict(list)

        for level in levels:
            if level.skill_value == -1:
                continue

            edges = (
                session.query(LevelsGraphEdge)
                .filter(
                    (LevelsGraphEdge.from_level_id == level.id)
                    | (LevelsGraphEdge.to_level_id == level.id)
                )
                .all()
            )

            for edge in edges:
                if edge.n_connections < Config.MIN_CONNECTIONS_FOR_CORRELATION:
                    continue

                if edge.from_level_id == level.id:
                    target_level_id = edge.to_level_id
                    ppg_ratio_edge = edge.ppg_ratio
                else:
                    # We go over same edge twice in this logic, let's skip the reverse edge
                    continue

                if target_level_id not in level_ids:
                    continue

                target_level = (
                    session.query(Level).filter_by(id=target_level_id).first()
                )
                if target_level:
                    skill_value_from = level.skill_value
                    skill_value_to = target_level.skill_value

                    # Same skill value - no correlation
                    if skill_value_from == skill_value_to:
                        continue

                    # Since we go over all levels in the sequence 0, we will see each edge twice
                    # This condition eliminates duplicates
                    if (
                        abs(skill_value_from - skill_value_to)
                        > Config.MAX_SKILL_DIFF_IN_EDGE
                    ):
                        continue

                    # Debug prints
                    # print(f"From Skill  {level.skill_value} to {target_level.skill_value} ratio: {ppg_ratio}")

                    # Ensure INCREASING SKILL VALUES for the correlation data!
                    if skill_value_from > skill_value_to:
                        skill_value_from, skill_value_to = (
                            skill_value_to,
                            skill_value_from,
                        )
                        ppg_ratio_edge = 1 / ppg_ratio_edge

                    correlation_data[(skill_value_from, skill_value_to)].append(
                        (ppg_ratio_edge, edge.n_games)
                    )

        # Save correlation data to the database
        for (skill_value_from, skill_value_to), ppg_ratios in correlation_data.items():
            ppg_ratios = [(ppg_ratio, n_games) for ppg_ratio, n_games in ppg_ratios]
            ppg_ratios_array = np.array(
                ppg_ratios, dtype=[("ppg_ratio", float), ("n_games", int)]
            )
            ppg_ratios_filtered = Config.discard_outliers(ppg_ratios_array["ppg_ratio"])
            if len(ppg_ratios_filtered) > 0:
                avg_ppg_ratio = float(
                    sum(
                        ppg_ratio * n_games
                        for ppg_ratio, n_games in ppg_ratios
                        if ppg_ratio in ppg_ratios_filtered
                    )
                    / sum(
                        n_games
                        for ppg_ratio, n_games in ppg_ratios
                        if ppg_ratio in ppg_ratios_filtered
                    )
                )
                total_n_games = sum(
                    n_games
                    for ppg_ratio, n_games in ppg_ratios
                    if ppg_ratio in ppg_ratios_filtered
                )
                correlation = SkillValuePPGRatio(
                    from_skill_value=skill_value_from,
                    to_skill_value=skill_value_to,
                    ppg_ratio=avg_ppg_ratio,
                    n_games=total_n_games,  # Store the sum of games
                )
                session.add(correlation)
                session.commit()
                # Update min and max skill values
                min_skill_value = min(min_skill_value, skill_value_from, skill_value_to)
                max_skill_value = max(max_skill_value, skill_value_from, skill_value_to)

    # Propagate skill levels
    levels = (
        session.query(Level)
        .filter(Level.skill_propagation_sequence == propagation_sequence)
        .all()
    )
    suggested_skill_values = defaultdict(list)

    for level in levels:
        edges = (
            session.query(LevelsGraphEdge)
            .filter(
                (LevelsGraphEdge.from_level_id == level.id)
                | (LevelsGraphEdge.to_level_id == level.id)
            )
            .all()
        )

        for edge in edges:
            if edge.n_connections < Config.MIN_CONNECTIONS_FOR_PROPAGATION:
                continue

            if edge.from_level_id == level.id:
                target_level_id = edge.to_level_id
                ppg_ratio_edge = edge.ppg_ratio
            else:
                target_level_id = edge.from_level_id
                ppg_ratio_edge = 1 / edge.ppg_ratio

            target_level = session.query(Level).filter_by(id=target_level_id).first()
            if target_level and target_level.skill_propagation_sequence == -1:
                correlations = (
                    session.query(SkillValuePPGRatio)
                    .filter(
                        (SkillValuePPGRatio.from_skill_value <= level.skill_value)
                        & (SkillValuePPGRatio.to_skill_value >= level.skill_value)
                    )
                    .all()
                )

                if correlations:
                    weighted_skill_values = []
                    for correlation in correlations:
                        # Skill value always increases in the correlation data
                        # Let's avoid extrapolating from the end of the edge and away from the edge!

                        # Check left side of the edge
                        if (
                            level.skill_value == correlation.from_skill_value
                            and level.skill_value > min_skill_value
                        ):
                            if ppg_ratio_edge < 1:
                                continue
                        # Check right side of the edge
                        if (
                            level.skill_value == correlation.to_skill_value
                            and level.skill_value < max_skill_value
                        ):
                            if ppg_ratio_edge > 1:
                                continue

                        # First confirm which way are we going here
                        if (ppg_ratio_edge < 1 and correlation.ppg_ratio > 1) or (
                            ppg_ratio_edge > 1 and correlation.ppg_ratio < 1
                        ):
                            # Reverse the correlation
                            from_skill_value = correlation.to_skill_value
                            to_skill_value = correlation.from_skill_value
                            ppg_ratio_range = 1 / correlation.ppg_ratio
                        else:
                            from_skill_value = correlation.from_skill_value
                            to_skill_value = correlation.to_skill_value
                            ppg_ratio_range = correlation.ppg_ratio

                        # Now both ratios are either < 1 or > 1
                        if ppg_ratio_edge < 1:
                            ppg_ratio_for_extrapolation = 1 / ppg_ratio_edge
                            ppg_ratio_range = 1 / ppg_ratio_range
                        else:
                            ppg_ratio_for_extrapolation = ppg_ratio_edge

                        # Interpolate or extrapolate skill value
                        skill_value_range = to_skill_value - from_skill_value
                        skill_value_diff = (
                            ppg_ratio_for_extrapolation / ppg_ratio_range
                        ) * skill_value_range
                        new_skill_value = level.skill_value + skill_value_diff
                        weighted_skill_values.append(
                            (new_skill_value, correlation.n_games)
                        )
                        # if target_level.id == 229:
                        #     print(f"Debug: From Level ID: {level.id}, To Level ID: {target_level.id}")
                        #     print(f"Debug: From Skill Value: {level.skill_value} PPG Ratio: {ppg_ratio_for_extrapolation}, PPG Ratio Range: {ppg_ratio_range}")
                        #     print(f"Debug: Skill Value Range: {skill_value_range}, Skill Value Diff: {skill_value_diff}")
                        #     print(f"Debug: New Skill Value: {new_skill_value}")

                    # Calculate weighted average of new skill values
                    total_n_games = sum(n_games for _, n_games in weighted_skill_values)
                    weighted_avg_skill_value = (
                        sum(
                            skill_value * n_games
                            for skill_value, n_games in weighted_skill_values
                        )
                        / total_n_games
                    )
                    suggested_skill_values[target_level_id].append(
                        weighted_avg_skill_value
                    )

    # Update skill values for target levels
    session.flush()  # Ensure all previous changes are flushed before updates
    for target_level_id, skill_values in suggested_skill_values.items():
        skill_values = Config.discard_outliers(np.array(skill_values))
        if len(skill_values) > 0:
            avg_skill_value = float(sum(skill_values) / len(skill_values))
            avg_skill_value = max(avg_skill_value, 9.6)
            if avg_skill_value < min_skill_value:
                avg_skill_value = min_skill_value - 0.01
            try:
                session.query(Level).filter_by(id=target_level_id).update(
                    {
                        "skill_value": avg_skill_value,
                        "skill_propagation_sequence": propagation_sequence + 1,
                    }
                )
                session.flush()  # Flush each update individually
            except Exception as e:
                print(f"Error updating level {target_level_id}: {e}")
                session.rollback()
                continue
    session.commit()

    print(f"Skill levels have been propagated for sequence {propagation_sequence}.")


if __name__ == "__main__":
    reset_skill_values_in_divisions()
    build_levels_graph_edges()

    for sequence in range(Config.MAX_PROPAGATION_SEQUENCE + 1):
        propagate_skill_levels(sequence)

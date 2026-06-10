"""
Game status constants matching the game_statuses table in the database.

Usage:
    from hockey_blast_common_lib.game_status_constants import (
        STATUS_FINAL, FINAL_STATUSES, COMPLETED_STATUSES, STATS_STATUSES,
        is_final, is_completed,
    )
"""

# Individual status IDs (match game_statuses.id in DB)
STATUS_CANCELED = 1
STATUS_FAILED = 2
STATUS_FINAL = 3
STATUS_FINAL_OT = 4
STATUS_FINAL_SO = 5
STATUS_FORFEIT = 6
STATUS_NOEVENTS = 7
STATUS_NOT_STARTED = 8
STATUS_OPEN = 9
STATUS_SCHEDULED = 10
STATUS_UNKNOWN = 11

# Useful sets for filtering

# Games that ended with a final score (regulation, OT, or shootout)
FINAL_STATUSES = {STATUS_FINAL, STATUS_FINAL_OT, STATUS_FINAL_SO}

# All games that are considered "completed" (finished, regardless of whether stats exist)
COMPLETED_STATUSES = {STATUS_FINAL, STATUS_FINAL_OT, STATUS_FINAL_SO, STATUS_FORFEIT, STATUS_NOEVENTS}

# Games with actual scored statistics (goals, shots, etc.) — used for per-game stat averages
STATS_STATUSES = {STATUS_FINAL, STATUS_FINAL_OT, STATUS_FINAL_SO}


def is_final(status_id):
    """Check if a game status represents a final result (regulation, OT, or SO)."""
    return status_id in FINAL_STATUSES


def is_completed(status_id):
    """Check if a game status represents a completed game (any terminal state with participation)."""
    return status_id in COMPLETED_STATUSES

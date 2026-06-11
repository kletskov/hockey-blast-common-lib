"""
Game status constants and helpers.

Status IDs match the game_statuses table. Use these constants and helpers
instead of comparing text strings.
"""


class StatusId:
    CANCELED = 1
    FAILED = 2
    FINAL = 3
    FINAL_OT = 4
    FINAL_SO = 5
    FORFEIT = 6
    NOEVENTS = 7
    NOT_STARTED = 8
    OPEN = 9
    SCHEDULED = 10
    UNKNOWN = 11


FINAL_STATUS_IDS = frozenset({StatusId.FINAL, StatusId.FINAL_OT, StatusId.FINAL_SO})
COMPLETED_STATUS_IDS = frozenset({StatusId.FINAL, StatusId.FINAL_OT, StatusId.FINAL_SO, StatusId.FORFEIT})
PARTICIPATED_STATUS_IDS = frozenset({StatusId.FINAL, StatusId.FINAL_OT, StatusId.FINAL_SO, StatusId.FORFEIT, StatusId.NOEVENTS})
PENDING_STATUS_IDS = frozenset({StatusId.SCHEDULED, StatusId.NOT_STARTED, StatusId.OPEN})

STATUS_NAMES = {
    StatusId.CANCELED: "CANCELED",
    StatusId.FAILED: "FAILED",
    StatusId.FINAL: "FINAL",
    StatusId.FINAL_OT: "FINAL_OT",
    StatusId.FINAL_SO: "FINAL_SO",
    StatusId.FORFEIT: "FORFEIT",
    StatusId.NOEVENTS: "NOEVENTS",
    StatusId.NOT_STARTED: "NOT_STARTED",
    StatusId.OPEN: "OPEN",
    StatusId.SCHEDULED: "SCHEDULED",
    StatusId.UNKNOWN: "UNKNOWN",
}


def is_final(game):
    return game.status_id in FINAL_STATUS_IDS


def is_completed(game):
    return game.status_id in COMPLETED_STATUS_IDS


def is_pending(game):
    return game.status_id in PENDING_STATUS_IDS


def is_forfeit(game):
    return game.status_id == StatusId.FORFEIT


def is_canceled(game):
    return game.status_id == StatusId.CANCELED


def is_open(game):
    return game.status_id == StatusId.OPEN


def is_scheduled(game):
    return game.status_id == StatusId.SCHEDULED


def status_name(game):
    return STATUS_NAMES.get(game.status_id, "UNKNOWN")

import argparse

from .models import Human

MAX_HUMAN_SEARCH_RESULTS = 25
MAX_TEAM_SEARCH_RESULTS = 25
MIN_GAMES_FOR_ORG_STATS = 1
MIN_GAMES_FOR_DIVISION_STATS = 1
MIN_GAMES_FOR_LEVEL_STATS = 1

orgs = {"caha", "sharksice", "tvice"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process data for a specific organization."
    )
    parser.add_argument(
        "org",
        choices=orgs,
        help="The organization to process (e.g., 'caha', 'sharksice', 'tvice').",
    )
    parser.add_argument(
        "--reprocess", action="store_true", help="Reprocess existing data."
    )
    parser.add_argument(
        "--pre_process", action="store_true", help="Pre-Process existing data."
    )
    return parser.parse_args()


def get_or_create_empty_net_human(session, game_date):
    """Get or create the special 'Empty Net' human record for tracking pulled goalies.

    Args:
        session: Database session
        game_date: Date of the game (used for first_date/last_date if creating)

    Returns:
        int: The human_id of the Empty Net special record
    """
    empty_net_human = (
        session.query(Human)
        .filter_by(first_name="Empty", middle_name="", last_name="Net")
        .first()
    )

    if not empty_net_human:
        empty_net_human = Human(
            first_name="Empty",
            middle_name="",
            last_name="Net",
            first_date=game_date,
            last_date=game_date,
        )
        session.add(empty_net_human)
        session.commit()

    return empty_net_human.id

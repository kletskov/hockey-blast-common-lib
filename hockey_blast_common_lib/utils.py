import os
import sys
from datetime import datetime, timedelta

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.sql import func

from hockey_blast_common_lib.models import Division, Human, Level, Organization


def get_org_id_from_alias(session, org_alias):
    # Predefined organizations
    predefined_organizations = [
        {
            "id": 1,
            "organization_name": "Sharks Ice",
            "alias": "sharksice",
            "website": "https://www.sharksice.com",
        },
        {
            "id": 2,
            "organization_name": "TriValley Ice",
            "alias": "tvice",
            "website": "https://www.trivalleyice.com",
        },
        {
            "id": 3,
            "organization_name": "CAHA",
            "alias": "caha",
            "website": "https://www.caha.com",
        },
        {
            "id": 4,
            "organization_name": "Tacoma Twin Rinks",
            "alias": "ttr",
            "website": "https://psicesports.com",
        },
    ]

    # Check if the organization exists
    organization = session.query(Organization).filter_by(alias=org_alias).first()
    if organization:
        return organization.id
    else:
        # Insert predefined organizations if they do not exist
        for org in predefined_organizations:
            existing_org = session.query(Organization).filter_by(id=org["id"]).first()
            if not existing_org:
                new_org = Organization(
                    id=org["id"],
                    organization_name=org["organization_name"],
                    alias=org["alias"],
                    website=org["website"],
                )
                session.add(new_org)
        session.commit()

        # Retry to get the organization after inserting predefined organizations
        organization = session.query(Organization).filter_by(alias=org_alias).first()
        if organization:
            return organization.id
        else:
            raise ValueError(f"Organization with alias '{org_alias}' not found.")


def get_human_ids_by_names(session, names):
    human_ids = set()
    for first_name, middle_name, last_name in names:
        query = session.query(Human.id)
        if first_name:
            query = query.filter(Human.first_name == first_name)
        if middle_name:
            query = query.filter(Human.middle_name == middle_name)
        if last_name:
            query = query.filter(Human.last_name == last_name)
        results = query.all()
        human_ids.update([result.id for result in results])
    return human_ids


def get_non_human_ids(session):
    """Get IDs of non-human entities (placeholder names, test accounts, etc.)

    Returns set of human_ids that should be filtered out from statistics.
    Filters out placeholder names like "Home", "Away", "Unknown", etc.
    Also excludes percentile marker humans.
    """
    not_human_names = [
        ("Home", None, None),
        ("Away", None, None),
        (None, "Unknown", None),
        ("Not", None, None),
        (None, None, "Goalie"),
        ("Unassigned", None, None),
        ("Not", "Signed", "In"),
        ("Incognito", None, None),
        ("Empty", None , "Net"),
        ("Fake", "Stats", "Human"),
        (None, None, "Percentile"),
    ]

    return get_human_ids_by_names(session, not_human_names)


def get_division_ids_for_last_season_in_all_leagues(session, org_id):
    # # TODO = remove tmp hack
    # return get_all_division_ids_for_org(session, org_id)
    league_numbers = (
        session.query(Division.league_number)
        .filter(Division.org_id == org_id)
        .distinct()
        .all()
    )
    division_ids = []
    for (league_number,) in league_numbers:
        max_season_number = (
            session.query(func.max(Division.season_number))
            .filter_by(league_number=league_number, org_id=org_id)
            .scalar()
        )
        division_ids_for_league = (
            session.query(Division.id)
            .filter_by(
                league_number=league_number,
                season_number=max_season_number,
                org_id=org_id,
            )
            .all()
        )
        division_ids.extend([division_id.id for division_id in division_ids_for_league])
    return division_ids


def get_all_division_ids_for_org(session, org_id):
    division_ids_for_org = session.query(Division.id).filter_by(org_id=org_id).all()
    return [division_id.id for division_id in division_ids_for_org]


def get_fake_human_for_stats(session):
    first_name = "Fake"
    middle_name = "Stats"
    last_name = "Human"

    # Check if the human already exists
    existing_human = (
        session.query(Human)
        .filter_by(first_name=first_name, middle_name=middle_name, last_name=last_name)
        .first()
    )
    if existing_human:
        return existing_human.id

    # Create a new human
    human = Human(first_name=first_name, middle_name=middle_name, last_name=last_name)
    session.add(human)
    session.commit()  # Commit to get the human.id

    return human.id


def get_start_datetime(last_game_datetime_str, aggregation_window):
    if aggregation_window == "Weekly":
        if last_game_datetime_str:
            last_game_datetime = datetime.strptime(
                last_game_datetime_str, "%Y-%m-%d %H:%M:%S"
            )
            # Check if the last game datetime is over 1 week from now
            if datetime.now() - last_game_datetime > timedelta(weeks=1):
                return None
        # Use current time as the start of the weekly window
        return datetime.now() - timedelta(weeks=1)
    if last_game_datetime_str:
        last_game_datetime = datetime.strptime(
            last_game_datetime_str, "%Y-%m-%d %H:%M:%S"
        )
        if aggregation_window == "Daily":
            # Check if the last game datetime is over 24 hours from now
            if datetime.now() - last_game_datetime > timedelta(hours=24):
                return None
            # From 10AM till midnight, 14 hours to avoid last day games
            return last_game_datetime - timedelta(hours=14)
    return None


def assign_ranks(stats_dict, field, reverse_rank=False):
    sorted_stats = sorted(
        stats_dict.items(), key=lambda x: x[1][field], reverse=not reverse_rank
    )
    for rank, (key, stat) in enumerate(sorted_stats, start=1):
        stats_dict[key][f"{field}_rank"] = rank


def get_fake_level(session):
    # Create a special fake Skill with org_id == -1 and skill_value == -1
    fake_skill = (
        session.query(Level).filter_by(org_id=1, level_name="Fake Skill").first()
    )
    if not fake_skill:
        fake_skill = Level(
            org_id=1,
            skill_value=-1,
            level_name="Fake Skill",
            level_alternative_name="",
            is_seed=False,
        )
        session.add(fake_skill)
        session.commit()
        print("Created special fake Skill record.")
    return fake_skill


def get_percentile_human(session, entity_type, percentile):
    """Get or create a human record representing a percentile marker.

    Args:
        session: Database session
        entity_type: One of "Skater", "Goalie", "Ref", "Scorekeeper"
        percentile: One of 25, 50, 75, 90, 95

    Returns:
        human_id of the percentile marker record
    """
    first_name = entity_type
    middle_name = str(percentile)
    last_name = "Percentile"

    # Check if the human already exists
    existing_human = (
        session.query(Human)
        .filter_by(first_name=first_name, middle_name=middle_name, last_name=last_name)
        .first()
    )
    if existing_human:
        return existing_human.id

    # Create a new human
    human = Human(first_name=first_name, middle_name=middle_name, last_name=last_name)
    session.add(human)
    session.commit()

    return human.id


def calculate_percentile_value(values, percentile):
    """Calculate the percentile value from a list of values.

    Args:
        values: List of numeric values
        percentile: Percentile to calculate (e.g., 25, 50, 75, 90, 95)

    Returns:
        The value at the given percentile
    """
    if not values:
        return 0

    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate index (using linear interpolation method)
    index = (percentile / 100.0) * (n - 1)
    lower_index = int(index)
    upper_index = min(lower_index + 1, n - 1)

    # Interpolate if needed
    fraction = index - lower_index
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]

    return lower_value + fraction * (upper_value - lower_value)


# TEST DB CONNECTION, PERMISSIONS...
# from hockey_blast_common_lib.db_connection import create_session
# session = create_session("frontend")
# human_id = get_fake_human_for_stats(session)
# print(f"Human ID: {human_id}")

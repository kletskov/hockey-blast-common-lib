import sys
import os
from datetime import datetime, timedelta


from hockey_blast_common_lib.models import Organization, Human, Division
from sqlalchemy.sql import func


def get_org_id_from_alias(session, org_alias):
    # Predefined organizations
    predefined_organizations = [
        {"id": 1, "organization_name": "Sharks Ice", "alias": "sharksice"},
        {"id": 2, "organization_name": "TriValley Ice", "alias": "tvice"},
        {"id": 3, "organization_name": "CAHA", "alias": "caha"}
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
                new_org = Organization(id=org["id"], organization_name=org["organization_name"], alias=org["alias"])
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

def get_division_ids_for_last_season_in_all_leagues(session, org_id):
    # # TODO = remove tmp hack
    # return get_all_division_ids_for_org(session, org_id)
    league_numbers = session.query(Division.league_number).filter(Division.org_id == org_id).distinct().all()
    division_ids = []
    for league_number, in league_numbers:
        max_season_number = session.query(func.max(Division.season_number)).filter_by(league_number=league_number, org_id=org_id).scalar()
        division_ids_for_league = session.query(Division.id).filter_by(league_number=league_number, season_number=max_season_number, org_id=org_id).all()
        division_ids.extend([division_id.id for division_id in division_ids_for_league])
    return division_ids

def get_all_division_ids_for_org(session, org_id):
    division_ids_for_org = session.query(Division.id).filter_by(org_id=org_id).all()
    return [division_id.id for division_id in division_ids_for_org]

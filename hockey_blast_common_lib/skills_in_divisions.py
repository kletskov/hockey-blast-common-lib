import os
import sys
from collections import defaultdict

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Game, League, Level, Season
from hockey_blast_common_lib.utils import get_fake_level


def analyze_levels(org):
    session = create_session(org)

    # Query to get games and their divisions for season_number 33 and 35 with league_number 1
    games_season_33 = (
        session.query(Game.home_team_id, Game.visitor_team_id, Division.level)
        .join(Division, Game.division_id == Division.id)
        .filter(Division.season_number == 33, Division.league_number == 1)
        .all()
    )
    games_season_35 = (
        session.query(Game.home_team_id, Game.visitor_team_id, Division.level)
        .join(Division, Game.division_id == Division.id)
        .filter(Division.season_number == 35, Division.league_number == 1)
        .all()
    )

    # Dictionary to store levels for each team by season
    team_levels_season_33 = defaultdict(set)
    team_levels_season_35 = defaultdict(set)

    # Populate the dictionaries
    for home_team_id, visitor_team_id, level in games_season_33:
        team_levels_season_33[home_team_id].add(level)
        team_levels_season_33[visitor_team_id].add(level)

    for home_team_id, visitor_team_id, level in games_season_35:
        team_levels_season_35[home_team_id].add(level)
        team_levels_season_35[visitor_team_id].add(level)

    # Dictionary to store level name connections
    level_connections = defaultdict(lambda: defaultdict(int))

    # Analyze the level name connections
    for team_id in team_levels_season_33:
        if team_id in team_levels_season_35:
            for old_level in team_levels_season_33[team_id]:
                for new_level in team_levels_season_35[team_id]:
                    level_connections[new_level][old_level] += 1

    # Output the results
    for new_level in sorted(level_connections.keys()):
        connections = level_connections[new_level]
        connections_list = sorted(connections.items(), key=lambda x: x[0])
        connections_str = ", ".join(
            [f"{old_level}: {count}" for old_level, count in connections_list]
        )
        print(f"{new_level}: {connections_str}")

    session.close()


def fill_seed_levels():
    session = create_session("boss")

    # List of Skill objects based on the provided comments
    levels = [
        Level(
            is_seed=True,
            org_id=1,
            skill_value=10.0,
            level_name="Adult Division 1",
            level_alternative_name="Senior A",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=20.0,
            level_name="Adult Division 2",
            level_alternative_name="Senior B",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=30.0,
            level_name="Adult Division 3A",
            level_alternative_name="Senior BB",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=35.0,
            level_name="Adult Division 3B",
            level_alternative_name="Senior C",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=40.0,
            level_name="Adult Division 4A",
            level_alternative_name="Senior CC",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=45.0,
            level_name="Adult Division 4B",
            level_alternative_name="Senior CCC,Senior CCCC",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=50.0,
            level_name="Adult Division 5A",
            level_alternative_name="Senior D,Senior DD",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=55.0,
            level_name="Adult Division 5B",
            level_alternative_name="Senior DDD",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=60.0,
            level_name="Adult Division 6A",
            level_alternative_name="Senior DDDD",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=65.0,
            level_name="Adult Division 6B",
            level_alternative_name="Senior DDDDD",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=70.0,
            level_name="Adult Division 7A",
            level_alternative_name="Senior E",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=75.0,
            level_name="Adult Division 7B",
            level_alternative_name="Senior EE",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=80.0,
            level_name="Adult Division 8",
            level_alternative_name="Senior EEE",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=80.0,
            level_name="Adult Division 8A",
            level_alternative_name="Senior EEE",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=85.0,
            level_name="Adult Division 8B",
            level_alternative_name="Senior EEEE",
        ),
        Level(
            is_seed=True,
            org_id=1,
            skill_value=90.0,
            level_name="Adult Division 9",
            level_alternative_name="Senior EEEEE",
        ),
    ]

    for skill in levels:
        session.add(skill)
        session.commit()

    print("Seed skills have been populated into the database.")


def assign_fake_level_to_divisions(session, fake_level):
    # Assign the special fake Skill to every existing Division
    divisions = session.query(Division).all()
    for division in divisions:
        division.skill_id = fake_level.id
    session.commit()
    print("Assigned special fake Skill to all Division records.")


def delete_all_levels():
    session = create_session("boss")
    fake_level = get_fake_level(session)
    assign_fake_level_to_divisions(session, fake_level)
    # Delete all Skill records except the fake skill
    session.query(Level).filter(Level.id != fake_level.id).delete(
        synchronize_session=False
    )
    session.commit()
    print("All Skill records except the fake skill have been deleted.")


def populate_season_ids():
    session = create_session("boss")
    divisions = session.query(Division).all()
    for division in divisions:
        # Find the Season record that matches the season_number
        season = (
            session.query(Season)
            .filter_by(
                season_number=division.season_number,
                org_id=division.org_id,
                league_number=division.league_number,
            )
            .first()
        )
        if season:
            division.season_id = season.id
            print(
                f"Assigned season_id {season.id} for Division with season_number {division.season_number}"
            )
        else:
            print(
                f"Season not found for Division with season_number {division.season_number}"
            )
    session.commit()
    print("Season IDs have been populated into the Division table.")


def populate_league_ids():
    session = create_session("boss")
    seasons = session.query(Season).all()
    for season in seasons:
        # Find the League record that matches the league_number and org_id
        league = (
            session.query(League)
            .filter_by(league_number=season.league_number, org_id=season.org_id)
            .first()
        )
        if league:
            season.league_id = league.id
            print(
                f"Assigned league_id {league.id} for Season with league_number {season.league_number}"
            )
        else:
            print(
                f"League not found for Season with league_number {season.league_number}"
            )
    session.commit()
    print("League IDs have been populated into the Season table.")


# if __name__ == "__main__":
# delete_all_levels()
# fill_seed_levels()
# populate_season_ids()  # Call the function to populate season_ids
# populate_league_ids()  # Call the new function to populate league_ids

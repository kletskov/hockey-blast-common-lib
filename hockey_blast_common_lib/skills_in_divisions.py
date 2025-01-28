import sys
import os
from collections import defaultdict

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.models import Game, Division, Skill, Season, League
from hockey_blast_common_lib.db_connection import create_session

def analyze_levels(org):
    session = create_session(org)

    # Query to get games and their divisions for season_number 33 and 35 with league_number 1
    games_season_33 = session.query(Game.home_team_id, Game.visitor_team_id, Division.level).join(Division, Game.division_id == Division.id).filter(Division.season_number == 33, Division.league_number == 1).all()
    games_season_35 = session.query(Game.home_team_id, Game.visitor_team_id, Division.level).join(Division, Game.division_id == Division.id).filter(Division.season_number == 35, Division.league_number == 1).all()

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
        connections_str = ", ".join([f"{old_level}: {count}" for old_level, count in connections_list])
        print(f"{new_level}: {connections_str}")

    session.close()

def fill_missing_skills_in_divisions():
    session = create_session("boss")

    # Fetch all records from the Division table where skill_id is null or it's the fake_skill
    fake_skill = get_fake_skill(session)
    divisions = session.query(Division).filter(
        (Division.skill_id == None) | (Division.skill_id == fake_skill.id)
    ).all()

    for division in divisions:
        # Look up the Skill table using the level from Division
        div_level = division.level

        # Query to find the matching Skill
        skill = session.query(Skill).filter(Skill.org_id == division.org_id, Skill.level_name == div_level).one_or_none()

        if not skill:
            # If no match found, check each alternative name individually
            skills = session.query(Skill).filter(Skill.org_id == division.org_id).all()
            for s in skills:
                alternative_names = s.level_alternative_name.split(',')
                if div_level in alternative_names:
                    skill = s
                    break

        if not skill:
            # Create a new Skill with this level_name and skill_value of 49.99
            skill = Skill(
                org_id=division.org_id,
                skill_value=-1.1,
                level_name=division.level,
                level_alternative_name=''
            )
            session.add(skill)
            session.commit()  # Commit to get the new level id

        # Assign the new level id to Division.level_id
        division.skill_id = skill.id
        print(f"Assigned Skill {skill.skill_value} for Division with name {division.level}")

        # Commit the changes to the Division
        session.commit()

    print("Skill IDs have been populated into the Division table.")

def fill_seed_skills():
    session = create_session("boss")

    # List of Skill objects based on the provided comments
    skills = [
        Skill(is_seed=True, org_id=1, skill_value=10.0, level_name='Adult Division 1', level_alternative_name='Senior A'),
        Skill(is_seed=True, org_id=1, skill_value=20.0, level_name='Adult Division 2', level_alternative_name='Senior B'),
        Skill(is_seed=True, org_id=1, skill_value=30.0, level_name='Adult Division 3A', level_alternative_name='Senior BB'),
        Skill(is_seed=True, org_id=1, skill_value=35.0, level_name='Adult Division 3B', level_alternative_name='Senior C'),
        Skill(is_seed=True, org_id=1, skill_value=40.0, level_name='Adult Division 4A', level_alternative_name='Senior CC'),
        Skill(is_seed=True, org_id=1, skill_value=45.0, level_name='Adult Division 4B', level_alternative_name='Senior CCC,Senior CCCC'),
        Skill(is_seed=True, org_id=1, skill_value=50.0, level_name='Adult Division 5A', level_alternative_name='Senior D,Senior DD'),
        Skill(is_seed=True, org_id=1, skill_value=55.0, level_name='Adult Division 5B', level_alternative_name='Senior DDD'),
        Skill(is_seed=True, org_id=1, skill_value=60.0, level_name='Adult Division 6A', level_alternative_name='Senior DDDD'),
        Skill(is_seed=True, org_id=1, skill_value=65.0, level_name='Adult Division 6B', level_alternative_name='Senior DDDDD'),
        Skill(is_seed=True, org_id=1, skill_value=70.0, level_name='Adult Division 7A', level_alternative_name='Senior E'),
        Skill(is_seed=True, org_id=1, skill_value=75.0, level_name='Adult Division 7B', level_alternative_name='Senior EE'),
        Skill(is_seed=True, org_id=1, skill_value=80.0, level_name='Adult Division 8', level_alternative_name='Senior EEE'),
        Skill(is_seed=True, org_id=1, skill_value=80.0, level_name='Adult Division 8A', level_alternative_name='Senior EEE'),
        Skill(is_seed=True, org_id=1, skill_value=85.0, level_name='Adult Division 8B', level_alternative_name='Senior EEEE'),
        Skill(is_seed=True, org_id=1, skill_value=90.0, level_name='Adult Division 9', level_alternative_name='Senior EEEEE')
    ]

    for skill in skills:
        session.add(skill)
        session.commit()

    print("Seed skills have been populated into the database.")

def get_fake_skill(session):
    # Create a special fake Skill with org_id == -1 and skill_value == -1
    fake_skill = session.query(Skill).filter_by(org_id=1, level_name='Fake Skill').first()
    if not fake_skill:
        fake_skill = Skill(
            org_id=1,
            skill_value=-1,
            level_name='Fake Skill',
            level_alternative_name='',
            is_seed=False
        )
        session.add(fake_skill)
        session.commit()
        print("Created special fake Skill record.")
    return fake_skill

def assign_fake_skill_to_divisions(session, fake_skill):
    # Assign the special fake Skill to every existing Division
    divisions = session.query(Division).all()
    for division in divisions:
        division.skill_id = fake_skill.id
    session.commit()
    print("Assigned special fake Skill to all Division records.")

def delete_all_skills():
    session = create_session("boss")
    fake_skill = get_fake_skill(session)
    assign_fake_skill_to_divisions(session, fake_skill)
    # Delete all Skill records except the fake skill
    session.query(Skill).filter(Skill.id != fake_skill.id).delete(synchronize_session=False)
    session.commit()
    print("All Skill records except the fake skill have been deleted.")

def populate_season_ids():
    session = create_session("boss")
    divisions = session.query(Division).all()
    for division in divisions:
        # Find the Season record that matches the season_number
        season = session.query(Season).filter_by(season_number=division.season_number, org_id=division.org_id, league_number=division.league_number).first()
        if season:
            division.season_id = season.id
            print(f"Assigned season_id {season.id} for Division with season_number {division.season_number}")
        else:
            print(f"Season not found for Division with season_number {division.season_number}")
    session.commit()
    print("Season IDs have been populated into the Division table.")

def populate_league_ids():
    session = create_session("boss")
    seasons = session.query(Season).all()
    for season in seasons:
        # Find the League record that matches the league_number and org_id
        league = session.query(League).filter_by(league_number=season.league_number, org_id=season.org_id).first()
        if league:
            season.league_id = league.id
            print(f"Assigned league_id {league.id} for Season with league_number {season.league_number}")
        else:
            print(f"League not found for Season with league_number {season.league_number}")
    session.commit()
    print("League IDs have been populated into the Season table.")

if __name__ == "__main__":
    # delete_all_skills()
    # fill_seed_skills()
    # fill_missing_skills_in_divisions()
    #populate_season_ids()  # Call the function to populate season_ids
    populate_league_ids()  # Call the new function to populate league_ids

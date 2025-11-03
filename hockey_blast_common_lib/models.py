from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# DEPRECATED - comments
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    comment_text = db.Column(db.Text)
    __table_args__ = (
        db.UniqueConstraint("game_id", "comment_text", name="unique_game_comment"),
    )


class Division(db.Model):
    __tablename__ = "divisions"
    id = db.Column(db.Integer, primary_key=True)
    league_number = db.Column(
        db.Integer
    )  # TODO: Deprecate usage and remove (get this info through Season->League)
    season_number = db.Column(
        db.Integer
    )  # TODO: Deprecate usage and remove (get this info from Season by season_id)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"))
    level = db.Column(
        db.String(100)
    )  # Used to display original level name, however level_id may combine some levels with different name!
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"))  # New field
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            "org_id",
            "league_number",
            "season_number",
            "level",
            name="_org_league_season_level_uc",
        ),
    )


class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(255), nullable=False, default="")
    last_update_ts = db.Column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"))
    game_number = db.Column(db.Integer)
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    day_of_week = db.Column(db.Integer)  # 1 to 7 for Monday to Sunday
    period_length = db.Column(db.Integer)  # In minutes
    location = db.Column(db.String(100))
    scorekeeper_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    referee_1_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    referee_2_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    home_goalie_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    visitor_goalie_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    visitor_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    visitor_final_score = db.Column(db.Integer)
    visitor_period_1_score = db.Column(db.Integer)
    visitor_period_2_score = db.Column(db.Integer)
    visitor_period_3_score = db.Column(db.Integer)
    home_final_score = db.Column(db.Integer)
    home_period_1_score = db.Column(db.Integer)
    home_period_2_score = db.Column(db.Integer)
    home_period_3_score = db.Column(db.Integer)
    home_ot_score = db.Column(db.Integer, default=0)
    visitor_ot_score = db.Column(db.Integer, default=0)
    game_type = db.Column(db.String(50))
    went_to_ot = db.Column(db.Boolean, default=False)
    home_period_1_shots = db.Column(db.Integer)
    home_period_2_shots = db.Column(db.Integer)
    home_period_3_shots = db.Column(db.Integer)
    home_ot_shots = db.Column(db.Integer, default=0)
    home_so_shots = db.Column(db.Integer, default=0)
    visitor_period_1_shots = db.Column(db.Integer)
    visitor_period_2_shots = db.Column(db.Integer)
    visitor_period_3_shots = db.Column(db.Integer)
    visitor_ot_shots = db.Column(db.Integer, default=0)
    visitor_so_shots = db.Column(db.Integer, default=0)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("org_id", "game_number", name="_org_game_number_uc"),
    )


class GameRoster(db.Model):
    __tablename__ = "game_rosters"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    role = db.Column(
        db.String(10)
    )  # e.g., G (goalie), C (captain), A (alternate), S (substitute)
    jersey_number = db.Column(db.String(10))  # Player's jersey number
    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "team_id", "human_id", name="_game_team_human_uc"
        ),
    )


class Goal(db.Model):
    __tablename__ = "goals"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    scoring_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    opposing_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    period = db.Column(db.String(10))  # Can be "1", "2", "3", "OT", "SO"
    time = db.Column(db.String(10))  # For elapsed time format
    goal_scorer_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    assist_1_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    assist_2_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    goalie_id = db.Column(
        db.Integer, db.ForeignKey("humans.id"), nullable=True
    )  # Goalie who allowed the goal (can be "Empty Net" special human)
    special_condition = db.Column(
        db.String(50)
    )  # e.g., PP (power play), SH (short-handed)
    sequence_number = db.Column(db.Integer)
    __table_args__ = (
        db.UniqueConstraint(
            "game_id",
            "scoring_team_id",
            "sequence_number",
            name="_goal_team_sequence_uc",
        ),
        db.UniqueConstraint(
            "game_id",
            "period",
            "time",
            "goal_scorer_id",
            "scoring_team_id",
            name="uq_goals_no_duplicates",
        ),
    )


class Human(db.Model):
    __tablename__ = "humans"
    id = db.Column(db.Integer, primary_key=True)
    # All name components now declared non-nullable at the ORM level. Ensure data cleanup
    # (convert existing NULLs to '') BEFORE applying a DB migration that enforces NOT NULL.
    # middle_name and suffix may be logically "empty" but must not be NULL; use '' for absence.
    first_name = db.Column(db.String(100), nullable=False, default="")
    middle_name = db.Column(db.String(100), nullable=False, default="")
    last_name = db.Column(db.String(100), nullable=False, default="")
    suffix = db.Column(db.String(100), nullable=False, default="")
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    skater_skill_value = db.Column(db.Float, nullable=True)
    __table_args__ = (
        db.UniqueConstraint(
            "first_name", "middle_name", "last_name", "suffix", name="_human_name_uc"
        ),
    )


class HumanAlias(db.Model):
    __tablename__ = "human_aliases"
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    suffix = db.Column(db.String(100))
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "human_id",
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            name="_human_alias_uc",
        ),
    )


class HumanInTTS(db.Model):
    __tablename__ = "humans_in_tts"
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    tts_id = db.Column(db.Integer)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("org_id", "tts_id", name="_org_tts_uc"),)


class HumansInLevels(db.Model):
    __tablename__ = "humans_in_levels"
    id = db.Column(db.Integer, primary_key=True)
    levels_monthly_id = db.Column(db.Integer, db.ForeignKey("levels_monthly.id"))
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    games_played = db.Column(db.Integer)
    __table_args__ = (
        db.UniqueConstraint(
            "levels_monthly_id", "human_id", name="_levels_monthly_human_uc"
        ),
    )


class HumanPrivacyOptOut(db.Model):
    __tablename__ = "human_privacy_opt_outs"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=False, default="")
    last_name = db.Column(db.String(100), nullable=False)
    suffix = db.Column(db.String(100), nullable=False, default="")
    opt_out_date = db.Column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    notes = db.Column(db.Text, nullable=True)
    __table_args__ = (
        db.UniqueConstraint(
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            name="_privacy_optout_name_uc",
        ),
    )


class League(db.Model):
    __tablename__ = "leagues"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    league_number = db.Column(db.Integer)
    league_name = db.Column(db.String(100))
    __table_args__ = (
        db.UniqueConstraint("org_id", "league_number", name="_org_league_number_uc"),
    )


class Level(db.Model):
    __tablename__ = "levels"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    skill_value = db.Column(db.Float)  # A number from 0 (NHL) to 100 (pedestrian)
    level_name = db.Column(db.String(100))
    level_alternative_name = db.Column(db.String(100))
    is_seed = db.Column(db.Boolean, nullable=True, default=False)  # New field
    skill_propagation_sequence = db.Column(db.Integer, nullable=True, default=-1)
    __table_args__ = (
        db.UniqueConstraint("org_id", "level_name", name="_org_level_name_uc"),
    )


class LevelsMonthly(db.Model):
    __tablename__ = "levels_monthly"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    league_number = db.Column(db.Integer)
    season_number = db.Column(db.Integer)
    season_name = db.Column(db.String(100))
    level = db.Column(db.String(100))
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            "org_id",
            "year",
            "month",
            "league_number",
            "season_number",
            "level",
            name="_org_year_month_league_season_level_uc",
        ),
    )


class OrgLeagueSeasonDates(db.Model):
    __tablename__ = "org_league_season_dates"
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    league_number = db.Column(db.Integer)
    season_number = db.Column(db.Integer)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "org_id", "league_number", "season_number", name="_org_league_season_uc_too"
        ),
    )


class NamesInOrgLeagueSeason(db.Model):
    __tablename__ = "names_in_org_league_season"
    id = db.Column(db.Integer, primary_key=True)
    org_league_season_id = db.Column(
        db.Integer, db.ForeignKey("org_league_season_dates.id")
    )
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "org_league_season_id",
            "first_name",
            "middle_name",
            "last_name",
            name="_org_league_season_name_uc",
        ),
    )


class NamesInTeams(db.Model):
    __tablename__ = "names_in_teams"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "team_id", "first_name", "middle_name", "last_name", name="_team_name_uc"
        ),
    )


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(100), unique=True)
    organization_name = db.Column(db.String(100), unique=True)
    website = db.Column(db.String(100), nullable=True)


class Penalty(db.Model):
    __tablename__ = "penalties"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    period = db.Column(db.String(10))  # Can be "1", "2", "3", "OT", etc.
    time = db.Column(db.String(10))  # For elapsed time format
    penalized_player_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    infraction = db.Column(db.String(100))
    penalty_minutes = db.Column(
        db.String(3)
    )  # Use this for numeric penalties like 2 minutes and GM, GS, M, PS, C, GR1
    penalty_start = db.Column(db.String(10))  # Elapsed time for start
    penalty_end = db.Column(
        db.String(10)
    )  # Elapsed time for end, can be NULL if unknown
    penalty_sequence_number = db.Column(db.Integer)
    __table_args__ = (
        db.UniqueConstraint(
            "game_id",
            "team_id",
            "penalty_sequence_number",
            name="_game_team_penalty_sequence_uc",
        ),
    )


class PlayerRole(db.Model):
    __tablename__ = "player_roles"
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"), primary_key=True)
    role_type = db.Column(
        db.String(10), primary_key=True
    )  # e.g., G (goalie), C (captain), A (alternate), S (substitute)
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (db.PrimaryKeyConstraint("team_id", "human_id", "role_type"),)


class RefDivision(db.Model):
    __tablename__ = "ref_divisions"
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"), primary_key=True)
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)


class RefereeName(db.Model):
    __tablename__ = "referee_names"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "first_name", "middle_name", "last_name", name="_referee_name_uc"
        ),
    )


class ScorekeeperDivision(db.Model):
    __tablename__ = "scorekeeper_divisions"
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"), primary_key=True)
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)


class ScorekeeperName(db.Model):
    __tablename__ = "scorekeeper_names"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    middle_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    __table_args__ = (
        db.UniqueConstraint(
            "first_name", "middle_name", "last_name", name="_scorekeeper_name_uc"
        ),
    )


class Season(db.Model):
    __tablename__ = "seasons"
    id = db.Column(db.Integer, primary_key=True)
    season_number = db.Column(db.Integer)
    season_name = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    league_number = db.Column(
        db.Integer
    )  # TODO: Deprecate usage and remove (get this info from League by league_id)
    league_id = db.Column(db.Integer, db.ForeignKey("leagues.id"))
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            "org_id", "league_number", "season_number", name="_org_league_season_uc"
        ),
    )


class Shootout(db.Model):
    __tablename__ = "shootout"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    shooting_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    shooter_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    goalie_id = db.Column(db.Integer, db.ForeignKey("humans.id"))
    has_scored = db.Column(
        db.Boolean
    )  # Reflect if goal was scored or not during shootout
    sequence_number = db.Column(db.Integer)
    __table_args__ = (
        db.UniqueConstraint(
            "game_id",
            "shooting_team_id",
            "sequence_number",
            name="_shootout_team_sequence_uc",
        ),
    )


class Team(db.Model):
    __tablename__ = "teams"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("org_id", "name", name="_org_team_name_uc"),)


class TeamDivision(db.Model):
    __tablename__ = "teams_divisions"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"))
    __table_args__ = (
        db.UniqueConstraint("team_id", "division_id", name="_team_division_uc"),
    )


class TeamInTTS(db.Model):
    __tablename__ = "teams_in_tts"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    tts_team_id = db.Column(db.Integer)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            "org_id", "team_id", "tts_team_id", name="_org_team_tts_uc"
        ),
    )


class RequestLog(db.Model):
    __tablename__ = "request_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_agent = db.Column(db.String, nullable=False)
    client_ip = db.Column(db.String, nullable=False)
    path = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    cgi_params = db.Column(db.String, nullable=True)
    response_time_ms = db.Column(
        db.Float, nullable=True
    )  # Response time in milliseconds


class GoalieSaves(db.Model):
    __tablename__ = "goalie_saves"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    goalie_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    saves_count = db.Column(db.Integer, nullable=False, default=0)
    shots_against = db.Column(db.Integer, nullable=False, default=0)
    goals_allowed = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (
        db.UniqueConstraint("game_id", "goalie_id", name="_game_goalie_saves_uc"),
    )


class ScorekeeperSaveQuality(db.Model):
    __tablename__ = "scorekeeper_save_quality"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    scorekeeper_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    total_saves_recorded = db.Column(db.Integer, nullable=False, default=0)
    max_saves_per_5sec = db.Column(
        db.Integer, nullable=False, default=0
    )  # Highest saves in any 5-second window
    max_saves_per_20sec = db.Column(
        db.Integer, nullable=False, default=0
    )  # Highest saves in any 20-second window
    saves_timestamps = db.Column(
        db.JSON, nullable=True
    )  # JSONB with home_saves/away_saves arrays of decisecond timestamps
    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "scorekeeper_id", name="_game_scorekeeper_quality_uc"
        ),
    )


class HumanEmbedding(db.Model):
    """Vector embeddings for semantic search of humans (players/referees/scorekeepers)."""
    __tablename__ = "human_embeddings"
    human_id = db.Column(db.Integer, db.ForeignKey("humans.id"), primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    embedding = db.Column(db.Text, nullable=False)  # pgvector type, stored as text
    updated_at = db.Column(db.DateTime, nullable=False)


class TeamEmbedding(db.Model):
    """Vector embeddings for semantic search of teams."""
    __tablename__ = "team_embeddings"
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), primary_key=True)
    team_name = db.Column(db.String(255), nullable=False)
    embedding = db.Column(db.Text, nullable=False)  # pgvector type, stored as text
    updated_at = db.Column(db.DateTime, nullable=False)


# # MANUAL AMENDS HAPPEN HERE :)
# from db_connection import create_session
# session = create_session("sharksice")

# # Update org_id to 1 for all records in the Division table
# session.query(Organization).filter(Organization.id == 3).update({Organization.alias: 'caha'})

# # Commit the changes to the database
# session.commit()


# print("Updated!")

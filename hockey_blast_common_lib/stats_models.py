from hockey_blast_common_lib.models import db
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import synonym

class BaseStatsHuman(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey('humans.id'), nullable=False)
    games_total = db.Column(db.Integer, default=0)
    games_total_rank = db.Column(db.Integer, default=0)
    games_skater = db.Column(db.Integer, default=0)
    games_skater_rank = db.Column(db.Integer, default=0)
    games_referee = db.Column(db.Integer, default=0)
    games_referee_rank = db.Column(db.Integer, default=0)
    games_scorekeeper = db.Column(db.Integer, default=0)
    games_scorekeeper_rank = db.Column(db.Integer, default=0)
    games_goalie = db.Column(db.Integer, default=0)
    games_goalie_rank = db.Column(db.Integer, default=0)
    total_in_rank = db.Column(db.Integer, default=0)
    skaters_in_rank = db.Column(db.Integer, default=0)
    goalies_in_rank = db.Column(db.Integer, default=0)
    referees_in_rank = db.Column(db.Integer, default=0)
    scorekeepers_in_rank = db.Column(db.Integer, default=0)
    first_game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    last_game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    first_game_id_skater = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    last_game_id_skater = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    first_game_id_goalie = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    last_game_id_goalie = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    first_game_id_referee = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    last_game_id_referee = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    first_game_id_scorekeeper = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)
    last_game_id_scorekeeper = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=True)

    @declared_attr
    def __table_args__(cls):
        return (
            db.UniqueConstraint('human_id', cls.get_aggregation_column(), name=f'_human_{cls.aggregation_type}_stats_uc1'),
            db.Index(f'idx_{cls.aggregation_type}_games_total1', cls.get_aggregation_column(), 'games_total'),
            db.Index(f'idx_{cls.aggregation_type}_games_skater1', cls.get_aggregation_column(), 'games_skater'),
            db.Index(f'idx_{cls.aggregation_type}_games_referee1', cls.get_aggregation_column(), 'games_referee'),
            db.Index(f'idx_{cls.aggregation_type}_games_scorekeeper1', cls.get_aggregation_column(), 'games_scorekeeper'),
            db.Index(f'idx_{cls.aggregation_type}_games_goalie1', cls.get_aggregation_column(), 'games_goalie')
        )

    @classmethod
    def get_aggregation_column(cls):
        raise NotImplementedError("Subclasses should implement this method to return the aggregation column name.")


class BaseStatsSkater(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey('humans.id'), nullable=False)
    games_played = db.Column(db.Integer, default=0)
    games_played_rank = db.Column(db.Integer, default=0)
    goals = db.Column(db.Integer, default=0)
    goals_rank = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    assists_rank = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    points_rank = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    penalties_rank = db.Column(db.Integer, default=0)
    gm_penalties = db.Column(db.Integer, default=0)  # New field for GM penalties
    gm_penalties_rank = db.Column(db.Integer, default=0)  # New field for GM penalties rank
    goals_per_game = db.Column(db.Float, default=0.0)
    goals_per_game_rank = db.Column(db.Integer, default=0)
    points_per_game = db.Column(db.Float, default=0.0)
    points_per_game_rank = db.Column(db.Integer, default=0)
    assists_per_game = db.Column(db.Float, default=0.0)
    assists_per_game_rank = db.Column(db.Integer, default=0)
    penalties_per_game = db.Column(db.Float, default=0.0)
    penalties_per_game_rank = db.Column(db.Integer, default=0)
    gm_penalties_per_game = db.Column(db.Float, default=0.0)
    gm_penalties_per_game_rank = db.Column(db.Integer, default=0)
    total_in_rank = db.Column(db.Integer, default=0)
    first_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))
    last_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))

    @declared_attr
    def __table_args__(cls):
        return (
            db.UniqueConstraint('human_id', cls.get_aggregation_column(), name=f'_human_{cls.aggregation_type}_uc_skater1'),
            db.Index(f'idx_{cls.aggregation_type}_goals_per_game3', cls.get_aggregation_column(), 'goals_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_points_per_game3', cls.get_aggregation_column(), 'points_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_assists_per_game3', cls.get_aggregation_column(), 'assists_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_penalties_per_game3', cls.get_aggregation_column(), 'penalties_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_gm_penalties_per_game3', cls.get_aggregation_column(), 'gm_penalties_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_games_played3', cls.get_aggregation_column(), 'games_played')
        )

    @classmethod
    def get_aggregation_column(cls):
        raise NotImplementedError("Subclasses should implement this method to return the aggregation column name.")

class BaseStatsGoalie(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey('humans.id'), nullable=False)
    games_played = db.Column(db.Integer, default=0)
    games_played_rank = db.Column(db.Integer, default=0)
    goals_allowed = db.Column(db.Integer, default=0)
    goals_allowed_rank = db.Column(db.Integer, default=0)
    goals_allowed_per_game = db.Column(db.Float, default=0.0)
    goals_allowed_per_game_rank = db.Column(db.Integer, default=0)
    shots_faced = db.Column(db.Integer, default=0)
    shots_faced_rank = db.Column(db.Integer, default=0)
    save_percentage = db.Column(db.Float, default=0.0)
    save_percentage_rank = db.Column(db.Integer, default=0)
    total_in_rank = db.Column(db.Integer, default=0)
    first_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))
    last_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))

    @declared_attr
    def __table_args__(cls):
        return (
            db.UniqueConstraint('human_id', cls.get_aggregation_column(), name=f'_human_{cls.aggregation_type}_uc_goalie1'),
            db.Index(f'idx_{cls.aggregation_type}_goals_allowed_per_game1', cls.get_aggregation_column(), 'goals_allowed_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_save_percentage1', cls.get_aggregation_column(), 'save_percentage'),
            db.Index(f'idx_{cls.aggregation_type}_shots_faced1', cls.get_aggregation_column(), 'shots_faced'),
            db.Index(f'idx_{cls.aggregation_type}_games_played_goalie1', cls.get_aggregation_column(), 'games_played'),
            db.Index(f'idx_{cls.aggregation_type}_goals_allowed1', cls.get_aggregation_column(), 'goals_allowed')
        )

    @classmethod
    def get_aggregation_column(cls):
        raise NotImplementedError("Subclasses should implement this method to return the aggregation column name.")

class BaseStatsReferee(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey('humans.id'), nullable=False)
    games_reffed = db.Column(db.Integer, default=0)
    games_reffed_rank = db.Column(db.Integer, default=0)
    penalties_given = db.Column(db.Integer, default=0)
    penalties_given_rank = db.Column(db.Integer, default=0)
    penalties_per_game = db.Column(db.Float, default=0.0)
    penalties_per_game_rank = db.Column(db.Integer, default=0)
    gm_given = db.Column(db.Integer, default=0)
    gm_given_rank = db.Column(db.Integer, default=0)
    gm_per_game = db.Column(db.Float, default=0.0)
    gm_per_game_rank = db.Column(db.Integer, default=0)
    total_in_rank = db.Column(db.Integer, default=0)
    first_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))
    last_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))

    @declared_attr
    def __table_args__(cls):
        return (
            db.UniqueConstraint('human_id', cls.get_aggregation_column(), name=f'_human_{cls.aggregation_type}_uc_referee1'),
            db.Index(f'idx_{cls.aggregation_type}_games_reffed1', cls.get_aggregation_column(), 'games_reffed'),
            db.Index(f'idx_{cls.aggregation_type}_penalties_given1', cls.get_aggregation_column(), 'penalties_given'),
            db.Index(f'idx_{cls.aggregation_type}_penalties_per_game1', cls.get_aggregation_column(), 'penalties_per_game'),
            db.Index(f'idx_{cls.aggregation_type}_gm_given1', cls.get_aggregation_column(), 'gm_given'),
            db.Index(f'idx_{cls.aggregation_type}_gm_per_game1', cls.get_aggregation_column(), 'gm_per_game')
        )

    @classmethod
    def get_aggregation_column(cls):
        raise NotImplementedError("Subclasses should implement this method to return the aggregation column name.")

class BaseStatsScorekeeper(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    human_id = db.Column(db.Integer, db.ForeignKey('humans.id'), nullable=False)
    games_recorded = db.Column(db.Integer, default=0)
    games_recorded_rank = db.Column(db.Integer, default=0)
    sog_given = db.Column(db.Integer, default=0)
    sog_given_rank = db.Column(db.Integer, default=0)
    sog_per_game = db.Column(db.Float, default=0.0)
    sog_per_game_rank = db.Column(db.Integer, default=0)
    total_in_rank = db.Column(db.Integer, default=0)
    first_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))
    last_game_id = db.Column(db.Integer, db.ForeignKey('games.id'))

    @declared_attr
    def __table_args__(cls):
        return (
            db.UniqueConstraint('human_id', cls.get_aggregation_column(), name=f'_human_{cls.aggregation_type}_uc_scorekeeper1'),
            db.Index(f'idx_{cls.aggregation_type}_games_recorded1', cls.get_aggregation_column(), 'games_recorded'),
            db.Index(f'idx_{cls.aggregation_type}_sog_given1', cls.get_aggregation_column(), 'sog_given'),
            db.Index(f'idx_{cls.aggregation_type}_sog_per_game1', cls.get_aggregation_column(), 'sog_per_game')
        )

    @classmethod
    def get_aggregation_column(cls):
        raise NotImplementedError("Subclasses should implement this method to return the aggregation column name.")

class OrgStatsHuman(BaseStatsHuman):
    __tablename__ = 'org_stats_human'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsHuman(BaseStatsHuman):
    __tablename__ = 'division_stats_human'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class LevelStatsHuman(BaseStatsHuman):
    __tablename__ = 'level_stats_human'
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    aggregation_id = synonym('level_id')

    @declared_attr
    def aggregation_type(cls):
        return 'level'

    @classmethod
    def get_aggregation_column(cls):
        return 'level_id'

class OrgStatsSkater(BaseStatsSkater):
    __tablename__ = 'org_stats_skater'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsSkater(BaseStatsSkater):
    __tablename__ = 'division_stats_skater'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class LevelStatsSkater(BaseStatsSkater):
    __tablename__ = 'level_stats_skater'
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    aggregation_id = synonym('level_id')

    @declared_attr
    def aggregation_type(cls):
        return 'level'

    @classmethod
    def get_aggregation_column(cls):
        return 'level_id'


class OrgStatsGoalie(BaseStatsGoalie):
    __tablename__ = 'org_stats_goalie'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsGoalie(BaseStatsGoalie):
    __tablename__ = 'division_stats_goalie'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class LevelStatsGoalie(BaseStatsGoalie):
    __tablename__ = 'level_stats_goalie'
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    aggregation_id = synonym('level_id')

    @declared_attr
    def aggregation_type(cls):
        return 'level'

    @classmethod
    def get_aggregation_column(cls):
        return 'level_id'


class OrgStatsReferee(BaseStatsReferee):
    __tablename__ = 'org_stats_referee'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsReferee(BaseStatsReferee):
    __tablename__ = 'division_stats_referee'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class LevelStatsReferee(BaseStatsReferee):
    __tablename__ = 'level_stats_referee'
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    aggregation_id = synonym('level_id')

    @declared_attr
    def aggregation_type(cls):
        return 'level'

    @classmethod
    def get_aggregation_column(cls):
        return 'level_id'


class OrgStatsScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'org_stats_scorekeeper'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'division_stats_scorekeeper'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class OrgStatsDailyHuman(BaseStatsHuman):
    __tablename__ = 'org_stats_daily_human'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'
    
    @declared_attr
    def aggregation_type(cls):
        return 'org_daily'

class OrgStatsWeeklyHuman(BaseStatsHuman):
    __tablename__ = 'org_stats_weekly_human'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

    @declared_attr
    def aggregation_type(cls):
        return 'org_weekly'

class DivisionStatsDailyHuman(BaseStatsHuman):
    __tablename__ = 'division_stats_daily_human'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

    @declared_attr
    def aggregation_type(cls):
        return 'division_daily'

class DivisionStatsWeeklyHuman(BaseStatsHuman):
    __tablename__ = 'division_stats_weekly_human'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

    @declared_attr
    def aggregation_type(cls):
        return 'division_weekly'

class OrgStatsDailySkater(BaseStatsSkater):
    __tablename__ = 'org_stats_daily_skater'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class OrgStatsWeeklySkater(BaseStatsSkater):
    __tablename__ = 'org_stats_weekly_skater'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsDailySkater(BaseStatsSkater):
    __tablename__ = 'division_stats_daily_skater'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class DivisionStatsWeeklySkater(BaseStatsSkater):
    __tablename__ = 'division_stats_weekly_skater'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class OrgStatsDailyGoalie(BaseStatsGoalie):
    __tablename__ = 'org_stats_daily_goalie'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class OrgStatsWeeklyGoalie(BaseStatsGoalie):
    __tablename__ = 'org_stats_weekly_goalie'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsDailyGoalie(BaseStatsGoalie):
    __tablename__ = 'division_stats_daily_goalie'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class DivisionStatsWeeklyGoalie(BaseStatsGoalie):
    __tablename__ = 'division_stats_weekly_goalie'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class OrgStatsDailyReferee(BaseStatsReferee):
    __tablename__ = 'org_stats_daily_referee'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class OrgStatsWeeklyReferee(BaseStatsReferee):
    __tablename__ = 'org_stats_weekly_referee'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsDailyReferee(BaseStatsReferee):
    __tablename__ = 'division_stats_daily_referee'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class DivisionStatsWeeklyReferee(BaseStatsReferee):
    __tablename__ = 'division_stats_weekly_referee'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class OrgStatsDailyScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'org_stats_daily_scorekeeper'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class OrgStatsWeeklyScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'org_stats_weekly_scorekeeper'
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    aggregation_id = synonym('org_id')

    @declared_attr
    def aggregation_type(cls):
        return 'org_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'org_id'

class DivisionStatsDailyScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'division_stats_daily_scorekeeper'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_daily'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class DivisionStatsWeeklyScorekeeper(BaseStatsScorekeeper):
    __tablename__ = 'division_stats_weekly_scorekeeper'
    division_id = db.Column(db.Integer, db.ForeignKey('divisions.id'), nullable=False)
    aggregation_id = synonym('division_id')

    @declared_attr
    def aggregation_type(cls):
        return 'division_weekly'

    @classmethod
    def get_aggregation_column(cls):
        return 'division_id'

class LevelsGraphEdge(db.Model):
    __tablename__ = 'levels_graph_edges'
    id = db.Column(db.Integer, primary_key=True)
    from_level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    to_level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    n_connections = db.Column(db.Integer, nullable=False)
    ppg_ratio = db.Column(db.Float, nullable=False)
    n_games = db.Column(db.Integer, nullable=False)  # New field to store the number of games

    __table_args__ = (
        db.UniqueConstraint('from_level_id', 'to_level_id', name='_from_to_level_uc'),
    )

class SkillPropagationCorrelation(db.Model):
    __tablename__ = 'skill_propagation_correlation'
    id = db.Column(db.Integer, primary_key=True)
    skill_value_from = db.Column(db.Float, nullable=False)
    skill_value_to = db.Column(db.Float, nullable=False)
    ppg_ratio = db.Column(db.Float, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('skill_value_from', 'skill_value_to', 'ppg_ratio', name='_skill_value_ppg_ratio_uc'),
    )

# How PPG changes with INCREASING SKILL VALUES
class SkillValuePPGRatio(db.Model):
    __tablename__ = 'skill_value_ppg_ratios'
    id = db.Column(db.Integer, primary_key=True)
    from_skill_value = db.Column(db.Float, nullable=False)
    to_skill_value = db.Column(db.Float, nullable=False)
    ppg_ratio = db.Column(db.Float, nullable=False)
    n_games = db.Column(db.Integer, nullable=False)  # New field to store the sum of games

    __table_args__ = (
        db.UniqueConstraint('from_skill_value', 'to_skill_value', name='_from_to_skill_value_uc'),
    )

from hockey_blast_common_lib.models import db


class H2HStats(db.Model):
    __tablename__ = "h2h_stats"
    id = db.Column(db.Integer, primary_key=True)
    human1_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    human2_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    # Always store with human1_id < human2_id for uniqueness
    __table_args__ = (
        db.UniqueConstraint("human1_id", "human2_id", name="_h2h_human_pair_uc"),
        db.Index(
            "ix_h2h_human_pair", "human1_id", "human2_id"
        ),  # Composite index for fast lookup
    )

    # General
    games_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where both played (any role, any team)
    games_against = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where both played on opposing teams
    games_tied_together = db.Column(db.Integer, default=0, nullable=False)
    games_tied_against = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games against each other that ended in a tie
    wins_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games both played on same team and won
    losses_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games both played on same team and lost
    h1_wins_vs_h2 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games h1's team won vs h2's team
    h2_wins_vs_h1 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games h2's team won vs h1's team

    # Role-specific counts
    games_h1_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where h1 was a goalie and h2 played
    games_h2_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where h2 was a goalie and h1 played
    games_h1_ref = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where h1 was a referee and h2 played
    games_h2_ref = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where h2 was a referee and h1 played
    games_both_referees = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games where both were referees

    # Goals/Assists/Penalties (when both played)
    goals_h1_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals by h1 when both played
    goals_h2_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals by h2 when both played
    assists_h1_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Assists by h1 when both played
    assists_h2_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Assists by h2 when both played
    penalties_h1_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Penalties on h1 when both played
    penalties_h2_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # Penalties on h2 when both played
    gm_penalties_h1_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # GM penalties on h1 when both played
    gm_penalties_h2_when_together = db.Column(
        db.Integer, default=0, nullable=False
    )  # GM penalties on h2 when both played

    # Goalie/Skater head-to-head (when one is goalie, other is skater on opposing team)
    h1_goalie_h2_scorer_goals = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals scored by h2 against h1 as goalie
    h2_goalie_h1_scorer_goals = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals scored by h1 against h2 as goalie
    shots_faced_h1_goalie_vs_h2 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Shots faced by h1 as goalie vs h2 as skater
    shots_faced_h2_goalie_vs_h1 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Shots faced by h2 as goalie vs h1 as skater
    goals_allowed_h1_goalie_vs_h2 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals allowed by h1 as goalie vs h2 as skater
    goals_allowed_h2_goalie_vs_h1 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Goals allowed by h2 as goalie vs h1 as skater
    save_percentage_h1_goalie_vs_h2 = db.Column(
        db.Float, default=0.0, nullable=False
    )  # Save % by h1 as goalie vs h2 as skater
    save_percentage_h2_goalie_vs_h1 = db.Column(
        db.Float, default=0.0, nullable=False
    )  # Save % by h2 as goalie vs h1 as skater

    # Referee/Player
    h1_ref_h2_player_games = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games h1 was referee, h2 was player
    h2_ref_h1_player_games = db.Column(
        db.Integer, default=0, nullable=False
    )  # Games h2 was referee, h1 was player
    h1_ref_penalties_on_h2 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Penalties given by h1 (as ref) to h2
    h2_ref_penalties_on_h1 = db.Column(
        db.Integer, default=0, nullable=False
    )  # Penalties given by h2 (as ref) to h1
    h1_ref_gm_penalties_on_h2 = db.Column(
        db.Integer, default=0, nullable=False
    )  # GM penalties given by h1 (as ref) to h2
    h2_ref_gm_penalties_on_h1 = db.Column(
        db.Integer, default=0, nullable=False
    )  # GM penalties given by h2 (as ref) to h1

    # Both referees (when both are referees in the same game)
    penalties_given_both_refs = db.Column(
        db.Integer, default=0, nullable=False
    )  # Total penalties given by both
    gm_penalties_given_both_refs = db.Column(
        db.Integer, default=0, nullable=False
    )  # Total GM penalties given by both

    # Shootouts
    h1_shootout_attempts_vs_h2_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # h1 shootout attempts vs h2 as goalie
    h1_shootout_goals_vs_h2_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # h1 shootout goals vs h2 as goalie
    h2_shootout_attempts_vs_h1_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # h2 shootout attempts vs h1 as goalie
    h2_shootout_goals_vs_h1_goalie = db.Column(
        db.Integer, default=0, nullable=False
    )  # h2 shootout goals vs h1 as goalie

    # First and last game IDs where both were present
    first_game_id = db.Column(
        db.Integer, nullable=False
    )  # Game.id of the first game where both were present
    last_game_id = db.Column(
        db.Integer, nullable=False
    )  # Game.id of the most recent game where both were present


class H2HStatsMeta(db.Model):
    __tablename__ = "h2h_stats_meta"
    id = db.Column(db.Integer, primary_key=True)
    last_run_timestamp = db.Column(
        db.DateTime, nullable=True
    )  # When the h2h stats were last updated
    last_processed_game_id = db.Column(
        db.Integer, nullable=True
    )  # Game.id of the latest processed game


class SkaterToSkaterStats(db.Model):
    __tablename__ = "skater_to_skater_stats"
    id = db.Column(db.Integer, primary_key=True)
    skater1_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    skater2_id = db.Column(db.Integer, db.ForeignKey("humans.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("skater1_id", "skater2_id", name="_s2s_skater_pair_uc"),
        db.Index("ix_s2s_skater_pair", "skater1_id", "skater2_id"),
    )

    # General stats
    games_against = db.Column(db.Integer, default=0, nullable=False)
    games_tied_against = db.Column(db.Integer, default=0, nullable=False)
    skater1_wins_vs_skater2 = db.Column(db.Integer, default=0, nullable=False)
    skater2_wins_vs_skater1 = db.Column(db.Integer, default=0, nullable=False)

    # Cumulative stats
    skater1_goals_against_skater2 = db.Column(db.Integer, default=0, nullable=False)
    skater2_goals_against_skater1 = db.Column(db.Integer, default=0, nullable=False)
    skater1_assists_against_skater2 = db.Column(db.Integer, default=0, nullable=False)
    skater2_assists_against_skater1 = db.Column(db.Integer, default=0, nullable=False)
    skater1_penalties_against_skater2 = db.Column(db.Integer, default=0, nullable=False)
    skater2_penalties_against_skater1 = db.Column(db.Integer, default=0, nullable=False)


class SkaterToSkaterStatsMeta(db.Model):
    __tablename__ = "skater_to_skater_stats_meta"
    id = db.Column(db.Integer, primary_key=True)
    last_run_timestamp = db.Column(db.DateTime, nullable=True)
    last_processed_game_id = db.Column(db.Integer, nullable=True)

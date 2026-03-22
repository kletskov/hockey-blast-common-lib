"""
merge_humans — merge a secondary Human record into a primary Human record.

This function mirrors link_humans() from hockey-blast-pipeline but uses only
hockey_blast_common_lib imports, making it safe to call from any consumer
(e.g. the PICKS sportsbook) without requiring pipeline dependencies.
"""

import logging
from sqlalchemy.exc import IntegrityError

from hockey_blast_common_lib.h2h_models import H2HStats, SkaterToSkaterStats
from hockey_blast_common_lib.models import (
    Game,
    GameRoster,
    Goal,
    GoalieSaves,
    Human,
    HumanAlias,
    HumanEmbedding,
    HumanGames,
    HumanInTTS,
    HumansInLevels,
    Penalty,
    PlayerRole,
    RefDivision,
    ScorekeeperDivision,
    ScorekeeperSaveQuality,
    Shootout,
)
from hockey_blast_common_lib.stats_models import (
    DivisionStatsDailyGoalie,
    DivisionStatsDailyHuman,
    DivisionStatsDailyReferee,
    DivisionStatsDailySkater,
    DivisionStatsGoalie,
    DivisionStatsGoalieTeam,
    DivisionStatsHuman,
    DivisionStatsReferee,
    DivisionStatsSkater,
    DivisionStatsSkaterTeam,
    DivisionStatsWeeklyGoalie,
    DivisionStatsWeeklyHuman,
    DivisionStatsWeeklyReferee,
    DivisionStatsWeeklySkater,
    GameStatsGoalie,
    GameStatsSkater,
    LevelStatsGoalie,
    LevelStatsHuman,
    LevelStatsReferee,
    LevelStatsSkater,
    OrgStatsDailyGoalie,
    OrgStatsDailyHuman,
    OrgStatsDailyReferee,
    OrgStatsDailyScorekeeper,
    OrgStatsDailySkater,
    OrgStatsGoalie,
    OrgStatsGoalieTeam,
    OrgStatsHuman,
    OrgStatsReferee,
    OrgStatsScorekeeper,
    OrgStatsSkater,
    OrgStatsSkaterTeam,
    OrgStatsWeeklyGoalie,
    OrgStatsWeeklyHuman,
    OrgStatsWeeklyReferee,
    OrgStatsWeeklyScorekeeper,
    OrgStatsWeeklySkater,
)

logger = logging.getLogger(__name__)


def _delete_human(session, human_id: int) -> None:
    """
    Delete a human and all remaining aliases from the database.
    This is inlined from pipeline's human_utils.delete_human.
    """
    session.query(HumanAlias).filter_by(human_id=human_id).delete()
    session.query(Human).filter_by(id=human_id).delete()
    session.commit()


def merge_humans(session, primary_human_id: int, secondary_human_id: int) -> None:
    """
    Merge secondary_human_id into primary_human_id.

    All references (game rosters, goals, stats, aliases, etc.) are re-pointed
    from the secondary to the primary.  The secondary Human record is then
    deleted.  Stats for the secondary are removed so they can be regenerated
    for the primary by the pipeline.

    Args:
        session: SQLAlchemy session connected to the hockey_blast database.
        primary_human_id: ID of the Human record to keep.
        secondary_human_id: ID of the Human record to merge away and delete.
    """
    primary_human = session.query(Human).filter_by(id=primary_human_id).first()
    if not primary_human:
        logger.warning(
            "merge_humans: primary human %d not found — aborting", primary_human_id
        )
        return

    # ── GameRoster ────────────────────────────────────────────────────────────
    try:
        secondary_roster_entries = (
            session.query(GameRoster).filter_by(human_id=secondary_human_id).all()
        )
        for entry in secondary_roster_entries:
            primary_entry = (
                session.query(GameRoster)
                .filter_by(game_id=entry.game_id, human_id=primary_human_id)
                .first()
            )
            if primary_entry:
                session.delete(entry)
            else:
                entry.human_id = primary_human_id
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.warning(
            "merge_humans: IntegrityError on GameRoster for secondary=%d — aborting merge",
            secondary_human_id,
        )
        return

    # ── PlayerRole ────────────────────────────────────────────────────────────
    try:
        session.query(PlayerRole).filter_by(human_id=secondary_human_id).update(
            {PlayerRole.human_id: primary_human_id}
        )
    except IntegrityError:
        session.rollback()
        # Fallback: merge date ranges and delete secondary role
        primary_role = (
            session.query(PlayerRole).filter_by(human_id=primary_human_id).first()
        )
        secondary_role = (
            session.query(PlayerRole).filter_by(human_id=secondary_human_id).first()
        )
        if primary_role and secondary_role:
            primary_role.first_date = min(primary_role.first_date, secondary_role.first_date)
            primary_role.last_date = max(primary_role.last_date, secondary_role.last_date)
            session.query(PlayerRole).filter_by(human_id=secondary_human_id).delete()

    session.commit()

    # ── Game references ───────────────────────────────────────────────────────
    session.query(Game).filter_by(scorekeeper_id=secondary_human_id).update(
        {Game.scorekeeper_id: primary_human_id}
    )
    session.query(Game).filter_by(referee_1_id=secondary_human_id).update(
        {Game.referee_1_id: primary_human_id}
    )
    session.query(Game).filter_by(referee_2_id=secondary_human_id).update(
        {Game.referee_2_id: primary_human_id}
    )
    session.query(Game).filter_by(home_goalie_id=secondary_human_id).update(
        {Game.home_goalie_id: primary_human_id}
    )
    session.query(Game).filter_by(visitor_goalie_id=secondary_human_id).update(
        {Game.visitor_goalie_id: primary_human_id}
    )

    # ── Goal references ───────────────────────────────────────────────────────
    session.query(Goal).filter_by(goal_scorer_id=secondary_human_id).update(
        {Goal.goal_scorer_id: primary_human_id}
    )
    session.query(Goal).filter_by(assist_1_id=secondary_human_id).update(
        {Goal.assist_1_id: primary_human_id}
    )
    session.query(Goal).filter_by(assist_2_id=secondary_human_id).update(
        {Goal.assist_2_id: primary_human_id}
    )
    session.query(Goal).filter_by(goalie_id=secondary_human_id).update(
        {Goal.goalie_id: primary_human_id}
    )

    # ── Other game event tables ───────────────────────────────────────────────
    session.query(GoalieSaves).filter_by(goalie_id=secondary_human_id).update(
        {GoalieSaves.goalie_id: primary_human_id}
    )
    session.query(ScorekeeperSaveQuality).filter_by(
        scorekeeper_id=secondary_human_id
    ).update({ScorekeeperSaveQuality.scorekeeper_id: primary_human_id})
    session.query(HumanInTTS).filter_by(human_id=secondary_human_id).update(
        {HumanInTTS.human_id: primary_human_id}
    )
    session.query(HumansInLevels).filter_by(human_id=secondary_human_id).update(
        {HumansInLevels.human_id: primary_human_id}
    )
    session.query(Penalty).filter_by(penalized_player_id=secondary_human_id).update(
        {Penalty.penalized_player_id: primary_human_id}
    )
    session.query(RefDivision).filter_by(human_id=secondary_human_id).update(
        {RefDivision.human_id: primary_human_id}
    )
    session.query(ScorekeeperDivision).filter_by(human_id=secondary_human_id).update(
        {ScorekeeperDivision.human_id: primary_human_id}
    )
    session.query(Shootout).filter_by(shooter_id=secondary_human_id).update(
        {Shootout.shooter_id: primary_human_id}
    )
    session.query(Shootout).filter_by(goalie_id=secondary_human_id).update(
        {Shootout.goalie_id: primary_human_id}
    )

    # ── Aliases ───────────────────────────────────────────────────────────────
    secondary_aliases = (
        session.query(HumanAlias).filter_by(human_id=secondary_human_id).all()
    )
    if secondary_aliases:
        for alias in secondary_aliases:
            existing_alias = (
                session.query(HumanAlias)
                .filter_by(
                    human_id=primary_human_id,
                    first_name=alias.first_name,
                    middle_name=alias.middle_name,
                    last_name=alias.last_name,
                    suffix=alias.suffix,
                )
                .first()
            )
            if not existing_alias:
                new_alias = HumanAlias(
                    human_id=primary_human_id,
                    first_name=alias.first_name,
                    middle_name=alias.middle_name,
                    last_name=alias.last_name,
                    suffix=alias.suffix,
                    first_date=alias.first_date,
                    last_date=alias.last_date,
                )
                session.add(new_alias)
    else:
        # No aliases: create one from the secondary human's own name
        secondary_human = session.query(Human).filter_by(id=secondary_human_id).first()
        if secondary_human:
            existing_alias = (
                session.query(HumanAlias)
                .filter_by(
                    human_id=primary_human_id,
                    first_name=secondary_human.first_name,
                    middle_name=secondary_human.middle_name,
                    last_name=secondary_human.last_name,
                    suffix=secondary_human.suffix,
                )
                .first()
            )
            if not existing_alias:
                new_alias = HumanAlias(
                    human_id=primary_human_id,
                    first_name=secondary_human.first_name,
                    middle_name=secondary_human.middle_name,
                    last_name=secondary_human.last_name,
                    suffix=secondary_human.suffix,
                    first_date=secondary_human.first_date,
                    last_date=secondary_human.last_date,
                )
                session.add(new_alias)

    session.commit()

    # ── Delete stats for secondary (regenerated by pipeline for primary) ──────
    session.query(OrgStatsHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsSkater).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsSkaterTeam).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsGoalieTeam).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsReferee).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsScorekeeper).filter_by(human_id=secondary_human_id).delete()

    session.query(OrgStatsDailyHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsDailySkater).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsDailyGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsDailyReferee).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsDailyScorekeeper).filter_by(human_id=secondary_human_id).delete()

    session.query(OrgStatsWeeklyHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsWeeklySkater).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsWeeklyGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsWeeklyReferee).filter_by(human_id=secondary_human_id).delete()
    session.query(OrgStatsWeeklyScorekeeper).filter_by(human_id=secondary_human_id).delete()

    session.query(DivisionStatsHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsSkater).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsSkaterTeam).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsGoalieTeam).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsReferee).filter_by(human_id=secondary_human_id).delete()

    session.query(DivisionStatsDailyHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsDailySkater).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsDailyGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsDailyReferee).filter_by(human_id=secondary_human_id).delete()

    session.query(DivisionStatsWeeklyHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsWeeklySkater).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsWeeklyGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(DivisionStatsWeeklyReferee).filter_by(human_id=secondary_human_id).delete()

    session.query(LevelStatsHuman).filter_by(human_id=secondary_human_id).delete()
    session.query(LevelStatsSkater).filter_by(human_id=secondary_human_id).delete()
    session.query(LevelStatsGoalie).filter_by(human_id=secondary_human_id).delete()
    session.query(LevelStatsReferee).filter_by(human_id=secondary_human_id).delete()

    session.query(GameStatsSkater).filter_by(human_id=secondary_human_id).delete()
    session.query(GameStatsGoalie).filter_by(human_id=secondary_human_id).delete()

    session.query(H2HStats).filter_by(human1_id=secondary_human_id).delete()
    session.query(H2HStats).filter_by(human2_id=secondary_human_id).delete()
    session.query(SkaterToSkaterStats).filter_by(skater1_id=secondary_human_id).delete()
    session.query(SkaterToSkaterStats).filter_by(skater2_id=secondary_human_id).delete()

    session.query(HumanGames).filter_by(human_id=secondary_human_id).delete()
    session.query(HumanEmbedding).filter_by(human_id=secondary_human_id).delete()

    session.commit()

    # ── Delete the secondary human record (and any remaining aliases) ─────────
    _delete_human(session, secondary_human_id)

    logger.info(
        "merge_humans: merged human %d into %d successfully",
        secondary_human_id,
        primary_human_id,
    )

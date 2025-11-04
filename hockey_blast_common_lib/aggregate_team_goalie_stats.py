"""
Aggregate goalie statistics by team.

This module aggregates goalie statistics for each team, counting only games
where the goalie was on that specific team (using GameRoster.team_id).

Key difference from regular aggregation:
- Aggregates by (aggregation_id, team_id, human_id) instead of just (aggregation_id, human_id)
- Filters to only games where GameRoster.team_id matches the target team
- Stores results in OrgStatsGoalieTeam / DivisionStatsGoalieTeam

"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
from sqlalchemy import func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import (
    Division,
    Game,
    GameRoster,
    GoalieSaves,
    Human,
    Organization,
    Team,
)
from hockey_blast_common_lib.options import (
    MIN_GAMES_FOR_DIVISION_STATS,
    MIN_GAMES_FOR_ORG_STATS,
)
from hockey_blast_common_lib.progress_utils import create_progress_tracker
from hockey_blast_common_lib.stats_models import (
    DivisionStatsGoalieTeam,
    OrgStatsGoalieTeam,
)
from hockey_blast_common_lib.utils import (
    calculate_percentile_value,
    get_non_human_ids,
    get_percentile_human,
)

# Import status constants for game filtering
FINAL_STATUS = "Final"
FINAL_SO_STATUS = "Final(SO)"
FORFEIT_STATUS = "FORFEIT"
NOEVENTS_STATUS = "NOEVENTS"


def aggregate_team_goalie_stats(session, aggregation_type, aggregation_id):
    """
    Aggregate goalie stats by team for an organization or division.

    For each team in the aggregation scope, calculates stats for all goalies
    who played for that team, counting only games where they were on that team.

    Args:
        session: Database session
        aggregation_type: "org" or "division"
        aggregation_id: ID of the organization or division
    """
    human_ids_to_filter = get_non_human_ids(session)

    # Determine aggregation details
    if aggregation_type == "org":
        StatsModel = OrgStatsGoalieTeam
        min_games = MIN_GAMES_FOR_ORG_STATS
        aggregation_name = (
            session.query(Organization)
            .filter(Organization.id == aggregation_id)
            .first()
            .organization_name
        )
        filter_condition = Game.org_id == aggregation_id
    elif aggregation_type == "division":
        StatsModel = DivisionStatsGoalieTeam
        min_games = MIN_GAMES_FOR_DIVISION_STATS
        aggregation_name = (
            session.query(Division).filter(Division.id == aggregation_id).first().level
        )
        filter_condition = Game.division_id == aggregation_id
    else:
        raise ValueError(f"Invalid aggregation type: {aggregation_type}")

    print(f"Aggregating team goalie stats for {aggregation_name}...")

    # Delete existing stats for this aggregation
    session.query(StatsModel).filter(StatsModel.aggregation_id == aggregation_id).delete()
    session.commit()

    # Get all teams in this aggregation scope
    if aggregation_type == "org":
        teams_query = (
            session.query(Team.id, Team.name)
            .join(Game, (Game.home_team_id == Team.id) | (Game.visitor_team_id == Team.id))
            .filter(Game.org_id == aggregation_id)
            .distinct()
        )
    else:  # division
        teams_query = (
            session.query(Team.id, Team.name)
            .join(Game, (Game.home_team_id == Team.id) | (Game.visitor_team_id == Team.id))
            .filter(Game.division_id == aggregation_id)
            .distinct()
        )

    teams = teams_query.all()
    print(f"Found {len(teams)} teams in {aggregation_name}")

    # Process each team
    progress = create_progress_tracker(len(teams), description="Processing teams")
    for team_id, team_name in teams:
        progress.update(1)

        # Aggregate stats for goalies on this team
        # Filter to only games where goalies were on THIS team
        games_played_query = (
            session.query(
                GameRoster.human_id,
                func.count(Game.id).label("games_played"),
                func.count(Game.id).label("games_participated"),
                func.count(Game.id).label("games_with_stats"),
                func.array_agg(Game.id).label("game_ids"),
            )
            .join(Game, Game.id == GameRoster.game_id)
            .filter(
                GameRoster.team_id == team_id,  # KEY: Filter by team
                GameRoster.role.ilike("g"),  # Only goalies
                GameRoster.human_id.notin_(human_ids_to_filter),
                Game.status.in_([FINAL_STATUS, FINAL_SO_STATUS, FORFEIT_STATUS, NOEVENTS_STATUS]),
                filter_condition,  # org_id or division_id filter
            )
            .group_by(GameRoster.human_id)
            .having(func.count(Game.id) >= min_games)
        )

        games_played_data = games_played_query.all()
        if not games_played_data:
            continue  # No goalies met minimum games for this team

        # Create stats dictionary
        stats_dict = {}
        for row in games_played_data:
            stats_dict[row.human_id] = {
                "games_played": row.games_played,
                "games_participated": row.games_participated,
                "games_with_stats": row.games_with_stats,
                "game_ids": row.game_ids,
                "first_game_id": row.game_ids[0] if row.game_ids else None,
                "last_game_id": row.game_ids[-1] if row.game_ids else None,
            }

        # Aggregate goals allowed and shots faced from GoalieSaves table
        goalie_saves_query = (
            session.query(
                GameRoster.human_id,
                func.sum(GoalieSaves.goals_allowed).label("goals_allowed"),
                func.sum(GoalieSaves.shots_against).label("shots_faced"),
            )
            .join(Game, Game.id == GameRoster.game_id)
            .join(
                GoalieSaves,
                (GoalieSaves.game_id == Game.id) & (GoalieSaves.goalie_id == GameRoster.human_id),
            )
            .filter(
                GameRoster.team_id == team_id,  # KEY: Filter by team
                GameRoster.role.ilike("g"),
                GameRoster.human_id.in_(stats_dict.keys()),
                Game.status.in_([FINAL_STATUS, FINAL_SO_STATUS]),
                filter_condition,
            )
            .group_by(GameRoster.human_id)
        )

        for row in goalie_saves_query.all():
            if row.human_id in stats_dict:
                stats_dict[row.human_id]["goals_allowed"] = row.goals_allowed or 0
                stats_dict[row.human_id]["shots_faced"] = row.shots_faced or 0

        # Calculate per-game averages and save percentage
        for human_id, stats in stats_dict.items():
            games_with_stats = stats.get("games_with_stats", 0)
            goals_allowed = stats.get("goals_allowed", 0)
            shots_faced = stats.get("shots_faced", 0)

            if games_with_stats > 0:
                stats["goals_allowed_per_game"] = goals_allowed / games_with_stats
            else:
                stats["goals_allowed_per_game"] = 0.0

            if shots_faced > 0:
                saves = shots_faced - goals_allowed
                stats["save_percentage"] = saves / shots_faced
            else:
                stats["save_percentage"] = 0.0

        # Insert stats for each goalie on this team
        for human_id, stats in stats_dict.items():
            goalie_stat = StatsModel(
                aggregation_id=aggregation_id,
                team_id=team_id,
                human_id=human_id,
                games_played=stats.get("games_played", 0),
                games_participated=stats.get("games_participated", 0),
                games_with_stats=stats.get("games_with_stats", 0),
                goals_allowed=stats.get("goals_allowed", 0),
                shots_faced=stats.get("shots_faced", 0),
                goals_allowed_per_game=stats.get("goals_allowed_per_game", 0.0),
                save_percentage=stats.get("save_percentage", 0.0),
                total_in_rank=len(stats_dict),
                first_game_id=stats.get("first_game_id"),
                last_game_id=stats.get("last_game_id"),
                # Initialize rank fields to 0 (not calculated for team stats)
                games_played_rank=0,
                games_participated_rank=0,
                games_with_stats_rank=0,
                goals_allowed_rank=0,
                shots_faced_rank=0,
                goals_allowed_per_game_rank=0,
                save_percentage_rank=0,
            )
            session.add(goalie_stat)

    session.commit()
    progress.finish()
    print(f"✓ Team goalie stats aggregation complete for {aggregation_name}")


def run_aggregate_team_goalie_stats():
    """
    Run team goalie stats aggregation for all organizations and divisions.
    """
    from hockey_blast_common_lib.utils import get_all_division_ids_for_org

    session = create_session("boss")

    # Get all org_id present in the Organization table
    org_ids = session.query(Organization.id).all()
    org_ids = [org_id[0] for org_id in org_ids]

    for org_id in org_ids:
        # Aggregate for organization level
        aggregate_team_goalie_stats(session, "org", org_id)

        # Aggregate for all divisions in this organization
        division_ids = get_all_division_ids_for_org(session, org_id)
        for division_id in division_ids:
            aggregate_team_goalie_stats(session, "division", division_id)

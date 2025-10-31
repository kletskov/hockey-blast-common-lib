import os
import sys
from datetime import datetime

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import types
from sqlalchemy.sql import func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.h2h_models import H2HStats, H2HStatsMeta
from hockey_blast_common_lib.models import Game, GameRoster, Goal, Penalty
from hockey_blast_common_lib.progress_utils import create_progress_tracker

# Max games to process (set to None to process all)
MAX_GAMES_TO_PROCESS = None  # Set to None to process all games


def aggregate_h2h_stats():
    session = create_session("boss")
    meta = None  # session.query(H2HStatsMeta).order_by(H2HStatsMeta.id.desc()).first()
    h2h_stats_dict = {}  # (h1, h2) -> H2HStats instance
    if (
        meta is None
        or meta.last_run_timestamp is None
        or meta.last_processed_game_id is None
    ):
        # Full run: delete all existing stats and process all games
        session.query(H2HStats).delete()
        session.commit()
        games_query = session.query(Game).order_by(Game.date, Game.time, Game.id)
        print(
            "No previous run found, deleted all existing H2H stats, processing all games..."
        )
    else:
        # Incremental: only process games after last processed
        # Load all existing stats into memory
        for stat in session.query(H2HStats).all():
            h2h_stats_dict[(stat.human1_id, stat.human2_id)] = stat
        last_game = (
            session.query(Game).filter(Game.id == meta.last_processed_game_id).first()
        )
        if last_game:
            last_dt = datetime.combine(last_game.date, last_game.time)
            games_query = (
                session.query(Game)
                .filter(
                    func.cast(func.concat(Game.date, " ", Game.time), types.TIMESTAMP())
                    > last_dt
                )
                .order_by(Game.date, Game.time, Game.id)
            )
            print(
                f"Resuming from game after id {meta.last_processed_game_id} ({last_dt})..."
            )
        else:
            games_query = session.query(Game).order_by(Game.date, Game.time, Game.id)
            print("Previous game id not found, processing all games...")

    total_games = games_query.count()
    print(f"Total games to process: {total_games}")

    # Create progress tracker
    progress = create_progress_tracker(total_games, "Processing H2H stats")
    processed = 0
    latest_game_id = None
    for game in games_query:
        if MAX_GAMES_TO_PROCESS is not None and processed >= MAX_GAMES_TO_PROCESS:
            break
        # --- Gather all relevant data for this game ---
        # Get all GameRoster entries for this game
        rosters = session.query(GameRoster).filter(GameRoster.game_id == game.id).all()
        # Map: team_id -> set of human_ids (players)
        team_to_players = {}
        human_roles = {}  # human_id -> set of roles in this game
        for roster in rosters:
            team_to_players.setdefault(roster.team_id, set()).add(roster.human_id)
            human_roles.setdefault(roster.human_id, set()).add(roster.role)
        # Get all human_ids in this game
        all_humans = set(human_roles.keys())
        # Add goalies from Game table (home/visitor)
        if game.home_goalie_id:
            all_humans.add(game.home_goalie_id)
            human_roles.setdefault(game.home_goalie_id, set()).add("G")
        if game.visitor_goalie_id:
            all_humans.add(game.visitor_goalie_id)
            human_roles.setdefault(game.visitor_goalie_id, set()).add("G")
        # Add referees from Game table (NOT from roster!)
        if game.referee_1_id:
            all_humans.add(game.referee_1_id)
            human_roles.setdefault(game.referee_1_id, set()).add("R")
        if game.referee_2_id:
            all_humans.add(game.referee_2_id)
            human_roles.setdefault(game.referee_2_id, set()).add("R")
        # --- Build all pairs of humans in this game ---
        all_humans = list(all_humans)
        for i in range(len(all_humans)):
            for j in range(i + 1, len(all_humans)):
                h1, h2 = sorted([all_humans[i], all_humans[j]])
                key = (h1, h2)
                h2h = h2h_stats_dict.get(key)
                if not h2h:
                    h2h = H2HStats(
                        human1_id=h1,
                        human2_id=h2,
                        first_game_id=game.id,
                        last_game_id=game.id,
                        games_together=0,
                        games_against=0,
                        games_tied_together=0,
                        games_tied_against=0,
                        wins_together=0,
                        losses_together=0,
                        h1_wins_vs_h2=0,
                        h2_wins_vs_h1=0,
                        games_h1_goalie=0,
                        games_h2_goalie=0,
                        games_h1_ref=0,
                        games_h2_ref=0,
                        games_both_referees=0,
                        goals_h1_when_together=0,
                        goals_h2_when_together=0,
                        assists_h1_when_together=0,
                        assists_h2_when_together=0,
                        penalties_h1_when_together=0,
                        penalties_h2_when_together=0,
                        gm_penalties_h1_when_together=0,
                        gm_penalties_h2_when_together=0,
                        h1_goalie_h2_scorer_goals=0,
                        h2_goalie_h1_scorer_goals=0,
                        shots_faced_h1_goalie_vs_h2=0,
                        shots_faced_h2_goalie_vs_h1=0,
                        goals_allowed_h1_goalie_vs_h2=0,
                        goals_allowed_h2_goalie_vs_h1=0,
                        save_percentage_h1_goalie_vs_h2=0.0,
                        save_percentage_h2_goalie_vs_h1=0.0,
                        h1_ref_h2_player_games=0,
                        h2_ref_h1_player_games=0,
                        h1_ref_penalties_on_h2=0,
                        h2_ref_penalties_on_h1=0,
                        h1_ref_gm_penalties_on_h2=0,
                        h2_ref_gm_penalties_on_h1=0,
                        penalties_given_both_refs=0,
                        gm_penalties_given_both_refs=0,
                        h1_shootout_attempts_vs_h2_goalie=0,
                        h1_shootout_goals_vs_h2_goalie=0,
                        h2_shootout_attempts_vs_h1_goalie=0,
                        h2_shootout_goals_vs_h1_goalie=0,
                    )
                    h2h_stats_dict[key] = h2h
                # Update first/last game ids
                if game.id < h2h.first_game_id:
                    h2h.first_game_id = game.id
                if game.id > h2h.last_game_id:
                    h2h.last_game_id = game.id
                # --- Determine roles and teams ---
                h1_roles = human_roles.get(h1, set())
                h2_roles = human_roles.get(h2, set())
                h1_team = None
                h2_team = None
                for team_id, players in team_to_players.items():
                    if h1 in players:
                        h1_team = team_id
                    if h2 in players:
                        h2_team = team_id
                # --- General stats ---
                h2h.games_together += 1  # Both present in this game
                if h1_team and h2_team:
                    if h1_team == h2_team:
                        h2h.wins_together += int(_is_win(game, h1_team))
                        h2h.losses_together += int(_is_loss(game, h1_team))
                        if _is_tie(game):
                            h2h.games_tied_together += 1
                    else:
                        h2h.games_against += 1
                        if _is_win(game, h1_team):
                            h2h.h1_wins_vs_h2 += 1
                        if _is_win(game, h2_team):
                            h2h.h2_wins_vs_h1 += 1
                        if _is_tie(game):
                            h2h.games_tied_against += 1
                # --- Role-specific stats ---
                if "G" in h1_roles:
                    h2h.games_h1_goalie += 1
                if "G" in h2_roles:
                    h2h.games_h2_goalie += 1
                if "R" in h1_roles:
                    h2h.games_h1_ref += 1
                if "R" in h2_roles:
                    h2h.games_h2_ref += 1
                if "R" in h1_roles and "R" in h2_roles:
                    h2h.games_both_referees += 1
                # --- Goals, assists, penalties ---
                # Goals
                goals = session.query(Goal).filter(Goal.game_id == game.id).all()
                for goal in goals:
                    if goal.goal_scorer_id == h1 and (
                        goal.assist_1_id == h2 or goal.assist_2_id == h2
                    ):
                        h2h.goals_h1_when_together += 1
                    if goal.goal_scorer_id == h2 and (
                        goal.assist_1_id == h1 or goal.assist_2_id == h1
                    ):
                        h2h.goals_h2_when_together += 1
                # Penalties
                penalties = (
                    session.query(Penalty).filter(Penalty.game_id == game.id).all()
                )
                for pen in penalties:
                    if pen.penalized_player_id == h1:
                        h2h.penalties_h1_when_together += 1
                        if pen.penalty_minutes and "GM" in pen.penalty_minutes:
                            h2h.gm_penalties_h1_when_together += 1
                    if pen.penalized_player_id == h2:
                        h2h.penalties_h2_when_together += 1
                        if pen.penalty_minutes and "GM" in pen.penalty_minutes:
                            h2h.gm_penalties_h2_when_together += 1
                # --- TODO: Add more detailed logic for goalie/skater, referee/player, shootouts, etc. ---
        latest_game_id = game.id
        processed += 1
        progress.update(processed)
    # Commit all stats at once
    session.query(H2HStats).delete()
    session.add_all(list(h2h_stats_dict.values()))
    session.commit()
    # Save/update meta
    meta = H2HStatsMeta(
        last_run_timestamp=datetime.utcnow(), last_processed_game_id=latest_game_id
    )
    session.add(meta)
    session.commit()
    print("H2H aggregation complete.")


# --- Helper functions for win/loss/tie ---
def _is_win(game, team_id):
    if team_id == game.home_team_id:
        return (game.home_final_score or 0) > (game.visitor_final_score or 0)
    if team_id == game.visitor_team_id:
        return (game.visitor_final_score or 0) > (game.home_final_score or 0)
    return False


def _is_loss(game, team_id):
    if team_id == game.home_team_id:
        return (game.home_final_score or 0) < (game.visitor_final_score or 0)
    if team_id == game.visitor_team_id:
        return (game.visitor_final_score or 0) < (game.home_final_score or 0)
    return False


def _is_tie(game):
    return (
        game.home_final_score is not None
        and game.visitor_final_score is not None
        and game.home_final_score == game.visitor_final_score
    )


if __name__ == "__main__":
    aggregate_h2h_stats()

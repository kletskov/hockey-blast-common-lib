import os
import sys
from datetime import datetime

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import types
from sqlalchemy.sql import func

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.h2h_models import (
    SkaterToSkaterStats,
    SkaterToSkaterStatsMeta,
)
from hockey_blast_common_lib.models import Game, GameRoster, Goal, Penalty

# Optional: Limit processing to a specific human_id
LIMIT_HUMAN_ID = None


def aggregate_s2s_stats():
    session = create_session("boss")
    meta = (
        session.query(SkaterToSkaterStatsMeta)
        .order_by(SkaterToSkaterStatsMeta.id.desc())
        .first()
    )
    s2s_stats_dict = {}  # (skater1_id, skater2_id) -> SkaterToSkaterStats instance

    if (
        meta is None
        or meta.last_run_timestamp is None
        or meta.last_processed_game_id is None
    ):
        # Full run: delete all existing stats and process all games
        session.query(SkaterToSkaterStats).delete()
        session.commit()
        games_query = session.query(Game).order_by(Game.date, Game.time, Game.id)
        print(
            "No previous run found, deleted all existing Skater-to-Skater stats, processing all games..."
        )
    else:
        # Incremental: only process games after last processed
        for stat in session.query(SkaterToSkaterStats).all():
            s2s_stats_dict[(stat.skater1_id, stat.skater2_id)] = stat
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
    processed = 0
    latest_game_id = None

    for game in games_query:
        # Separate skaters into home and away rosters (exclude goalies)
        home_skaters = [
            entry.human_id
            for entry in session.query(GameRoster)
            .filter(
                GameRoster.game_id == game.id,
                GameRoster.team_id == game.home_team_id,
                ~GameRoster.role.ilike("g"),
            )
            .all()
        ]
        away_skaters = [
            entry.human_id
            for entry in session.query(GameRoster)
            .filter(
                GameRoster.game_id == game.id,
                GameRoster.team_id == game.visitor_team_id,
                ~GameRoster.role.ilike("g"),
            )
            .all()
        ]

        if (
            LIMIT_HUMAN_ID is not None
            and LIMIT_HUMAN_ID not in home_skaters + away_skaters
        ):
            continue

        # Create pairs of skaters from different rosters
        for h_skater in home_skaters:
            for a_skater in away_skaters:
                if LIMIT_HUMAN_ID is not None and LIMIT_HUMAN_ID not in [
                    h_skater,
                    a_skater,
                ]:
                    continue

                s1, s2 = sorted([h_skater, a_skater])
                key = (s1, s2)
                s2s = s2s_stats_dict.get(key)
                if not s2s:
                    s2s = SkaterToSkaterStats(
                        skater1_id=s1,
                        skater2_id=s2,
                        games_against=0,
                        games_tied_against=0,
                        skater1_wins_vs_skater2=0,
                        skater2_wins_vs_skater1=0,
                        skater1_goals_against_skater2=0,
                        skater2_goals_against_skater1=0,
                        skater1_assists_against_skater2=0,
                        skater2_assists_against_skater1=0,
                        skater1_penalties_against_skater2=0,
                        skater2_penalties_against_skater1=0,
                    )
                    s2s_stats_dict[key] = s2s

                # Update stats
                s2s.games_against += 1
                if _is_tie(game):
                    s2s.games_tied_against += 1
                elif _is_win(game, s1, game.home_team_id):
                    s2s.skater1_wins_vs_skater2 += 1
                elif _is_win(game, s2, game.visitor_team_id):
                    s2s.skater2_wins_vs_skater1 += 1

                # Goals and assists
                goals_stats = session.query(Goal).filter(Goal.game_id == game.id).all()
                for goal in goals_stats:
                    if goal.goal_scorer_id == s1:
                        s2s.skater1_goals_against_skater2 += 1
                    if goal.goal_scorer_id == s2:
                        s2s.skater2_goals_against_skater1 += 1
                    if goal.assist_1_id == s1 or goal.assist_2_id == s1:
                        s2s.skater1_assists_against_skater2 += 1
                    if goal.assist_1_id == s2 or goal.assist_2_id == s2:
                        s2s.skater2_assists_against_skater1 += 1

                # Penalties
                penalties_stats = (
                    session.query(Penalty).filter(Penalty.game_id == game.id).all()
                )
                for penalty in penalties_stats:
                    if penalty.penalized_player_id == s1:
                        s2s.skater1_penalties_against_skater2 += 1
                    if penalty.penalized_player_id == s2:
                        s2s.skater2_penalties_against_skater1 += 1

        latest_game_id = game.id
        processed += 1
        if processed % 10 == 0 or processed == total_games:
            print(
                f"\rProcessed {processed}/{total_games} games ({(processed/total_games)*100:.2f}%)",
                end="",
            )
            sys.stdout.flush()

    # Commit all stats at once
    session.query(SkaterToSkaterStats).delete()
    session.add_all(list(s2s_stats_dict.values()))
    session.commit()
    print(f"\rProcessed {processed}/{total_games} games (100.00%)")

    # Save/update meta
    meta = SkaterToSkaterStatsMeta(
        last_run_timestamp=datetime.utcnow(), last_processed_game_id=latest_game_id
    )
    session.add(meta)
    session.commit()
    print("Skater-to-Skater aggregation complete.")


# --- Helper functions for win/loss/tie ---
def _is_win(game, skater_id, team_id):
    if team_id == game.home_team_id:
        return (game.home_final_score or 0) > (game.visitor_final_score or 0)
    if team_id == game.visitor_team_id:
        return (game.visitor_final_score or 0) > (game.home_final_score or 0)
    return False


def _is_tie(game):
    return (
        game.home_final_score is not None
        and game.visitor_final_score is not None
        and game.home_final_score == game.visitor_final_score
    )


if __name__ == "__main__":
    aggregate_s2s_stats()

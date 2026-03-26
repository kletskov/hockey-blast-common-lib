"""
Aggregate team standings per division.

Computes wins, losses, ties, OT results, goals for/against, points, and rank
for every team in every active division. Marks is_champion=True for the
top-ranked team in completed divisions.

Run as part of aggregate_all_stats.py nightly job.

Points system:
    Win (regulation)  = 2 pts
    Win (OT/SO)       = 2 pts
    Loss (OT/SO)      = 1 pt
    Tie               = 1 pt each
    Loss (regulation) = 0 pts
"""
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, case, text

from hockey_blast_common_lib.db_connection import create_session_boss
from hockey_blast_common_lib.models import Division, Game, Team
from hockey_blast_common_lib.stats_models import DivisionTeamStandings

FINAL_STATUSES = ("Final", "Final.", "Final/OT", "Final/OT2", "Final/SO", "Final(SO)", "NOEVENTS", "FORFEIT")


def aggregate_division_team_standings(session, division_id: int) -> int:
    """
    Compute and upsert standings for all teams in a single division.
    Returns number of team rows written.
    """
    division = session.query(Division).filter(Division.id == division_id).first()
    if not division:
        return 0

    # All completed games in this division
    games = (
        session.query(Game)
        .filter(
            Game.division_id == division_id,
            Game.status.in_(FINAL_STATUSES),
            Game.home_team_id.isnot(None),
            Game.visitor_team_id.isnot(None),
            Game.home_final_score.isnot(None),
            Game.visitor_final_score.isnot(None),
        )
        .all()
    )

    if not games:
        return 0

    # Accumulate stats per team
    stats: dict[int, dict] = {}

    def _get(team_id):
        if team_id not in stats:
            stats[team_id] = dict(
                games_played=0, wins=0, losses=0, ties=0,
                ot_wins=0, ot_losses=0, points=0,
                goals_for=0, goals_against=0,
            )
        return stats[team_id]

    for g in games:
        h = g.home_final_score
        v = g.visitor_final_score
        is_ot = bool(g.went_to_ot) or g.status in ("Final/OT", "Final/OT2", "Final/SO", "Final(SO)")

        ht = _get(g.home_team_id)
        vt = _get(g.visitor_team_id)

        ht["games_played"] += 1
        vt["games_played"] += 1
        ht["goals_for"] += h
        ht["goals_against"] += v
        vt["goals_for"] += v
        vt["goals_against"] += h

        if h == v:  # Tie
            ht["ties"] += 1
            vt["ties"] += 1
            ht["points"] += 1
            vt["points"] += 1
        elif h > v:  # Home wins
            ht["wins"] += 1
            vt["losses"] += 1
            ht["points"] += 2
            if is_ot:
                ht["ot_wins"] += 1
                vt["ot_losses"] += 1
                vt["points"] += 1  # OT loss = 1 pt
        else:  # Visitor wins
            vt["wins"] += 1
            ht["losses"] += 1
            vt["points"] += 2
            if is_ot:
                vt["ot_wins"] += 1
                ht["ot_losses"] += 1
                ht["points"] += 1  # OT loss = 1 pt

    if not stats:
        return 0

    # Rank by: points DESC, wins DESC, goal_differential DESC
    ranked = sorted(
        stats.items(),
        key=lambda kv: (
            kv[1]["points"],
            kv[1]["wins"],
            kv[1]["goals_for"] - kv[1]["goals_against"],
        ),
        reverse=True,
    )

    # Determine if division is complete (no scheduled games left)
    remaining = session.query(func.count(Game.id)).filter(
        Game.division_id == division_id,
        Game.status == "Scheduled",
    ).scalar() or 0
    division_complete = remaining == 0

    # Delete existing rows for this division
    session.query(DivisionTeamStandings).filter(
        DivisionTeamStandings.division_id == division_id
    ).delete()

    now = datetime.utcnow()
    written = 0
    for rank, (team_id, s) in enumerate(ranked, 1):
        row = DivisionTeamStandings(
            division_id=division_id,
            team_id=team_id,
            games_played=s["games_played"],
            wins=s["wins"],
            losses=s["losses"],
            ties=s["ties"],
            ot_wins=s["ot_wins"],
            ot_losses=s["ot_losses"],
            points=s["points"],
            goals_for=s["goals_for"],
            goals_against=s["goals_against"],
            goal_differential=s["goals_for"] - s["goals_against"],
            rank=rank,
            is_champion=(rank == 1 and division_complete),
            updated_at=now,
        )
        session.add(row)
        written += 1

    session.commit()
    return written


def run_aggregate_division_team_standings():
    """Aggregate team standings for all divisions that have completed games."""
    print("\n" + "=" * 80, flush=True)
    print("AGGREGATING DIVISION TEAM STANDINGS", flush=True)
    print("=" * 80, flush=True)

    start = datetime.now()
    session = create_session_boss()

    try:
        # Find all divisions that have at least one completed game
        divisions_with_games = (
            session.query(Game.division_id)
            .filter(Game.status.in_(FINAL_STATUSES))
            .distinct()
            .all()
        )
        division_ids = [r[0] for r in divisions_with_games if r[0] is not None]

        print(f"Processing {len(division_ids):,} divisions...", flush=True)

        total_rows = 0
        for i, div_id in enumerate(division_ids):
            rows = aggregate_division_team_standings(session, div_id)
            total_rows += rows
            if (i + 1) % 100 == 0:
                print(f"  {i + 1:,} / {len(division_ids):,} divisions processed ({total_rows:,} rows)", flush=True)

        duration = (datetime.now() - start).total_seconds()
        print(f"\n✓ Done: {len(division_ids):,} divisions, {total_rows:,} team-standing rows in {duration:.1f}s", flush=True)
        print("=" * 80, flush=True)

    finally:
        session.close()


if __name__ == "__main__":
    run_aggregate_division_team_standings()

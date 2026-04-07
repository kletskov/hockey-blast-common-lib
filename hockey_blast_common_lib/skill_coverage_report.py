"""
Skill propagation coverage report.

Analyzes the state of the skill graph and prints/saves a detailed report.
Useful to run before and after skill propagation to see how the graph improved.

Usage:
    python skill_coverage_report.py                    # Print to stdout
    python skill_coverage_report.py --save report.md   # Also save to file
    python skill_coverage_report.py --save-auto        # Auto-name with timestamp
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.db_connection import create_session
from hockey_blast_common_lib.models import Division, Human, Level, Organization
from hockey_blast_common_lib.stats_models import (
    LevelsGraphEdge,
    LevelStatsSkater,
    SkillValuePPGRatio,
)


def generate_coverage_report(session):
    """Generate a comprehensive skill coverage report. Returns report as string."""
    lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"# Skill Propagation Coverage Report")
    lines.append(f"Generated: {timestamp}")
    lines.append("")

    # === 1. Level coverage ===
    lines.append("## Level Coverage")
    lines.append("")

    orgs = session.query(Organization).order_by(Organization.alias).all()
    org_map = {o.id: o.alias for o in orgs}

    all_levels = session.query(Level).all()
    total_levels = len(all_levels)
    seed_levels = [l for l in all_levels if l.is_seed]
    propagated_levels = [l for l in all_levels if not l.is_seed and l.skill_propagation_sequence is not None and l.skill_propagation_sequence >= 0]
    unassigned_levels = [l for l in all_levels if l.skill_value is None or l.skill_value < 0]

    lines.append(f"| Metric | Count | % |")
    lines.append(f"|--------|------:|----:|")
    lines.append(f"| Total levels | {total_levels} | 100% |")
    lines.append(f"| Seed levels (manually assigned) | {len(seed_levels)} | {len(seed_levels)*100//max(total_levels,1)}% |")
    lines.append(f"| Propagated levels (auto-assigned) | {len(propagated_levels)} | {len(propagated_levels)*100//max(total_levels,1)}% |")
    lines.append(f"| Levels WITH skill value | {len(seed_levels) + len(propagated_levels)} | {(len(seed_levels)+len(propagated_levels))*100//max(total_levels,1)}% |")
    lines.append(f"| Levels WITHOUT skill value | {len(unassigned_levels)} | {len(unassigned_levels)*100//max(total_levels,1)}% |")
    lines.append("")

    # Breakdown by propagation sequence
    seq_counts = defaultdict(int)
    for l in all_levels:
        seq = l.skill_propagation_sequence if l.skill_propagation_sequence is not None else -1
        seq_counts[seq] += 1

    lines.append("### By propagation sequence")
    lines.append("")
    lines.append("| Sequence | Count | Meaning |")
    lines.append("|----------|------:|---------|")
    for seq in sorted(seq_counts.keys()):
        meaning = "Seed" if seq == 0 else ("Not reached" if seq == -1 else f"Propagation round {seq}")
        lines.append(f"| {seq} | {seq_counts[seq]} | {meaning} |")
    lines.append("")

    # === 2. Per-org breakdown ===
    lines.append("## Per-Organization Breakdown")
    lines.append("")

    org_level_data = defaultdict(lambda: {"total": 0, "with_skill": 0, "seed": 0, "propagated": 0})
    for l in all_levels:
        org_alias = org_map.get(l.org_id, f"org_{l.org_id}")
        org_level_data[org_alias]["total"] += 1
        if l.is_seed:
            org_level_data[org_alias]["seed"] += 1
            org_level_data[org_alias]["with_skill"] += 1
        elif l.skill_propagation_sequence is not None and l.skill_propagation_sequence >= 0:
            org_level_data[org_alias]["propagated"] += 1
            org_level_data[org_alias]["with_skill"] += 1

    lines.append("| Org | Total Levels | Seed | Propagated | With Skill | Without | Coverage |")
    lines.append("|-----|------------:|-----:|-----------:|-----------:|--------:|---------:|")
    for org_alias in sorted(org_level_data.keys()):
        d = org_level_data[org_alias]
        without = d["total"] - d["with_skill"]
        pct = d["with_skill"] * 100 // max(d["total"], 1)
        lines.append(f"| {org_alias} | {d['total']} | {d['seed']} | {d['propagated']} | {d['with_skill']} | {without} | {pct}% |")
    lines.append("")

    # === 3. Graph edges ===
    lines.append("## Graph Edges")
    lines.append("")

    edges = session.query(LevelsGraphEdge).all()
    total_edges = len(edges)

    if total_edges > 0:
        conn_values = [e.n_connections for e in edges]
        game_values = [e.n_games for e in edges]
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|------:|")
        lines.append(f"| Total edges | {total_edges} |")
        lines.append(f"| Edges with >= 5 connections | {sum(1 for c in conn_values if c >= 5)} |")
        lines.append(f"| Edges with >= 20 connections | {sum(1 for c in conn_values if c >= 20)} |")
        lines.append(f"| Min connections per edge | {min(conn_values)} |")
        lines.append(f"| Max connections per edge | {max(conn_values)} |")
        lines.append(f"| Median connections | {sorted(conn_values)[len(conn_values)//2]} |")
        lines.append(f"| Total games across edges | {sum(game_values)} |")
    else:
        lines.append("No graph edges found.")
    lines.append("")

    # === 4. PPG Ratio correlations ===
    correlations = session.query(SkillValuePPGRatio).all()
    lines.append("## Skill-PPG Correlations")
    lines.append("")
    lines.append(f"Total correlation entries: {len(correlations)}")
    if correlations:
        lines.append("")
        lines.append("| From Skill | To Skill | PPG Ratio | Games |")
        lines.append("|-----------:|---------:|----------:|------:|")
        for c in sorted(correlations, key=lambda x: x.from_skill_value):
            lines.append(f"| {c.from_skill_value:.1f} | {c.to_skill_value:.1f} | {c.ppg_ratio:.3f} | {c.n_games} |")
    lines.append("")

    # === 5. Human skill coverage ===
    lines.append("## Human (Skater) Skill Coverage")
    lines.append("")

    total_humans = session.query(Human).count()
    humans_with_skill = session.query(Human).filter(
        Human.skater_skill_value.isnot(None),
        Human.skater_skill_value > 0
    ).count()
    humans_with_level_stats = session.query(LevelStatsSkater.human_id).distinct().count()

    lines.append(f"| Metric | Count | % of total |")
    lines.append(f"|--------|------:|-----------:|")
    lines.append(f"| Total humans | {total_humans} | 100% |")
    lines.append(f"| Humans with level stats | {humans_with_level_stats} | {humans_with_level_stats*100//max(total_humans,1)}% |")
    lines.append(f"| Humans with skill value assigned | {humans_with_skill} | {humans_with_skill*100//max(total_humans,1)}% |")
    lines.append(f"| Humans without skill value | {total_humans - humans_with_skill} | {(total_humans - humans_with_skill)*100//max(total_humans,1)}% |")
    lines.append("")

    # === 6. Unassigned levels detail ===
    if unassigned_levels:
        lines.append("## Unassigned Levels (no skill value)")
        lines.append("")
        lines.append("| Org | Level Name | Has Edges? | Divisions Using |")
        lines.append("|-----|-----------|:----------:|-----------------:|")

        # Count divisions per level
        div_counts = defaultdict(int)
        for div in session.query(Division).all():
            if div.level_id:
                div_counts[div.level_id] += 1

        # Check which unassigned levels have edges
        edge_level_ids = set()
        for e in edges:
            edge_level_ids.add(e.from_level_id)
            edge_level_ids.add(e.to_level_id)

        for l in sorted(unassigned_levels, key=lambda x: (org_map.get(x.org_id, ""), x.level_name)):
            org_alias = org_map.get(l.org_id, f"org_{l.org_id}")
            has_edges = "Yes" if l.id in edge_level_ids else "No"
            n_divs = div_counts.get(l.id, 0)
            lines.append(f"| {org_alias} | {l.level_name} | {has_edges} | {n_divs} |")
        lines.append("")

    report = "\n".join(lines)
    return report


def main():
    parser = argparse.ArgumentParser(description="Skill propagation coverage report")
    parser.add_argument("--save", type=str, help="Save report to this file path")
    parser.add_argument("--save-auto", action="store_true", help="Auto-save with timestamp")
    args = parser.parse_args()

    session = create_session("boss")
    report = generate_coverage_report(session)
    session.close()

    print(report)

    save_path = args.save
    if args.save_auto:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"skill_coverage_{timestamp}.md")

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {save_path}")


if __name__ == "__main__":
    main()

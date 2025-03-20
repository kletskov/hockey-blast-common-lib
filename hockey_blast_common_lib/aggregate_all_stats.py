import sys, os

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hockey_blast_common_lib.aggregate_human_stats import run_aggregate_human_stats
from hockey_blast_common_lib.aggregate_skater_stats import run_aggregate_skater_stats
from hockey_blast_common_lib.aggregate_goalie_stats import run_aggregate_goalie_stats
from hockey_blast_common_lib.aggregate_referee_stats import run_aggregate_referee_stats

if __name__ == "__main__":
    print("Running aggregate_skater_stats...", flush=True)
    run_aggregate_skater_stats()
    print("Finished running aggregate_skater_stats\n")

    print("Running aggregate_goalie_stats...", flush=True)
    run_aggregate_goalie_stats()
    print("Finished running aggregate_goalie_stats\n")

    print("Running aggregate_referee_stats...", flush=True)
    run_aggregate_referee_stats()
    print("Finished running aggregate_referee_stats\n")

    print("Running aggregate_human_stats...", flush=True)
    run_aggregate_human_stats()
    print("Finished running aggregate_human_stats\n")

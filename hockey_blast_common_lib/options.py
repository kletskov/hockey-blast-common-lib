import argparse

MAX_HUMAN_SEARCH_RESULTS = 25
MAX_TEAM_SEARCH_RESULTS = 25
MIN_GAMES_FOR_ORG_STATS = 1
MIN_GAMES_FOR_DIVISION_STATS = 1
MIN_GAMES_FOR_LEVEL_STATS = 1

orgs = {'caha', 'sharksice', 'tvice'}

not_human_names = [
    ("Away", None, None),
    (None, "Unknown", None),
    ("Not", None , None),
    (None , None, "Goalie"),
    ("Unassigned",None , None)
]

def parse_args():
    parser = argparse.ArgumentParser(description="Process data for a specific organization.")
    parser.add_argument("org", choices=orgs, help="The organization to process (e.g., 'caha', 'sharksice', 'tvice').")
    parser.add_argument("--reprocess", action="store_true", help="Reprocess existing data.")
    parser.add_argument("--pre_process", action="store_true", help="Pre-Process existing data.")
    return parser.parse_args()

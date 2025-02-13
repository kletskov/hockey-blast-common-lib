def assign_ranks(stats_dict, field, reverse_rank=False):
    sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1][field], reverse=not reverse_rank)
    for rank, (key, stat) in enumerate(sorted_stats, start=1):
        stats_dict[key][f'{field}_rank'] = rank

ALL_ORGS_ID = -1
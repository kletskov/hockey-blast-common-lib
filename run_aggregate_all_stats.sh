#!/bin/bash
# Wrapper script for aggregate_all_stats.py that ensures fresh logs each night

# Define log file paths
LOG_OUT="/tmp/aggregate_all_stats.out"
LOG_ERR="/tmp/aggregate_all_stats.err"

# Truncate log files (create fresh files)
> "$LOG_OUT"
> "$LOG_ERR"

# Add timestamp header to log
echo "=================================================================================" >> "$LOG_OUT"
echo "Stats Aggregation Started: $(date)" >> "$LOG_OUT"
echo "=================================================================================" >> "$LOG_OUT"
echo "" >> "$LOG_OUT"

# Run the Python script
/Users/pavelkletskov/hockey-blast-prod/hockey-blast-common-lib/.venv/bin/python \
  /Users/pavelkletskov/hockey-blast-prod/hockey-blast-common-lib/hockey_blast_common_lib/aggregate_all_stats.py \
  >> "$LOG_OUT" 2>> "$LOG_ERR"

# Capture exit code
EXIT_CODE=$?

# Add completion timestamp
echo "" >> "$LOG_OUT"
echo "=================================================================================" >> "$LOG_OUT"
echo "Stats Aggregation Completed: $(date)" >> "$LOG_OUT"
echo "Exit Code: $EXIT_CODE" >> "$LOG_OUT"
echo "=================================================================================" >> "$LOG_OUT"

exit $EXIT_CODE

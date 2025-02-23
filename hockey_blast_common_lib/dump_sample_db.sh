#!/bin/zsh

# Database credentials from environment variables
DB_USER=${DB_USER:-"frontend_user"}
DB_PASSWORD=${DB_PASSWORD:-"hockey-blast"}
DB_NAME=${DB_NAME:-"hockey_blast_sample"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-"5432"}
DUMP_FILE="hockey_blast_sample_backup.sql"
COMPRESSED_DUMP_FILE="hockey_blast_sample_backup.sql.gz"

# Export PGPASSWORD to avoid password prompt
export PGPASSWORD=$DB_PASSWORD

# Dump the database schema and data
pg_dump --username=$DB_USER --host=$DB_HOST --port=$DB_PORT --format=custom --file=$DUMP_FILE $DB_NAME
if [ $? -ne 0 ]; then
  echo "Error: Database dump failed."
  exit 1
fi

# Compress the backup file
gzip -c $DUMP_FILE > $COMPRESSED_DUMP_FILE

# Remove the uncompressed backup file
rm $DUMP_FILE

echo "Database dump completed: $COMPRESSED_DUMP_FILE"

#!/bin/zsh

# Database credentials from environment variables
DB_USER=${DB_USER:-"frontend_user"}
DB_PASSWORD=${DB_PASSWORD:-"hockey-blast"}
DB_NAME=${DB_NAME:-"hockey_blast_sample"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-"5432"}
COMPRESSED_DUMP_FILE="hockey_blast_sample_backup.sql.gz"

# Superuser credentials
SUPERUSER="your_superuser"
SUPERUSER_PASSWORD="your_superuser_password"

# Export PGPASSWORD to avoid password prompt
export PGPASSWORD=$SUPERUSER_PASSWORD

# Generate a unique timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP_DB_NAME="${DB_NAME}_backup_${TIMESTAMP}"

# Check if the database exists and rename it if it does
DB_EXISTS=$(psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT -d postgres --tuples-only --command="SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'")
if [ "$DB_EXISTS" = "1" ]; then
  psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT -d postgres --command="SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '$DB_NAME' AND pid <> pg_backend_pid();"
  psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT -d postgres --command="ALTER DATABASE $DB_NAME RENAME TO $BACKUP_DB_NAME"
fi

# Create a new database
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT -d postgres --command="CREATE DATABASE $DB_NAME OWNER $SUPERUSER"

# Export PGPASSWORD for frontend_user user
export PGPASSWORD=$DB_PASSWORD

# Restore the database from the dump file with --no-owner option
gunzip -c $COMPRESSED_DUMP_FILE | pg_restore --username=$DB_USER --host=$DB_HOST --port=$DB_PORT --dbname=$DB_NAME --format=custom --no-owner

# Create the frontend_user if it does not exist
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --dbname=$DB_NAME --command="DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'frontend_user') THEN CREATE ROLE frontend_user LOGIN PASSWORD '$DB_PASSWORD'; END IF; END \$\$;"

# Grant necessary permissions to the  user
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --dbname=$DB_NAME  --command="GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO frontend_user"

echo "Database restore completed: $DB_NAME"
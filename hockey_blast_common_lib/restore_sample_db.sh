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

# Drop the existing database if it exists
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --command="SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '$DB_NAME' AND pid <> pg_backend_pid();"
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --command="DROP DATABASE IF EXISTS $DB_NAME"

# Create a new database
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --command="CREATE DATABASE $DB_NAME OWNER $SUPERUSER"

# Export PGPASSWORD for read-only user
export PGPASSWORD=$DB_PASSWORD

# Restore the database from the dump file with --no-owner option
gunzip -c $COMPRESSED_DUMP_FILE | pg_restore --username=$DB_USER --host=$DB_HOST --port=$DB_PORT --dbname=$DB_NAME --format=custom --no-owner

# Grant necessary permissions to the read-only user
psql --username=$SUPERUSER --host=$DB_HOST --port=$DB_PORT --dbname=$DB_NAME --command="GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO frontend_user"

echo "Database restore completed: $DB_NAME"
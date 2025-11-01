import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file in the root directory of THE PROJECT (not this library)
load_dotenv()

# Database connection parameters per organization
DB_PARAMS = {
    "frontend": {
        "dbname": os.getenv("DB_NAME", "hockey_blast"),
        "user": os.getenv("DB_USER", "frontend_user"),
        "password": os.getenv("DB_PASSWORD", "hockey-blast"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
    },
    "frontend-sample-db": {
        "dbname": os.getenv("DB_NAME_SAMPLE", "hockey_blast_sample"),
        "user": os.getenv("DB_USER", "frontend_user"),
        "password": os.getenv("DB_PASSWORD", "hockey-blast"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
    },
    # MCP server uses read-only frontend_user (same as frontend)
    "mcp": {
        "dbname": os.getenv("DB_NAME", "hockey_blast"),
        "user": os.getenv("DB_USER", "frontend_user"),
        "password": os.getenv("DB_PASSWORD", "hockey-blast"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
    },
    # The section below is to handle recovery of sample DB where boss user is present, to avoid warnings and errors
    # TODO: Maybe figure out a way to do backup without it and make frontend_user own the sample?
    "boss": {
        "dbname": os.getenv("DB_NAME", "hockey_blast"),
        "user": os.getenv("DB_USER_BOSS", "boss"),
        "password": os.getenv("DB_PASSWORD_BOSS", "boss"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
    },
}


def get_db_params(config_name):
    if config_name not in DB_PARAMS:
        raise ValueError(f"Invalid organization: {config_name}")
    return DB_PARAMS[config_name]


def create_session(config_name):
    """
    Create a database session using the specified configuration.

    Args:
        config_name: One of "frontend", "frontend-sample-db", "mcp", "boss"

    Returns:
        SQLAlchemy session object
    """
    db_params = get_db_params(config_name)
    db_url = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


# Convenience functions for standardized session creation
def create_session_frontend():
    """
    Create read-only session for frontend web application.
    Uses frontend_user with limited permissions.
    """
    return create_session("frontend")


def create_session_mcp():
    """
    Create read-only session for MCP server.
    Uses frontend_user with limited permissions (same as frontend).
    """
    return create_session("mcp")


def create_session_frontend_sampledb():
    """
    Create read-only session for frontend sample database.
    Uses frontend_user with limited permissions.
    """
    return create_session("frontend-sample-db")


def create_session_boss():
    """
    Create full-access session for pipeline operations.
    WARNING: Has write permissions. Use only in pipeline scripts.
    """
    return create_session("boss")

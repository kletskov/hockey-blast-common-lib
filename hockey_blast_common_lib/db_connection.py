import os
import threading

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session as _SessionType

# Load environment variables from .env file in the root directory of THE PROJECT (not this library)
load_dotenv(override=False)

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


# Cached engines + sessionmakers, keyed by config_name. Long-running
# processes (Flask apps, schedulers) call create_session() repeatedly,
# and previously each call did create_engine() — leaking the engine's
# connection pool every time. We now build ONE engine per config and
# reuse it. _engine_lock prevents two threads from building the same
# engine concurrently on first use.
_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker] = {}
_engine_lock = threading.Lock()


def _get_engine(config_name: str) -> Engine:
    """Return a cached engine for *config_name*, building it on first call."""
    if config_name in _engines:
        return _engines[config_name]
    with _engine_lock:
        if config_name in _engines:  # another thread built it while we waited
            return _engines[config_name]
        db_params = get_db_params(config_name)
        db_url = (
            f"postgresql://{db_params['user']}:{db_params['password']}"
            f"@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
        )
        # pool_pre_ping=True transparently retries a stale connection (e.g.
        # after a DB restart) instead of raising — long-running services
        # otherwise wedge on the first reused connection after an outage.
        engine = create_engine(db_url, pool_pre_ping=True)
        _engines[config_name] = engine
        _sessionmakers[config_name] = sessionmaker(bind=engine)
        return engine


def create_session(config_name) -> _SessionType:
    """
    Create a database session using the specified configuration.

    Args:
        config_name: One of "frontend", "frontend-sample-db", "mcp", "boss"

    Returns:
        SQLAlchemy session object backed by the cached engine for
        *config_name*. Callers MUST call .close() on the session when
        done (or use it as a context manager); the underlying TCP
        connection is returned to the pool, not destroyed.
    """
    _get_engine(config_name)  # ensures _sessionmakers[config_name] exists
    return _sessionmakers[config_name]()


def dispose_engines() -> None:
    """Release every cached engine's connection pool. For test teardown
    and graceful shutdown only — production code should let engines
    live for the process lifetime."""
    with _engine_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()
        _sessionmakers.clear()


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

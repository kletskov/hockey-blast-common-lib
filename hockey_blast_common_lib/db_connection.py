import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database connection parameters per organization
DB_PARAMS = {
    "frontend": {
        "dbname": os.getenv("DB_NAME", "hockey_blast"),
        "user": os.getenv("DB_USER", "frontend_user"),
        "password": os.getenv("DB_PASSWORD", "hockey-blast"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432))
    },

    "frontend-sample-db": {
        "dbname": os.getenv("DB_NAME_SAMPLE", "hockey_blast_sample"),
        "user": os.getenv("DB_USER_SAMPLE", "frontend_user"),
        "password": os.getenv("DB_PASSWORD_SAMPLE", "hockey-blast"),
        "host": os.getenv("DB_HOST_SAMPLE", "localhost"),
        "port": int(os.getenv("DB_PORT_SAMPLE", 5432))
    },

# TODO - the section below is just to handle recovery of sample DB where boss user is present
# Maybe figure out a way to do backup without it and make frontend_user own the sample? 
    "boss": {
        "dbname": os.getenv("DB_NAME_BOSS", "hockey_blast"),
        "user": os.getenv("DB_USER_BOSS", "boss"),
        "password": os.getenv("DB_PASSWORD_BOSS", "boss"),
        "host": os.getenv("DB_HOST_BOSS", "localhost"),
        "port": int(os.getenv("DB_PORT_BOSS", 5432))
    },
}

def get_db_params(config_name):
    if config_name not in DB_PARAMS:
        raise ValueError(f"Invalid organization: {config_name}")
    return DB_PARAMS[config_name]

def create_session(config_name):
    db_params = get_db_params(config_name)
    db_url = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

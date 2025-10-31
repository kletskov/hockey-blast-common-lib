import os
import sys

# Add the package directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_migrate import Migrate

from hockey_blast_common_lib.db_connection import get_db_params
from hockey_blast_common_lib.h2h_models import *
from hockey_blast_common_lib.models import *
from hockey_blast_common_lib.stats_models import *
from hockey_blast_common_lib.stats_models import db

app = Flask(__name__)
db_params = get_db_params("boss")
db_url = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
app.config["SQLALCHEMY_DATABASE_URI"] = db_url

db.init_app(app)
migrate = Migrate(app, db)

# Export db and migrate for flask cli

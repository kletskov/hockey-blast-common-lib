from flask_migrate import Migrate
from flask import Flask
from .models import *
from .stats_models import *
from .stats_models import db
from .db_connection import get_db_params

app = Flask(__name__)
db_params = get_db_params("hockey-blast-radonly")
db_url = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['dbname']}"
app.config['SQLALCHEMY_DATABASE_URI'] = db_url

db.init_app(app)
migrate = Migrate(app, db)

# Export db and migrate for flask cli

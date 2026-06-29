from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
oauth = OAuth()
csrf = CSRFProtect()

login_manager.login_view = "web_auth.login"
login_manager.login_message = "Iniciá sesión para acceder a esta página."
login_manager.login_message_category = "info"

import importlib
import os

from config import config
from flask import Blueprint, Flask
from utils.email_manager import EmailManager
from extensions import db, jwt, cache, migrate, api, cors

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

URL_SCHEMA = "http"
if "HTTPS" in os.environ:
    URL_SCHEMA = "https"

BASE_SERVER_URL = os.environ.get("BASE_SERVER_URL", "http://localhost:3000")


def register_blueprints(app: Flask, package_path: str, url_prefix: str = None):
    """
    Dynamically discovers and registers Blueprints from a given package path.

    :param app: The Flask application instance.
    :param package_path: The filesystem path to the package (e.g., "controllers").
    :param url_prefix: An optional prefix for all blueprints found.
    """
    package_dir = Path(package_path)

    if not package_dir.exists() or not package_dir.is_dir():
        return

    import_path = ".".join(package_dir.parts)

    for file in package_dir.iterdir():
        if (
            not file.is_file()
            or not file.name.endswith(".py")
            or file.name.startswith("_")
        ):
            continue

        module_name = file.stem

        try:
            module = importlib.import_module(f".{module_name}", package=import_path)
        except ImportError as e:
            print(f"Warning: Could not import blueprint from {file.name}: {e}")
            continue

        for obj in module.__dict__.values():
            if isinstance(obj, Blueprint):
                app.register_blueprint(obj, url_prefix=url_prefix)
                break


def register_loaders(app: Flask):
    """
    Register user loaders and other callback functions for extensions.
    This keeps the create_app function cleaner.
    """
    from models.user import User

    @cache.memoize(timeout=20)
    @jwt.user_lookup_loader
    def user_lookup_loader(_jwt_header, jwt_data):
        """
        This function is called whenever a protected endpoint is accessed,
        and must return an object that represents the user identity.
        """
        identity = jwt_data["sub"]

        # Using a more performant cache-aware lookup
        return User.query.filter_by(email=identity).first()


def create_app(config_name: str = None) -> Flask:
    """
    An application factory, as explained in the Flask docs.

    :param config_name: The name of the configuration to use.
    """
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize Flask extensions
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    cors.init_app(app)

    # Note: migrate.init_app requires both app and db
    migrate.init_app(app, db)

    # Attach a custom manager to the app context, avoiding globals
    app.email_manager = EmailManager(app)

    # Register components
    register_loaders(app)
    register_blueprints(app, "controllers")

    api.config.title = f"{app.config.get('PRODUCT_NAME')} API"
    api.config.version = "0.0.1"
    api.register(app)  # URL: http://localhost:5000/apidoc/swagger

    return app

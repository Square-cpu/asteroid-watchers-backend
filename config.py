# config.py
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration class. Contains default and common settings."""

    SECRET_KEY = (
        os.environ.get("SECRET_KEY") or "a-very-hard-to-guess-and-long-secret-key"
    )

    SERVER_NAME = os.environ.get("SERVER_NAME", "localhost:5000")

    PRODUCT_NAME = "Startup"
    APP_TITLE = PRODUCT_NAME

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 299

    EMAIL = os.environ.get("ADMIN_EMAIL") or "example@gmail.com"
    MAIL_SUBJECT_PREFIX = f"[{PRODUCT_NAME}] "
    MAIL_SENDER = f"{PRODUCT_NAME} Admin <{EMAIL}>"
    ADMINS = (os.environ.get("ADMINS") or EMAIL).split(",")

    # --- Email Configuration ---
    # Set to 'true' in your .env file for production to enable real emails.
    EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() in (
        "true",
        "1",
        "t",
    )

    # The absolute path to the Google Service Account JSON file.
    # e.g., SERVICE_ACCOUNT_FILE=/path/to/your/credentials.json
    SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE")

    # The email address that the service account will impersonate.
    # e.g., GMAIL_API_SUBJECT=contact@yourstartup.com
    GMAIL_API_SUBJECT = os.environ.get("GMAIL_API_SUBJECT")

    # The "From" address that appears in emails sent to users.
    MAIL_SENDER = os.environ.get("MAIL_SENDER") or "Your Startup <noreply@example.com>"

    WTF_CSRF_ENABLED = True

    @staticmethod
    def init_app(app):
        """Hook for additional app initializations."""
        pass


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG = True

    # Use a simple in-memory cache for development
    CACHE_TYPE = "SimpleCache"

    # Use a local SQLite database for simplicity
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DEV_DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "dev.sqlite")


class TestingConfig(Config):
    """Configuration for running tests."""

    TESTING = True
    DEBUG = True

    EMAIL_ENABLED = False

    # Use an in-memory SQLite database for tests to keep them fast and isolated
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # CSRF protection is often disabled during tests for convenience
    WTF_CSRF_ENABLED = False

    # Disable caching for tests
    CACHE_TYPE = "NullCache"


class ProductionConfig(Config):
    """Configuration for production."""

    # Ensure DEBUG is explicitly False in production
    DEBUG = False

    CACHE_TYPE = "SimpleCache"

    # Database URI must be set in the environment for production
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


# A dictionary to easily select the correct config class
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

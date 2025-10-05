import pytest
from factory import create_app, db
from models.user import User  # Import a model to help with seeding


# It's good practice to have a seeder function for tests
def seed_database():
    """Seeds the database with initial data for testing."""
    # Create a user to test login
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        password="password123",  # Set a known password
    )
    db.session.add(user)
    db.session.commit()


@pytest.fixture(scope="module")
def app():
    """
    A fixture that creates a new Flask application instance for each test module.
    It uses the 'testing' configuration.
    """
    # 1. Create the app using the 'testing' configuration
    app = create_app(config_name="testing")

    # 2. Establish an application context
    with app.app_context():
        # 3. Create the database tables
        db.create_all()

        # 4. Yield the app instance to the tests
        yield app

        # 5. Teardown: drop all database tables after tests are done
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="module")
def client(app):
    """
    A fixture that provides a test client for the application.
    It also seeds the database with initial data.
    """
    # Establish an application context for the seeding
    with app.app_context():
        # Your 'init' script's logic can be called here.
        # For simplicity, we'll call a seeder function directly.
        seed_database()

    # Create and yield the test client
    with app.test_client() as client:
        yield client

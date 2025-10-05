# Flask Backend Startup Template

Welcome to the Startup Backend Template! This project is a production-ready foundation for building robust and scalable web applications using Flask. It comes pre-configured with a professional project structure, user authentication, testing suite, and API documentation, allowing you to focus on building your startup's unique features instead of reinventing the wheel.

This template is designed to be easily adapted. Simply rename the "Startup" project name in the configuration files to your own project's name, configure your own email service, and start building.

### Core Technologies

  * **Framework**: [Flask](https://flask.palletsprojects.com/)
  * **Database ORM**: [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
  * **Database Migrations**: [Flask-Migrate](https://flask-migrate.readthedocs.io/)
  * **Authentication**: [Flask-JWT-Extended](https://flask-jwt-extended.readthedocs.io/) for token-based auth (access & refresh tokens).
  * **API Documentation**: [Spectree](https://spectree.readthedocs.io/) with Pydantic for request validation and automatic OpenAPI (Swagger) documentation.
  * **Testing**: [Pytest](https://docs.pytest.org/) with `pytest-cov` for coverage.
  * **CORS**: [Flask-Cors](https://www.google.com/search?q=https://flask-cors.readthedocs.io/) to handle cross-origin requests.
  * **Configuration**: Environment-based configuration management using `.env` files.

### Getting Started

Follow these steps to get the project running on your local machine.

#### 1. Prerequisites

  * Python 3.10+
  * A package manager like `pip` or `uv`

#### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd backend  # Or your project's root directory
```

#### 3. Setup Virtual Environment

It's crucial to use a virtual environment to manage project dependencies.

```bash
# Create the virtual environment
python -m venv .venv

# Activate it
# On Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# On macOS / Linux
source .venv/bin/activate
```

#### 4. Install Dependencies

Install all required packages from the `requirements.txt` file.

```bash
# Using pip
python -m pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

#### 5. Configure Environment Variables

The application is configured using environment variables.

1.  **Create a `.env` file:** Make a copy of the example file.

    ```bash
    # On Windows
    copy .env.example .env
    # On macOS / Linux
    cp .env.example .env
    ```

2.  **Edit the `.env` file:** Open the new `.env` file and set the necessary variables. For local development, you can often leave the defaults. The `SECRET_KEY` is the most important one to set.

-----

### Creating the database

```bash
flask db init
```

```bash
flask db migrate
```

```bash
flask db upgrade
```

### Running the Application

With the setup complete, you can run the Flask development server.

```bash
# Ensure your virtual environment is active
# The command uses the FLASK_CONFIG and FLASK_DEBUG variables from your .env file
python -m flask run
```

The application will be running at `http://127.0.0.1:5000`.

The auto-generated API documentation (Swagger UI) will be available at `http://127.0.0.1:5000/apidoc/swagger`.

-----

### Running the Test Suite

This project uses `pytest` for testing. We recommend running tests from the project's root directory (`backend`).

#### 1. Standard Test Run

This is the fastest way to check if all tests are passing. It provides a simple pass/fail summary.

```bash
python -m pytest
```

#### 2. Test Run with Live Output

If a test is failing and you want to see `print()` statements from your code for debugging, use the `-s` flag.

```bash
python -m pytest -s
```

#### 3. Test Run with Coverage Report

To measure how much of your code is covered by tests, you can generate a coverage report. This command will produce both a summary in the terminal and a detailed HTML report.

```bash
python -m pytest --cov=. --cov-report=html
```

After the command finishes:

1.  A new directory named **`htmlcov`** will be created in your project root.
2.  Open the **`htmlcov/index.html`** file in your web browser.
3.  You can now browse the report, clicking on files to see exactly which lines of code were executed during the tests.
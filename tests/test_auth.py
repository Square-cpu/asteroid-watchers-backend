import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from flask import current_app

from itsdangerous import URLSafeSerializer

from models.user import User

# =================================================================
# Tests for the /auth/login endpoint (Existing Tests)
# =================================================================


def test_login_success(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/auth/login' endpoint is posted to with valid credentials
    THEN check that the response is valid and contains tokens
    """
    # Arrange: The user 'test@example.com' was created by the client fixture
    login_data = {"email": "test@example.com", "password": "password123"}

    # Act: Make a request to the login endpoint
    response = client.post(
        "/auth/login", data=json.dumps(login_data), content_type="application/json"
    )

    # Assert: Check the results
    assert response.status_code == 200
    response_data = response.get_json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data


def test_login_failure_wrong_password(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/auth/login' endpoint is posted to with an invalid password
    THEN check that a 401 Unauthorized error is returned
    """
    # Arrange
    login_data = {"email": "test@example.com", "password": "wrongpassword"}

    # Act
    response = client.post(
        "/auth/login", data=json.dumps(login_data), content_type="application/json"
    )

    # Assert
    assert response.status_code == 401
    response_data = response.get_json()
    assert response_data["msg"] == "Bad username or password"


# ===================================================================
# Tests for the /auth/register endpoint (Existing Tests)
# ===================================================================


def test_register_success(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/auth/register' endpoint is posted to with valid new user data
    THEN check that the response is 201 and the user is created in the database
    """
    # Arrange
    register_data = {
        "name": "New User",
        "email": "newuser@example.com",
        "password": "new_password_123",
        "confirm_password": "new_password_123",
        "discovered": {"value": "Google", "other": ""},
    }

    # Act
    response = client.post(
        "/auth/register",
        data=json.dumps(register_data),
        content_type="application/json",
    )

    # Assert: Check the HTTP response
    assert response.status_code == 201
    response_data = response.get_json()
    assert response_data["status"] == "success"
    assert "id" in response_data["data"]

    # Assert: Check that the user was actually created in the database
    user = User.query.filter_by(email="newuser@example.com").first()
    assert user is not None


def test_login_with_google_existing_user(client, mocker):
    """
    GIVEN a mocker to simulate Google's API for an existing user
    WHEN the '/auth/login' endpoint is hit with that user's Google token
    THEN check that the login is successful and no new user is created
    """
    # Arrange:
    # 1. The email we'll use is 'test@example.com', which already exists
    #    because it was created by the `client` fixture's seeder.
    fake_token_info = {"email": "test@example.com"}

    # 2. Mock only the `tokeninfo` endpoint. The `userinfo` endpoint should
    #    not be called, so we don't need to mock its response.
    mock_response = MagicMock()
    mock_response.json.return_value = fake_token_info
    mock_requests_get = mocker.patch("requests.get", return_value=mock_response)

    # Act: Call the login endpoint
    response = client.post(
        "/auth/login",
        data=json.dumps({"google_token": "another_fake_token"}),
        content_type="application/json",
    )

    # Assert:
    # 1. Check the HTTP response is successful and returns tokens
    assert response.status_code == 200
    assert "access_token" in response.get_json()

    # 2. Assert that `requests.get` was only called ONCE (for tokeninfo)
    #    This proves the "create user" branch was not taken.
    mock_requests_get.assert_called_once()


def test_register_failure_user_exists(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/auth/register' endpoint is posted to with an email that already exists
    THEN check that a 400 Bad Request error is returned
    """
    # Arrange: Use the same email as the user created in the test fixture
    register_data = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "discovered": {"value": "Friend", "other": ""},
    }

    # Act
    response = client.post(
        "/auth/register",
        data=json.dumps(register_data),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["msg"] == "A user with this email address already exists."


def test_register_failure_password_mismatch(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/auth/register' endpoint is posted with mismatching passwords
    THEN check that a 400 Bad Request error is returned
    """
    # Arrange
    register_data = {
        "name": "Another User",
        "email": "another@example.com",
        "password": "password123",
        "confirm_password": "password456_DIFFERENT",
        "discovered": {"value": "Other", "other": "Podcast"},
    }

    # Act
    response = client.post(
        "/auth/register",
        data=json.dumps(register_data),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    response_data = response.get_json()
    assert response_data["msg"] == "Password and Confirm Password do not match."


# ===================================================================
# MOCKING: Tests for Google Login and Email Sending (New Tests)
# ===================================================================


def test_login_with_google_new_user(client, mocker):
    """
    GIVEN a mocker to simulate Google's API responses for a new user
    WHEN the '/auth/login' endpoint is hit with a valid Google token
    THEN check that a new user is created and tokens are returned
    """
    # Arrange:
    # 1. Define the fake data Google's API will "return"
    fake_token_info = {"email": "google.user@example.com"}
    fake_user_info = {
        "email": "google.user@example.com",
        "given_name": "Google",
        "family_name": "User",
    }

    # 2. Create a mock function to replace `requests.get`
    #    It will return different data based on the URL it's called with.
    def mock_google_requests(*args, **kwargs):
        mock_response = MagicMock()
        if "tokeninfo" in args[0]:
            mock_response.json.return_value = fake_token_info
        elif "userinfo" in args[0]:
            mock_response.json.return_value = fake_user_info
        return mock_response

    # 3. Use mocker.patch to replace the real `requests.get` with our mock
    mocker.patch("requests.get", side_effect=mock_google_requests)

    # Act: Call the login endpoint with a fake Google token
    response = client.post(
        "/auth/login",
        data=json.dumps({"google_token": "fake_google_token", "locale": "en"}),
        content_type="application/json",
    )

    # Assert:
    # 1. Check the HTTP response
    assert response.status_code == 200
    assert "access_token" in response.get_json()

    # 2. Check that the new user was actually created in the database
    user = User.query.filter_by(email="google.user@example.com").first()
    assert user is not None
    assert user.first_name == "Google"


def test_forgot_password_sends_email(client, mocker):
    """
    GIVEN a mocker to simulate the email sending functionality
    WHEN the '/auth/forgot-password' endpoint is hit for an existing user
    THEN check that the email sending function is called correctly
    """
    # Arrange
    # 1. Patch the `send_email` method on the EmailManager instance.
    #    The path points to where the object is *used*.
    mock_send_email = mocker.patch(
        "controllers.auth_controller.current_app.email_manager.send_email"
    )

    forgot_password_data = {
        "email": "test@example.com"  # This user was created by the fixture
    }

    # Act
    response = client.post(
        "/auth/forgot-password",
        data=json.dumps(forgot_password_data),
        content_type="application/json",
    )

    # Assert
    # 1. Check the HTTP response
    assert response.status_code == 200
    assert response.get_json()["status"] == "success"

    # 2. Check that our mock email function was called exactly once
    mock_send_email.assert_called_once()

    # 3. (Optional) Check *what* the function was called with
    call_args, call_kwargs = mock_send_email.call_args
    assert call_args[0] == "test@example.com"  # Check recipient
    assert call_args[1] == "Mudar Senha"  # Check title


def test_refresh_token_success(client):
    """
    GIVEN a valid refresh token from a logged-in user
    WHEN the '/auth/refresh' endpoint is hit with that token
    THEN check that a new access token is returned
    """
    # Arrange:
    # 1. First, log in to get a valid refresh token.
    login_data = {"email": "test@example.com", "password": "password123"}
    login_response = client.post(
        "/auth/login", data=json.dumps(login_data), content_type="application/json"
    )
    assert login_response.status_code == 200
    refresh_token = login_response.get_json()["refresh_token"]

    # Act:
    # 2. Make a request to the refresh endpoint with the refresh token.
    response = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )

    # Assert:
    # 3. Check that the response is successful and contains a new access token.
    assert response.status_code == 200
    response_data = response.get_json()
    assert "access_token" in response_data


def test_new_password_success(client):
    """
    GIVEN a valid password reset token
    WHEN the '/auth/new-password' endpoint is hit with the token and a new password
    THEN check that the password is successfully updated
    """
    # Arrange:
    # 1. Get the user we want to create a token for.
    user = User.query.filter_by(email="test@example.com").first()
    assert user is not None

    # 2. Manually create a valid, non-expired token for this user.
    #    This simulates the token that would be sent via email.
    s = URLSafeSerializer(current_app.config["SECRET_KEY"])
    token = s.dumps(
        [
            datetime.now(timezone.utc).isoformat(),
            f"change_password.{user.id}",
        ]
    )

    # 3. Define the new password.
    new_password_data = {"token": token, "password": "my_brand_new_password"}

    # Act:
    # 4. Make the request to change the password.
    response = client.post(
        "/auth/new-password",
        data=json.dumps(new_password_data),
        content_type="application/json",
    )

    # Assert:
    # 5. Check that the response is successful.
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

    # 6. Verify that the user can now log in with the new password.
    login_data = {"email": "test@example.com", "password": "my_brand_new_password"}
    login_response = client.post(
        "/auth/login", data=json.dumps(login_data), content_type="application/json"
    )
    assert login_response.status_code == 200


def test_new_password_failure_invalid_token(client):
    """
    GIVEN an invalid or tampered password reset token
    WHEN the '/auth/new-password' endpoint is hit
    THEN check that a 400 Bad Request error is returned
    """
    # Arrange
    new_password_data = {
        "token": "this.is.an.invalid.token",
        "password": "some_password",
    }

    # Act
    response = client.post(
        "/auth/new-password",
        data=json.dumps(new_password_data),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400

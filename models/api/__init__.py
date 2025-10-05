from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# --- Generic Reusable Models ---


class ErrorMessage(BaseModel):
    """A generic error message response."""

    msg: str


class SuccessMessage(BaseModel):
    """A generic success message response."""

    status: str
    msg: str


# --- /login ---


class LoginRequest(BaseModel):
    """
    Request model for the login endpoint.
    Can accept email/password OR a Google token.
    """

    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=1)
    google_token: Optional[str] = None


class AuthTokenResponse(BaseModel):
    """Response model for successful authentication, providing tokens."""

    access_token: str
    refresh_token: str


# --- /register ---


class DiscoveredInfo(BaseModel):
    """Nested model for how a user discovered the service."""

    value: str
    other: Optional[str] = None


class RegisterRequest(BaseModel):
    """Request model for creating a new user."""

    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str
    discovered: DiscoveredInfo


class RegisterSuccessData(BaseModel):
    """The 'data' part of a successful registration response."""

    id: int


class RegisterSuccessResponse(BaseModel):
    """Full response model for a successful user registration."""

    status: str
    msg: str
    data: RegisterSuccessData


# --- /forgot-password ---


class ForgotPasswordRequest(BaseModel):
    """Request model for the forgot password endpoint."""

    email: Optional[EmailStr] = None


# --- /new-password ---


class NewPasswordRequest(BaseModel):
    """Request model for setting a new password using a token."""

    token: str
    password: str = Field(min_length=8)


# --- /refresh ---


class RefreshResponse(BaseModel):
    """Response model for refreshing an access token."""

    access_token: str


# ------


# Orm Mode
class OrmBase(BaseModel):
    id: int

    model_config = {"from_attributes": True}


from .user import UserDTO

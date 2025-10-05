from . import OrmBase

from factory import URL_SCHEMA

from flask import url_for
from pydantic import Field, computed_field


class UserDTO(OrmBase):
    fullname: str = Field(..., example="John Doe")
    email: str = Field(..., example="john.doe@example.com")

    @computed_field
    @property
    def image(self) -> str:
        return url_for(
            "image_controller.user_profile",
            user_id=self.id,
            _external=True,
            _scheme=URL_SCHEMA,
        )

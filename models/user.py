import base64
from datetime import datetime, timedelta, timezone

from flask import current_app, render_template, url_for
from itsdangerous import Serializer
from sqlalchemy.orm import deferred
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy.dialects.postgresql import JSONB

from factory import URL_SCHEMA, db
from utils.email_manager import EmailManager

from models.api import UserDTO


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True, index=True)
    first_name = db.Column(db.Unicode(64))
    last_name = db.Column(db.Unicode(64), default="")
    fullname = db.column_property(first_name + " " + last_name)

    username = db.Column(db.String(64), index=True)
    email = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), index=True)
    is_email_valid = db.Column(
        db.Integer, default=0
    )  # User has to valid its email following the validation link

    # For google login
    google_id = db.Column(db.String(25))

    # Personal Data
    cpf = deferred(db.Column(db.String), group="personal")
    gender = deferred(db.Column(db.String(32)), group="personal")
    birthday_date = deferred(db.Column(db.DateTime(timezone=True)), group="personal")

    original_profile_image_bytes = deferred(db.Column(db.LargeBinary), group="images")
    profile_image_bytes = deferred(db.Column(db.LargeBinary), group="images")

    # Location
    last_lat = deferred(db.Column(db.Float), group="location")
    last_lng = deferred(db.Column(db.Float), group="location")
    last_city = deferred(db.Column(db.Unicode(32)), group="location")
    last_region = deferred(db.Column(db.Unicode(32)), group="location")
    last_country = deferred(db.Column(db.Unicode(32)), group="location")
    last_location_update = deferred(
        db.Column(db.DateTime(timezone=True)), group="location"
    )

    def to_dict(self):
        return UserDTO.model_validate(self).model_dump()

    def to_simple_dict(self):
        return {
            "id": self.id,
            "name": self.fullname,
            "color": self.color,
            "image": url_for(
                "images_blueprint.user_profile",
                user_id=self.id,
                _external=True,
                _scheme=URL_SCHEMA,
            ),
        }

    @property
    def age(self):
        if self.birthday_date is None:
            return None

        today = datetime.now(timezone.utc)
        birthday = self.birthday_date
        age = today.year - birthday.year
        if today.month < birthday.month or (
            today.month == birthday.month and today.day < birthday.day
        ):
            age -= 1

        return age

    @property
    def is_location_updated(self):
        if self.last_location_update is None:
            return False

        now = datetime.now(timezone.utc)

        if now - self.last_location_update > timedelta(days=1):
            return False

        return True

    @property
    def original_profile_image(self):
        return "data:;base64," + base64.b64encode(
            self.original_profile_image_bytes
        ).decode("utf-8")

    @property
    def profile_image(self):
        if self.profile_image_bytes is not None:
            return "data:;base64," + base64.b64encode(self.profile_image_bytes).decode(
                "utf-8"
            )

        return url_for("static", filename="photos/default.png")

    def generate_confirmation_token(self):
        serializer = Serializer(current_app.config["SECRET_KEY"])
        return serializer.dumps({"confirm": self.id})

    def confirm_email(self, token):
        serializer = Serializer(current_app.config["SECRET_KEY"])

        try:
            data = serializer.loads(token)
        except:
            return False

        if data.get("confirm") != self.id:
            return False

        self.is_email_valid = True
        db.session.add(self)
        return True

    def send_confirmation_code(self):
        try:
            email_manager = EmailManager(current_app)
            token = self.generate_confirmation_token()
            email_manager.send_email(
                self.email,
                "Confirme seu email",
                render_template("emails/confirm_email.txt", user=self, token=token),
                render_template(
                    "emails/HTML/confirm_email.html", user=self, token=token
                ),
                asynchronous=True,
            )
            return True
        except Exception:
            return False

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    def ping(self):
        self.last_seen = datetime.now(timezone.utc)
        db.session.add(self)
        db.session.commit()

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def __repr__(self):
        return "<User {} {} - {}>".format(self.first_name, self.last_name, self.role)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)

        # role is a backref from Role table
        # pylint: disable=access-member-before-definition
        if self.role is None:
            admin_email = current_app.config.get("ADMIN_EMAIL")
            if admin_email and self.email in admin_email:
                self.role = Role.query.filter_by(permissions=0xFF).first()
        if self.role is None:
            self.role = Role.query.filter_by(default=1).first()

    # Check if the user can perform a specif action
    def can(self, permissions):
        return (
            self.role is not None
            and (self.role.permissions & permissions) == permissions
        )


class Permission:
    ACTION_1 = 0x01
    ACTION_2 = 0x02
    ACTION_3 = 0x04
    ACTION_4 = 0x08
    MODERATE = 0x10
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Integer, default=0, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship("User", backref="role", lazy="dynamic")

    def __repr__(self):
        return "<Role {}>".format(self.name)

    @staticmethod
    def insert_roles():
        roles = {
            "User": (Permission.ACTION_1, 1),
            "Moderator": (
                Permission.ACTION_1
                | Permission.ACTION_2
                | Permission.ACTION_3
                | Permission.ACTION_4
                | Permission.MODERATE,
                0,
            ),
            "Administrator": (0xFF, 0),
        }

        for role_name in roles:
            role = Role.query.filter_by(name=role_name).first()
            if role is None:
                role = Role(name=role_name)
            role.permissions = roles[role_name][0]
            role.default = roles[role_name][1]
            db.session.add(role)
        db.session.commit()

"""
Centralized place to initialize Flask extensions.
This avoids circular import issues.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from flask_migrate import Migrate
from flask_cors import CORS
from spectree import SpecTree, SecurityScheme

db = SQLAlchemy()
jwt = JWTManager()
cache = Cache()
migrate = Migrate()
cors = CORS(supports_credentials=True)
api = SpecTree(
    "flask",
    mode="strict",
    security_schemes=[
        SecurityScheme(
            name="api_key",
            data={
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": 'Use: "Bearer token"',
            },
        )
    ],
    security={"api_key": []},
)

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import os
import requests

asteroid_blueprint = Blueprint("asteroid_controller", __name__, url_prefix="/asteroid")


@asteroid_blueprint.route("/feed", methods=["GET"])
def feed():
    """
    Proxy to NASA NEO Feed API:
    GET /asteroid/feed?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

    - Validates date format and prevents future dates.
    - Reads NASA API key from environment variable NASA_API_KEY.
    - Returns NASA's JSON response (so frontend can reuse existing parsing).
    """
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date", start_date)

    # default to today if no start_date provided
    if not start_date:
        start_date = date.today().isoformat()
        end_date = start_date

    # validate format YYYY-MM-DD
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

    today = date.today()
    if sd > today or ed > today:
        return jsonify({"message": f"Dates cannot be in the future. Max allowed: {today.isoformat()}"}), 400
    if ed < sd:
        return jsonify({"message": "end_date cannot be before start_date."}), 400

    nasa_key = os.getenv("NASA_API_KEY")
    if not nasa_key:
        current_app.logger.warning("NASA_API_KEY not set; using DEMO_KEY (rate-limited).")

    nasa_url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {
        "start_date": sd.isoformat(),
        "end_date": ed.isoformat(),
        "api_key": nasa_key or "DEMO_KEY",
    }

    try:
        resp = requests.get(nasa_url, params=params, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        current_app.logger.exception("Error fetching data from NASA NEO feed")
        return jsonify({"message": "Failed to fetch asteroid data from upstream.", "details": str(exc)}), 502

    try:
        return jsonify(resp.json())
    except ValueError:
        return jsonify({"message": "Upstream returned invalid JSON."}), 502

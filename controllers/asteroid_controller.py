from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import os
import requests
import json
import math
import time

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

WORLDPOP_BASE = os.getenv('WORLDPOP_BASE', 'https://api.worldpop.org/v1/services/stats')
WORLDPOP_DATASET = os.getenv('WORLDPOP_DATASET', 'wpgppop')
WORLDPOP_YEAR = os.getenv('WORLDPOP_YEAR', '2020')
WORLDPOP_KEY = os.getenv('WORLDPOP_KEY')

NOMINATIM_BASE = 'https://nominatim.openstreetmap.org/reverse'


@asteroid_blueprint.route('/simulate-impact', methods=['POST'])
def simulate_impact():
    """
    Accepts a JSON body with either:
      - 'geojson' (Polygon)  OR
      - 'location': { lat, lon, radius_km } plus optionally 'asteroid' object
    Uses WorldPop stats service to get population inside the (server-built) polygon,
    uses asteroid info (if provided) to estimate lethality, and returns results.
    """
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'error': 'missing payload'}), 400

    # Accept geojson directly (backwards compatible)
    geojson = payload.get('geojson')

    # Or accept simple location + radius and build polygon server-side
    location = payload.get('location')
    asteroid = payload.get('asteroid')  # optional full object from frontend

    if not geojson and not location:
        return jsonify({'error': 'either geojson or location required'}), 400

    if not geojson:
        # Validate location
        try:
            lat = float(location.get('lat'))
            lon = float(location.get('lon'))
            radius_km = float(location.get('radius_km', 5.0))
        except Exception:
            return jsonify({'error': 'invalid location payload'}), 400

        # Build polygon (approximate great-circle circle) with N points
        def destination_point(lat_deg, lon_deg, bearing_deg, distance_km):
            R = 6371.0088  # Earth radius km
            lat1 = math.radians(lat_deg)
            lon1 = math.radians(lon_deg)
            bearing = math.radians(bearing_deg)
            d = distance_km / R
            lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(bearing))
            lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(d) * math.cos(lat1),
                                     math.cos(d) - math.sin(lat1) * math.sin(lat2))
            return math.degrees(lat2), math.degrees(lon2)

        steps = 64
        coords = []
        for i in range(steps + 1):
            bearing = float(i) * (360.0 / steps)
            lat2, lon2 = destination_point(lat, lon, bearing, radius_km)
            coords.append([lon2, lat2])  # GeoJSON order: lon, lat
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords]
                    }
                }
            ]
        }

    # Now call WorldPop stats service
    wp_params = {
        'dataset': WORLDPOP_DATASET,
        'year': WORLDPOP_YEAR,
        'geojson': json.dumps(geojson),
        'runasync': 'false'
    }
    if WORLDPOP_KEY:
        wp_params['key'] = WORLDPOP_KEY

    try:
        resp = requests.get(WORLDPOP_BASE, params=wp_params, timeout=60)
    except requests.exceptions.RequestException as exc:
        current_app.logger.exception("WorldPop request failed")
        return jsonify({'error': 'WorldPop request failed', 'details': str(exc)}), 502

    if resp.status_code != 200:
        return jsonify({'error': 'WorldPop request failed', 'details': resp.text}), 502

    wp_json = resp.json()
    population = None

    # handle both direct data and possible async task response
    if wp_json.get('status') == 'created' and 'taskid' in wp_json:
        taskid = wp_json['taskid']
        task_url = f'https://api.worldpop.org/v1/tasks/{taskid}'
        # poll briefly
        for _ in range(30):
            t = requests.get(task_url)
            if t.status_code == 200:
                tj = t.json()
                if tj.get('status') == 'finished':
                    population = tj.get('data', {}).get('total_population', 0)
                    break
            time.sleep(0.5)
        else:
            return jsonify({'error': 'WorldPop task did not finish in time'}), 504
    else:
        population = wp_json.get('data', {}).get('total_population') if wp_json.get('data') else None

    if population is None:
        return jsonify({'error': 'Could not extract population from WorldPop response', 'raw': wp_json}), 500

    # Reverse geocode center for display (best-effort)
    place = None
    try:
        # compute centroid from polygon's first feature
        features = geojson.get('features') if isinstance(geojson, dict) else None
        if features and len(features) > 0:
            geom = features[0].get('geometry')
            if geom and geom.get('type') == 'Polygon':
                ring = geom['coordinates'][0]
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                lon_cent = sum(xs) / len(xs)
                lat_cent = sum(ys) / len(ys)
                r = requests.get(NOMINATIM_BASE, params={'lat': lat_cent, 'lon': lon_cent, 'format': 'jsonv2', 'zoom': 10}, headers={'User-Agent': 'asteroid-sim/1.0'}, timeout=10)
                if r.status_code == 200:
                    place = r.json().get('display_name')
    except Exception:
        place = None

    # Compute lethality using asteroid info when available
    try:
        # default lethality (if no asteroid info): simple function of radius
        if asteroid and isinstance(asteroid, dict):
            # try to use impact energy if present
            impact_energy_tnt = asteroid.get('impact_energy_tnt')
            mass_kg = asteroid.get('mass_kg')
            v_km_s = asteroid.get('entry_speed_km_s') or asteroid.get('relative_velocity_km_s')
            # if impact_energy not available, compute from mass & speed if possible
            if impact_energy_tnt is None and mass_kg and v_km_s:
                v_m_s = float(v_km_s) * 1000.0
                energy_j = 0.5 * float(mass_kg) * v_m_s * v_m_s
                impact_energy_tnt = energy_j / 4.184e9
            # determine lethality from energy thresholds
            lethality = 0.5  # baseline
            if impact_energy_tnt is not None:
                e = float(impact_energy_tnt)
                if e >= 1e6:
                    lethality = 0.99
                elif e >= 1e4:
                    lethality = 0.9
                elif e >= 1e2:
                    lethality = 0.75
                elif e >= 1:
                    lethality = 0.5
                else:
                    lethality = 0.25
            else:
                # fallback to radius heuristic
                try:
                    radius_km_val = float(location.get('radius_km', 5.0)) if location else 5.0
                except Exception:
                    radius_km_val = 5.0
                lethality = 0.9 if radius_km_val >= 5 else 0.5
        else:
            # no asteroid info: simple radius-based lethality
            radius_km_val = float(location.get('radius_km', 5.0)) if location else 5.0
            lethality = 0.9 if radius_km_val >= 5 else 0.5

        estimated_kills = int(round(population * lethality))
    except Exception:
        estimated_kills = None

    return jsonify({
        'place': place,
        'population': int(round(population)),
        'estimated_kills': estimated_kills,
        'lethality_used': float(lethality),
    })
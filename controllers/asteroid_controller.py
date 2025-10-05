from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import os
import requests
import json
import math
import time

from spectree import SpecTree, Response
from pydantic import BaseModel, Field

from factory import api, cache, db


class AsteroidRequest(BaseModel):
    start_date: str = Field(
        ..., example="2025-10-05", description="Start date (YYYY-MM-DD)"
    )
    end_date: str | None = Field(
        None, example="2025-10-05", description="End date (YYYY-MM-DD)"
    )


class AsteroidItem(BaseModel):
    id: str
    name: str
    distance: float


class AsteroidFeedResponse(BaseModel):
    asteroids: list[AsteroidItem]


class ErrorResponse(BaseModel):
    message: str
    details: str | None = None


class AsteroidInfo(BaseModel):
    diameter: float
    mass: float
    velocity: float
    distance: float
    magnitude: float


asteroid_blueprint = Blueprint("asteroid_controller", __name__, url_prefix="/asteroid")


@asteroid_blueprint.route("/feed", methods=["GET"])
@api.validate(
    query=AsteroidRequest,
    resp=Response(HTTP_200=AsteroidFeedResponse),
    tags=["asteroid"],
)
def feed():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date", start_date)

    if not start_date:
        start_date = date.today().isoformat()
        end_date = start_date

    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD."}), 400

    today = date.today()
    if sd > today or ed > today:
        return (
            jsonify(
                {
                    "message": f"Dates cannot be in the future. Max allowed: {today.isoformat()}"
                }
            ),
            400,
        )
    if ed < sd:
        return jsonify({"message": "end_date cannot be before start_date."}), 400

    nasa_key = os.getenv("NASA_API_KEY") or "DEMO_KEY"
    if nasa_key == "DEMO_KEY":
        current_app.logger.warning(
            "NASA_API_KEY not set; using DEMO_KEY (rate-limited)."
        )

    nasa_url = "https://api.nasa.gov/neo/rest/v1/feed"
    params = {
        "start_date": sd.isoformat(),
        "end_date": ed.isoformat(),
        "api_key": nasa_key,
    }

    try:
        resp = requests.get(nasa_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        current_app.logger.exception("Error fetching data from NASA NEO feed")
        return (
            jsonify(
                {
                    "message": "Failed to fetch asteroid data from upstream.",
                    "details": str(exc),
                }
            ),
            502,
        )
    except ValueError as exc:
        return (
            jsonify({"message": "Invalid JSON from upstream", "details": str(exc)}),
            502,
        )

    near_earth_objects = data.get("near_earth_objects", {})

    # Build list of simple asteroid objects (id, name, date, is_potentially_hazardous)
    formatted_asteroids = []
    for date_str, asteroids in near_earth_objects.items():
        for asteroid in asteroids:
            formatted_asteroids.append(
                {
                    "id": asteroid.get("id"),
                    "name": asteroid.get("name"),
                    "distance": asteroid.get("close_approach_data", [{}])[0]
                    .get("miss_distance", {})
                    .get("kilometers", 0.0),
                }
            )

    return jsonify({"asteroids": formatted_asteroids}), 200


@asteroid_blueprint.route("/get_by_id/<asteroid_id>", methods=["GET"])
# @api.validate(
#     resp=Response(HTTP_200=AsteroidInfo),
#     tags=["asteroid"],
# )
def get_asteroid_data(asteroid_id):
    nasa_key = os.getenv("NASA_API_KEY") or "DEMO_KEY"
    if nasa_key == "DEMO_KEY":
        current_app.logger.warning(
            "NASA_API_KEY not set; using DEMO_KEY (rate-limited)."
        )

    # use the lookup endpoint for a single NEO by id
    nasa_url = f"https://api.nasa.gov/neo/rest/v1/neo/{asteroid_id}"
    params = {"api_key": nasa_key}

    try:
        resp = requests.get(nasa_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as exc:
        current_app.logger.exception("NASA returned HTTP error")
        return (
            jsonify(
                {
                    "message": "Failed to fetch asteroid data from upstream.",
                    "details": str(exc),
                }
            ),
            502,
        )
    except requests.exceptions.RequestException as exc:
        current_app.logger.exception("Error fetching data from NASA NEO API")
        return (
            jsonify(
                {
                    "message": "Failed to fetch asteroid data from upstream.",
                    "details": str(exc),
                }
            ),
            502,
        )
    except ValueError as exc:
        return jsonify({"message": "Invalid JSON from NASA", "details": str(exc)}), 502

    gravitational_constant = 6.67430 * (10 ** (-11))  # m^3 kg^-1 s^-2
    sun_mass = 1.9885 * (10**30)  # kg

    diameter = (
        data["estimated_diameter"]["meters"]["estimated_diameter_max"]
        + data["estimated_diameter"]["meters"]["estimated_diameter_min"]
    ) / 2
    mass = ((diameter / 2) ** 3) * 2500 * (4 / 3) * math.pi
    eccentricity = float(data["orbital_data"]["eccentricity"])
    minor_axis = float(
        float(data["orbital_data"]["semi_major_axis"])
        * math.sqrt(1 - (eccentricity) ** 2)
    )

    aphelion = float(data['orbital_data']['aphelion_distance']) * 149597870700

    info = {
        "diameter": diameter,
        "mass": mass,
        "velocity": data["close_approach_data"][0]["relative_velocity"]["kilometers_per_second"],
        "distance": data["close_approach_data"][0]["miss_distance"]["kilometers"],
        "magnitude": data["absolute_magnitude_h"],
        "closest_approach_date": data["close_approach_data"][0]["close_approach_date"],
        "danger": data["is_potentially_hazardous_asteroid"],
        "inclination": data["orbital_data"]["inclination"],
        "major-axis": data["orbital_data"]["semi_major_axis"],
        "minor-axis": minor_axis,
        "eccentricity": data["orbital_data"]["eccentricity"],
        "period": data["orbital_data"]["orbital_period"],
        "eccentricity": data["orbital_data"]["eccentricity"],
        "aphelion": aphelion,
        "perihelion": data["orbital_data"]["perihelion_distance"],
        "total_energy": (mass * gravitational_constant * sun_mass)
        / (2 * (float(data["orbital_data"]["semi_major_axis"]))),
    }

    return jsonify(info), 200


WORLDPOP_BASE = os.getenv("WORLDPOP_BASE", "https://api.worldpop.org/v1/services/stats")
WORLDPOP_DATASET = os.getenv("WORLDPOP_DATASET", "wpgppop")
WORLDPOP_YEAR = os.getenv("WORLDPOP_YEAR", "2020")
WORLDPOP_KEY = os.getenv("WORLDPOP_KEY")

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/reverse"


@asteroid_blueprint.route("/simulate-impact", methods=["POST"])
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
        return jsonify({"error": "missing payload"}), 400

    # Accept geojson directly (backwards compatible)
    geojson = payload.get("geojson")

    # Or accept simple location + radius and build polygon server-side
    location = payload.get("location")
    asteroid = payload.get("asteroid")  # optional full object from frontend

    gravitational_constant = 6.67430 * (10 ** (-11))  # m^3 kg^-1 s^-2
    sun_mass = 1.9885 * (10**30)  # kg
    aphelion = float(asteroid['orbital_data']['aphelion_distance'])

    if not geojson and not location:
        return jsonify({"error": "either geojson or location required"}), 400

    if not geojson:
        # Validate location
        try:
            lat = float(location.get("lat"))
            lon = float(location.get("lon"))
            radius_km = float(location.get("radius_km", 5.0))
        except Exception:
            return jsonify({"error": "invalid location payload"}), 400

        # Build polygon (approximate great-circle circle) with N points
        def destination_point(lat_deg, lon_deg, bearing_deg, distance_km):
            R = 6371.0088  # Earth radius km
            lat1 = math.radians(lat_deg)
            lon1 = math.radians(lon_deg)
            bearing = math.radians(bearing_deg)
            d = distance_km / R
            lat2 = math.asin(
                math.sin(lat1) * math.cos(d)
                + math.cos(lat1) * math.sin(d) * math.cos(bearing)
            )
            lon2 = lon1 + math.atan2(
                math.sin(bearing) * math.sin(d) * math.cos(lat1),
                math.cos(d) - math.sin(lat1) * math.sin(lat2),
            )
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
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }
            ],
        }

    # Now call WorldPop stats service
    wp_params = {
        "dataset": WORLDPOP_DATASET,
        "year": WORLDPOP_YEAR,
        "geojson": json.dumps(geojson),
        "runasync": "false",
    }
    # if WORLDPOP_KEY:
    #     wp_params["key"] = WORLDPOP_KEY

    try:
        resp = requests.get(WORLDPOP_BASE, params=wp_params, timeout=60)
    except requests.exceptions.RequestException as exc:
        current_app.logger.exception("WorldPop request failed")
        return jsonify({"error": "WorldPop request failed", "details": str(exc)}), 502

    if resp.status_code != 200:
        return jsonify({"error": "WorldPop request failed", "details": resp.text}), 502

    wp_json = resp.json()
    population = None

    # handle both direct data and possible async task response
    if wp_json.get("status") == "created" and "taskid" in wp_json:
        taskid = wp_json["taskid"]
        task_url = f"https://api.worldpop.org/v1/tasks/{taskid}"
        # poll briefly
        for _ in range(30):
            t = requests.get(task_url)
            if t.status_code == 200:
                tj = t.json()
                if tj.get("status") == "finished":
                    population = tj.get("data", {}).get("total_population", 0)
                    break
            time.sleep(0.5)
        else:
            return jsonify({"error": "WorldPop task did not finish in time"}), 504
    else:
        population = (
            wp_json.get("data", {}).get("total_population")
            if wp_json.get("data")
            else None
        )

    if population is None:
        return (
            jsonify(
                {
                    "error": "Could not extract population from WorldPop response",
                    "raw": wp_json,
                }
            ),
            500,
        )

    # Reverse geocode center for display (best-effort)
    place = None
    try:
        # compute centroid from polygon's first feature
        features = geojson.get("features") if isinstance(geojson, dict) else None
        if features and len(features) > 0:
            geom = features[0].get("geometry")
            if geom and geom.get("type") == "Polygon":
                ring = geom["coordinates"][0]
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                lon_cent = sum(xs) / len(xs)
                lat_cent = sum(ys) / len(ys)
                r = requests.get(
                    NOMINATIM_BASE,
                    params={
                        "lat": lat_cent,
                        "lon": lon_cent,
                        "format": "jsonv2",
                        "zoom": 10,
                    },
                    headers={"User-Agent": "asteroid-sim/1.0"},
                    timeout=10,
                )
                if r.status_code == 200:
                    place = r.json().get("display_name")
    except Exception:
        place = None

    # Compute lethality using asteroid info when available
    try:
        # default lethality (if no asteroid info): simple function of radius
        if asteroid and isinstance(asteroid, dict):
            # try to use impact energy if present
            impact_energy_tnt = asteroid.get("impact_energy_tnt")
            mass_kg = asteroid.get("mass_kg")
            v_km_s = asteroid.get("entry_speed_km_s") or asteroid.get(
                "relative_velocity_km_s"
            )
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
                    radius_km_val = (
                        float(location.get("radius_km", 5.0)) if location else 5.0
                    )
                except Exception:
                    radius_km_val = 5.0
                lethality = 0.9 if radius_km_val >= 5 else 0.5
        else:
            # no asteroid info: simple radius-based lethality
            radius_km_val = float(location.get("radius_km", 5.0)) if location else 5.0
            lethality = 0.9 if radius_km_val >= 5 else 0.5

        estimated_kills = int(round(population * lethality))
    except Exception:
        estimated_kills = None

    density = 2500

    diameter = None
    if asteroid and isinstance(asteroid, dict):
        # frontend mapping uses diameterMeters (meters)
        for k in ("diameter", "diameterMeters", "diameter_m", "diameter_meters"):
            if k in asteroid and asteroid[k] is not None:
                try:
                    diameter = float(asteroid[k])
                    break
                except (TypeError, ValueError):
                    diameter = None

    # fallback to NASA-style estimated_diameter object (min/max average)
    if diameter is None and asteroid and isinstance(asteroid, dict):
        est = asteroid.get("estimated_diameter") or asteroid.get("estimatedDiameter")
        if isinstance(est, dict):
            meters = est.get("meters") or est.get("m")
            if isinstance(meters, dict):
                mn = meters.get("estimated_diameter_min")
                mx = meters.get("estimated_diameter_max")
                try:
                    if mn is not None and mx is not None:
                        diameter = (float(mn) + float(mx)) / 2.0
                except (TypeError, ValueError):
                    diameter = None

    impact_velocity = math.sqrt((gravitational_constant * 2 * sun_mass)/aphelion) #VEJA QUE ESSA VELOCIDADE É A VELOCIDADE DE IMPACTO MÁXIMA, POSTERIORMENTE VAMOS COLOCAR QUE ESSE É O CASO EXTREMO, O PROGRAMA ESTÁ RETORNANDO A VELOCIDADE EM M/S!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!, E SE FAZER CALCULOS COM ELA, MANTER ASSIM, MAS FICA MAIS BONITO MANDAR PRO USUARIO DIVIDIDO POR 1000, POIS ASSIM APARECE EM KM/S
    
    velocity_km_s = None
    if asteroid and isinstance(asteroid, dict):
        velocity_km_s = (
            asteroid.get("entry_speed_km_s")
            or asteroid.get("relative_velocity_km_s")
            or asteroid.get("relative_velocity")
            or asteroid.get("relativeVelocity")
        )

        # if nested close_approach_data exists in payload, try it safely
        if velocity_km_s is None:
            cad = asteroid.get("close_approach_data") or asteroid.get("closeApproachData")
            if isinstance(cad, list) and len(cad) > 0 and isinstance(cad[0], dict):
                rv = cad[0].get("relative_velocity") or cad[0].get("relativeVelocity") or {}
                velocity_km_s = rv.get("kilometers_per_second") or rv.get("kilometersPerSecond")

    try:
        velocity_km_s = float(velocity_km_s) if velocity_km_s is not None else None
    except (TypeError, ValueError):
        velocity_km_s = None

    # fallback: if velocity isn't provided, use the computed 'impact_velocity' (m/s -> km/s)
    if velocity_km_s is None:
        velocity_km_s = (impact_velocity / 1000.0) if impact_velocity is not None else 20.0

    # convert to m/s for energy math
    velocity_m_s = float(velocity_km_s) * 1000.0
    
    volume = (4/3)*math.pi * (diameter/2)**3

    mass = density * volume

    k_energy = 0.5 * mass * velocity_m_s**2

    k_energy_mt = k_energy / (4.184*(10**15)) 
    crater_diameter = 0.765 * k_energy_mt**(1/3.4) * 10

    crater_depth = 0.4*(crater_diameter**0.3)

    fireball_radius = 60 * (k_energy_mt**(1/3))

    shock_wave = 3 * (k_energy_mt**(1/3))

    pressure_at_20radius = 15 * (k_energy_mt**(1/3))/(20*(diameter/2))

    wind_velocity_at_20radius = 1055 * (pressure_at_20radius)/(math.sqrt(103+7*pressure_at_20radius))

    sismic_energy = 0.0001 * k_energy
    sismic_magnitude = (3/2) * (math.log10(sismic_energy) - 4.8)


    #precisa dar round(x, 3) em TODOS AQUI EM BAIXO!

    return jsonify(
        {
            "place": place,
            "population": int(round(population)),
            "estimated_kills": estimated_kills,
            "lethality_used": float(lethality),
            "crater_radius": float(crater_diameter/2),
            "impact_velocity_km_s": float(impact_velocity) / 1000,
            "impact_energy_mt": float(k_energy_mt), #In MegaTNT
            "fireball_radius_km": float(fireball_radius),
            "shock_wave_km": float(shock_wave),
            "wind_speed_kmh": float(wind_velocity_at_20radius),
            "sismic_magnitude": sismic_magnitude,
        }
    )

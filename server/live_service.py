import os
import re
import threading
import time
import unicodedata

from pathlib import Path

import requests

from dotenv import load_dotenv

from sportsdb_service import (
    SportsDBService,
)

# ============================================================
# RUTAS
# ============================================================

SERVER_DIR = Path(__file__).resolve().parent

PROJECT_DIR = SERVER_DIR.parent


load_dotenv(PROJECT_DIR / ".env")


# ============================================================
# API FOOTBALL
# ============================================================

API_BASE_URL = "https://v3.football.api-sports.io"

API_FOOTBALL_KEY = os.getenv(
    "API_FOOTBALL_KEY",
    "",
)


LIGA_MX_ID = 262

TIMEZONE = "America/Mazatlan"


# ============================================================
# MODO API
# ============================================================

API_FOOTBALL_MODE = os.getenv(
    "API_FOOTBALL_MODE",
    "FREE",
).upper()


# ============================================================
# POLLING
#
# FREE:
# aproximadamente 1 consulta cada 90 s.
#
# Puedes cambiarlo luego en Railway/.env.
# ============================================================

OVERLAY_CACHE_SECONDS = int(
    os.getenv(
        "API_FOOTBALL_OVERLAY_SECONDS",
        "90",
    )
)


DETAIL_CACHE_SECONDS = int(
    os.getenv(
        "API_FOOTBALL_DETAIL_SECONDS",
        "90",
    )
)


RESOLVE_CACHE_SECONDS = 60 * 60 * 4


# ============================================================
# HTTP
# ============================================================

_SESSION = requests.Session()


# ============================================================
# CACHE
# ============================================================

_CACHE = {}

_CACHE_LOCK = threading.Lock()


# ============================================================
# QUOTA
# ============================================================

QUOTA_STATUS = {
    "limit": None,
    "remaining": None,
    "last_error": None,
    "mode": API_FOOTBALL_MODE,
}


# ============================================================
# FINALIZADOS EN ESTA EJECUCIÓN
# ============================================================

_FINISHED_MATCHES = set()


# ============================================================
# NORMALIZAR TEXTO
# ============================================================


def _normalize_text(
    value,
):

    value = str(value or "")

    value = unicodedata.normalize(
        "NFD",
        value,
    )

    value = "".join(char for char in value if (unicodedata.category(char) != "Mn"))

    value = value.casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(value.split())


# ============================================================
# ALIASES
# ============================================================

TEAM_ALIASES = {
    "club america": "america",
    "america": "america",
    "cf america": "america",
    "pumas unam": "pumas",
    "unam pumas": "pumas",
    "unam": "pumas",
    "u n a m pumas": "pumas",
    "guadalajara": "chivas",
    "cd guadalajara": "chivas",
    "guadalajara chivas": "chivas",
    "chivas": "chivas",
    "fc juarez": "juarez",
    "juarez": "juarez",
    "club tijuana": "tijuana",
    "tijuana": "tijuana",
    "atletico san luis": "san luis",
    "san luis": "san luis",
    "club leon": "leon",
    "leon": "leon",
    "cf pachuca": "pachuca",
    "pachuca": "pachuca",
    "club necaxa": "necaxa",
    "necaxa": "necaxa",
    "club puebla": "puebla",
    "puebla": "puebla",
    "club queretaro": "queretaro",
    "queretaro": "queretaro",
    "santos laguna": "santos",
    "santos": "santos",
    "tigres uanl": "tigres",
    "tigres": "tigres",
    "toluca": "toluca",
    "deportivo toluca": "toluca",
    "cruz azul": "cruz azul",
    "atlas": "atlas",
    "monterrey": "monterrey",
    "rayados": "monterrey",
    "rayados de monterrey": "monterrey",
    "mazatlan": "mazatlan",
    "atlante": "mazatlan",
}


def _canonical_team(
    value,
):

    normalized = _normalize_text(value)

    return TEAM_ALIASES.get(
        normalized,
        normalized,
    )


# ============================================================
# CACHE KEY
# ============================================================


def _cache_key(
    path,
    params,
):

    return (
        path,
        tuple(
            sorted(
                (
                    str(key),
                    str(value),
                )
                for key, value in params.items()
            )
        ),
    )


# ============================================================
# SAFE NUMBER
# ============================================================


def _safe_number(
    value,
):

    if value is None:
        return None

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        return value

    text = str(value).strip()

    if not text:
        return None

    if text.endswith("%"):

        text = text[:-1]

    try:

        number = float(text)

        if number.is_integer():

            return int(number)

        return number

    except ValueError:

        return None


# ============================================================
# QUOTA
# ============================================================


def get_quota_status():

    return {**QUOTA_STATUS}


# ============================================================
# SERVICE
# ============================================================


class LiveFootballService:

    def __init__(
        self,
    ):

        self.api_key = API_FOOTBALL_KEY

        self.sportsdb = SportsDBService()

    # ========================================================
    # API DISPONIBLE
    # ========================================================

    def has_api_football(
        self,
    ):

        return bool(self.api_key)

    # ========================================================
    # ACTUALIZAR QUOTA
    # ========================================================

    def _update_quota(
        self,
        response,
    ):

        limit = response.headers.get("x-ratelimit-requests-limit")

        remaining = response.headers.get("x-ratelimit-requests-remaining")

        if limit is not None:

            try:

                QUOTA_STATUS["limit"] = int(limit)

            except ValueError:

                pass

        if remaining is not None:

            try:

                QUOTA_STATUS["remaining"] = int(remaining)

            except ValueError:

                pass

    # ========================================================
    # DETECTAR CUOTA AGOTADA
    # ========================================================

    def _is_quota_error(
        self,
        message,
    ):

        normalized = str(message or "").casefold()

        return (
            "request limit" in normalized
            or "reached the request limit" in normalized
            or "requests:" in normalized
        )

    # ========================================================
    # API GET
    # ========================================================

    def _api_get(
        self,
        path,
        params=None,
        cache_seconds=OVERLAY_CACHE_SECONDS,
        allow_stale=True,
    ):

        if not self.api_key:

            raise RuntimeError("API-Football no está configurada.")

        params = params or {}

        key = _cache_key(
            path,
            params,
        )

        now = time.time()

        cached = None

        with _CACHE_LOCK:

            cached = _CACHE.get(key)

            if cached:

                age = now - cached["timestamp"]

                if age < cache_seconds:

                    return {
                        "data": cached["data"],
                        "cached": True,
                        "stale": False,
                        "age_seconds": int(age),
                    }

        # ====================================================
        # SI SABEMOS QUE QUEDAN 0 REQUESTS
        # EVITAMOS LLAMAR OTRA VEZ
        # ====================================================

        if QUOTA_STATUS["remaining"] == 0:

            if allow_stale and cached:

                return {
                    "data": cached["data"],
                    "cached": True,
                    "stale": True,
                    "quota_exhausted": True,
                }

            raise RuntimeError("La cuota diaria de API-Football " "está agotada.")

        url = f"{API_BASE_URL}{path}"

        try:

            response = _SESSION.get(
                url,
                headers={
                    "x-apisports-key": self.api_key,
                    "Accept": "application/json",
                },
                params=params,
                timeout=15,
            )

            self._update_quota(response)

            if not response.ok:

                raise RuntimeError(
                    "API-Football respondió " f"HTTP {response.status_code}."
                )

            payload = response.json()

            errors = payload.get("errors")

            if errors:

                if isinstance(
                    errors,
                    dict,
                ):

                    message = "; ".join(
                        f"{key}: {value}" for key, value in errors.items()
                    )

                elif isinstance(
                    errors,
                    list,
                ):

                    message = "; ".join(
                        map(
                            str,
                            errors,
                        )
                    )

                else:

                    message = str(errors)

                QUOTA_STATUS["last_error"] = message

                if self._is_quota_error(message):

                    QUOTA_STATUS["remaining"] = 0

                raise RuntimeError(f"API-Football: {message}")

            data = payload.get("response") or []

            with _CACHE_LOCK:

                _CACHE[key] = {
                    "timestamp": now,
                    "data": data,
                }

            QUOTA_STATUS["last_error"] = None

            return {
                "data": data,
                "cached": False,
                "stale": False,
                "age_seconds": 0,
            }

        except Exception as error:

            # =================================================
            # STALE CACHE
            # =================================================

            if allow_stale and cached:

                return {
                    "data": cached["data"],
                    "cached": True,
                    "stale": True,
                    "error": str(error),
                }

            raise

    # ========================================================
    # BUSCAR MATCH API EN LISTA
    # ========================================================

    def _find_matching_fixture(
        self,
        schedule_match,
        api_fixtures,
    ):

        target_home = _canonical_team(
            schedule_match.get(
                "home",
                {},
            ).get("name")
        )

        target_away = _canonical_team(
            schedule_match.get(
                "away",
                {},
            ).get("name")
        )

        for fixture in api_fixtures:

            league_id = fixture.get(
                "league",
                {},
            ).get("id")

            if league_id != LIGA_MX_ID:

                continue

            api_home = _canonical_team(
                fixture.get(
                    "teams",
                    {},
                )
                .get(
                    "home",
                    {},
                )
                .get("name")
            )

            api_away = _canonical_team(
                fixture.get(
                    "teams",
                    {},
                )
                .get(
                    "away",
                    {},
                )
                .get("name")
            )

            if api_home == target_home and api_away == target_away:

                return fixture

        return None

    # ========================================================
    # APLICAR LIVE OVERLAY
    # ========================================================

    def _apply_overlay(
        self,
        schedule_match,
        fixture,
    ):

        if not fixture:

            return schedule_match

        api_fixture = fixture.get(
            "fixture",
            {},
        )

        teams = fixture.get(
            "teams",
            {},
        )

        goals = fixture.get(
            "goals",
            {},
        )

        status = api_fixture.get(
            "status",
            {},
        )

        status_short = status.get("short") or "NS"

        live_verified = status_short in {
            "1H",
            "HT",
            "2H",
            "ET",
            "BT",
            "P",
            "INT",
            "SUSP",
        }

        fixture_id = api_fixture.get("id")

        result = {
            **schedule_match,
            "fixture_id": fixture_id,
            "live_verified": live_verified,
            "live_data_source": "api-football",
            "status": {
                "short": status_short,
                "long": status.get("long"),
                "elapsed": status.get("elapsed"),
                "extra": status.get("extra"),
            },
            "home": {
                **schedule_match.get(
                    "home",
                    {},
                ),
                "id_api": teams.get(
                    "home",
                    {},
                ).get("id"),
                "goals": goals.get("home"),
                "winner": teams.get(
                    "home",
                    {},
                ).get("winner"),
            },
            "away": {
                **schedule_match.get(
                    "away",
                    {},
                ),
                "id_api": teams.get(
                    "away",
                    {},
                ).get("id"),
                "goals": goals.get("away"),
                "winner": teams.get(
                    "away",
                    {},
                ).get("winner"),
            },
        }

        # ====================================================
        # SI FINALIZÓ, NO SEGUIR CONSIDERÁNDOLO LIVE
        # ====================================================

        if status_short in {
            "FT",
            "AET",
            "PEN",
        }:

            result["live_candidate"] = False

            if fixture_id:

                _FINISHED_MATCHES.add(fixture_id)

        return result

    # ========================================================
    # LISTADO + LIVE OVERLAY
    # ========================================================

    def get_matches(
        self,
        scope="today",
    ):

        # ====================================================
        # 1. CARTELERA GRATIS
        # ====================================================

        matches = self.sportsdb.get_matches(
            scope="today",
        )

        # ====================================================
        # 2. DETERMINAR SI NECESITAMOS API-FOOTBALL
        # ====================================================

        candidates = [
            match
            for match in matches
            if (
                match.get("live_candidate")
                and match.get(
                    "status",
                    {},
                ).get("short")
                not in {
                    "FT",
                    "AET",
                    "PEN",
                    "CANC",
                    "PST",
                }
            )
        ]

        overlay_active = len(candidates) > 0

        overlay_error = None

        stale = False

        api_called = False

        # ====================================================
        # 3. LIVE OVERLAY
        #
        # IMPORTANTE:
        #
        # UNA SOLA CONSULTA POR FECHA.
        #
        # Aunque haya 5 partidos simultáneos.
        # ====================================================

        if overlay_active and self.has_api_football():

            # =================================================
            # AGRUPAR FECHAS
            # =================================================

            dates = sorted(
                {
                    match.get("date_local")
                    for match in candidates
                    if match.get("date_local")
                }
            )

            api_fixtures_by_date = {}

            for date_value in dates:

                try:

                    response = self._api_get(
                        "/fixtures",
                        params={
                            "date": date_value,
                            "league": LIGA_MX_ID,
                            "timezone": TIMEZONE,
                        },
                        cache_seconds=OVERLAY_CACHE_SECONDS,
                        allow_stale=True,
                    )

                    api_fixtures_by_date[date_value] = response["data"]

                    stale = stale or response.get(
                        "stale",
                        False,
                    )

                    api_called = api_called or not response.get(
                        "cached",
                        False,
                    )

                except Exception as error:

                    overlay_error = str(error)

            # =================================================
            # 4. OVERLAY SOBRE LAS MISMAS TARJETAS
            # =================================================

            updated_matches = []

            for match in matches:

                date_value = match.get("date_local")

                api_fixtures = api_fixtures_by_date.get(
                    date_value,
                    [],
                )

                fixture = self._find_matching_fixture(
                    match,
                    api_fixtures,
                )

                if fixture:

                    updated_matches.append(
                        self._apply_overlay(
                            match,
                            fixture,
                        )
                    )

                else:

                    updated_matches.append(match)

            matches = updated_matches

        # ====================================================
        # 5. FILTRO VENTANA LIVE
        # ====================================================

        if scope == "live":

            matches = [
                match
                for match in matches
                if (match.get("live_candidate") or match.get("live_verified"))
            ]

        # ====================================================
        # 6. RESPONSE
        # ====================================================

        return {
            "matches": matches,
            "count": len(matches),
            "schedule_provider": "thesportsdb",
            "live_provider": ("api-football" if self.has_api_football() else None),
            "overlay_active": overlay_active,
            "overlay_available": self.has_api_football(),
            "overlay_stale": stale,
            "overlay_error": overlay_error,
            "api_called": api_called,
            "quota": get_quota_status(),
            # =================================================
            # React puede preguntar seguido.
            #
            # El cache evita consumir proveedor.
            # =================================================
            "ui_refresh_seconds": (20 if overlay_active else 60),
            "provider_refresh_seconds": (
                OVERLAY_CACHE_SECONDS if overlay_active else 300
            ),
        }

    # ========================================================
    # RESOLVER PARTIDO
    # ========================================================

    def resolve_match(
        self,
        date,
        home,
        away,
    ):

        response = self._api_get(
            "/fixtures",
            params={
                "date": date,
                "league": LIGA_MX_ID,
                "timezone": TIMEZONE,
            },
            cache_seconds=RESOLVE_CACHE_SECONDS,
            allow_stale=True,
        )

        schedule_match = {
            "home": {
                "name": home,
            },
            "away": {
                "name": away,
            },
        }

        fixture = self._find_matching_fixture(
            schedule_match,
            response["data"],
        )

        if not fixture:

            raise RuntimeError(
                "No fue posible relacionar " "el partido con API-Football."
            )

        return {
            "fixture_id": fixture["fixture"]["id"],
            "home": fixture["teams"]["home"]["name"],
            "away": fixture["teams"]["away"]["name"],
        }

    # ========================================================
    # DETALLE PARTIDO
    # ========================================================

    def get_fixture_detail(
        self,
        fixture_id,
    ):

        fixture_id = int(fixture_id)

        response = self._api_get(
            "/fixtures",
            params={
                "id": fixture_id,
            },
            cache_seconds=DETAIL_CACHE_SECONDS,
            allow_stale=True,
        )

        data = response["data"]

        if not data:

            raise RuntimeError("No se encontró el partido " "en API-Football.")

        fixture = data[0]

        detail = self._normalize_fixture_detail(fixture)

        detail["stale"] = response.get(
            "stale",
            False,
        )

        detail["cached"] = response.get(
            "cached",
            False,
        )

        detail["data_source"] = "api-football"

        return detail

    # ========================================================
    # NORMALIZAR FIXTURE
    # ========================================================

    def _normalize_fixture(
        self,
        item,
    ):

        fixture = item.get(
            "fixture",
            {},
        )

        league = item.get(
            "league",
            {},
        )

        teams = item.get(
            "teams",
            {},
        )

        goals = item.get(
            "goals",
            {},
        )

        status = fixture.get(
            "status",
            {},
        )

        return {
            "id": fixture.get("id"),
            "fixture_id": fixture.get("id"),
            "date": fixture.get("date"),
            "referee": fixture.get("referee"),
            "venue": fixture.get(
                "venue",
                {},
            ),
            "league": {
                "id": league.get("id"),
                "name": league.get("name"),
                "round": league.get("round"),
                "season": league.get("season"),
            },
            "status": {
                "short": status.get("short"),
                "long": status.get("long"),
                "elapsed": status.get("elapsed"),
                "extra": status.get("extra"),
            },
            "home": {
                "id": teams.get(
                    "home",
                    {},
                ).get("id"),
                "name": teams.get(
                    "home",
                    {},
                ).get("name"),
                "logo": teams.get(
                    "home",
                    {},
                ).get("logo"),
                "goals": goals.get("home"),
            },
            "away": {
                "id": teams.get(
                    "away",
                    {},
                ).get("id"),
                "name": teams.get(
                    "away",
                    {},
                ).get("name"),
                "logo": teams.get(
                    "away",
                    {},
                ).get("logo"),
                "goals": goals.get("away"),
            },
        }

    # ========================================================
    # NORMALIZAR DETALLE
    # ========================================================

    def _normalize_fixture_detail(
        self,
        item,
    ):

        base = self._normalize_fixture(item)

        base["events"] = self._normalize_events(item.get("events") or [])

        base["statistics"] = self._normalize_statistics(
            item.get("statistics") or [],
            base,
        )

        base["lineups"] = item.get("lineups") or []

        base["score"] = item.get("score") or {}

        return base

    # ========================================================
    # EVENTS
    # ========================================================

    def _normalize_events(
        self,
        events,
    ):

        output = []

        for event in events:

            output.append(
                {
                    "elapsed": event.get(
                        "time",
                        {},
                    ).get("elapsed"),
                    "extra": event.get(
                        "time",
                        {},
                    ).get("extra"),
                    "team_id": event.get(
                        "team",
                        {},
                    ).get("id"),
                    "team": event.get(
                        "team",
                        {},
                    ).get("name"),
                    "player": event.get(
                        "player",
                        {},
                    ).get("name"),
                    "assist": event.get(
                        "assist",
                        {},
                    ).get("name"),
                    "type": event.get("type"),
                    "detail": event.get("detail"),
                    "comments": event.get("comments"),
                }
            )

        output.sort(
            key=lambda event: (
                event.get("elapsed") or 0,
                event.get("extra") or 0,
            )
        )

        return output

    # ========================================================
    # STATS
    # ========================================================

    def _normalize_statistics(
        self,
        statistics,
        fixture,
    ):

        result = {
            "home": {
                "team": fixture["home"]["name"],
                "values": {},
            },
            "away": {
                "team": fixture["away"]["name"],
                "values": {},
            },
        }

        home_id = fixture["home"]["id"]

        for team_stats in statistics:

            values = {}

            for stat in team_stats.get("statistics") or []:

                values[stat.get("type")] = _safe_number(stat.get("value"))

            team_id = team_stats.get(
                "team",
                {},
            ).get("id")

            side = "home" if team_id == home_id else "away"

            result[side]["values"] = values

        return result

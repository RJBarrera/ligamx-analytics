import os
import threading
import time

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from dotenv import load_dotenv

from team_identity import normalize_team_name

# ============================================================
# RUTAS
# ============================================================

SERVER_DIR = Path(__file__).resolve().parent

PROJECT_DIR = SERVER_DIR.parent


load_dotenv(PROJECT_DIR / ".env")


# ============================================================
# CONFIGURACIÓN
# ============================================================

SPORTSDB_API_KEY = os.getenv(
    "SPORTSDB_API_KEY",
    "123",
)

SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"

SPORTSDB_LIGA_MX_ID = 4350


TIMEZONE_NAME = "America/Mazatlan"

LOCAL_TIMEZONE = ZoneInfo(TIMEZONE_NAME)


SCHEDULE_CACHE_SECONDS = 300


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
# HELPERS
# ============================================================


def _cache_key(
    endpoint,
    params,
):

    return (
        endpoint,
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


def _to_int(
    value,
):

    if value is None or value == "":

        return None

    try:

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# FECHA/HORA
# ============================================================


def _parse_datetime(
    event,
):
    """
    Convierte siempre el partido a America/Mazatlan.

    Prioridad:
    1. strTimestamp
    2. dateEventLocal + strTimeLocal
    3. dateEvent + strTime
    """

    # ========================================================
    # TIMESTAMP
    # ========================================================

    timestamp = event.get("strTimestamp")

    if timestamp:

        try:

            timestamp_text = (
                str(timestamp)
                .strip()
                .replace(
                    "Z",
                    "+00:00",
                )
            )

            dt = datetime.fromisoformat(timestamp_text)

            if dt.tzinfo is None:

                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(LOCAL_TIMEZONE)

        except (
            TypeError,
            ValueError,
        ):

            pass

    # ========================================================
    # FECHA LOCAL
    # ========================================================

    local_date = event.get("dateEventLocal")

    local_time = event.get("strTimeLocal")

    if local_date and local_time:

        try:

            clean_time = str(local_time).strip()

            if len(clean_time) == 5:

                clean_time = f"{clean_time}:00"

            dt = datetime.fromisoformat(f"{local_date}T{clean_time}")

            return dt.replace(tzinfo=LOCAL_TIMEZONE)

        except (
            TypeError,
            ValueError,
        ):

            pass

    # ========================================================
    # FECHA GENERAL / UTC
    # ========================================================

    date_value = event.get("dateEvent")

    time_value = event.get("strTime")

    if date_value and time_value:

        try:

            clean_time = str(time_value).strip()

            if len(clean_time) == 5:

                clean_time = f"{clean_time}:00"

            dt = datetime.fromisoformat(f"{date_value}T{clean_time}")

            dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(LOCAL_TIMEZONE)

        except (
            TypeError,
            ValueError,
        ):

            pass

    return None


# ============================================================
# STATUS
# ============================================================


def _normalize_status(
    event,
):

    raw = str(event.get("strStatus") or "").strip()

    normalized = raw.casefold()

    if normalized in {
        "match finished",
        "finished",
        "ft",
    }:

        return {
            "short": "FT",
            "long": "Finalizado",
            "elapsed": None,
        }

    if normalized in {
        "half time",
        "ht",
    }:

        return {
            "short": "HT",
            "long": "Medio tiempo",
            "elapsed": 45,
        }

    if "progress" in normalized or normalized in {
        "live",
        "1h",
        "2h",
    }:

        return {
            "short": "LIVE",
            "long": "En juego",
            "elapsed": None,
        }

    if normalized in {
        "postponed",
        "pst",
    }:

        return {
            "short": "PST",
            "long": "Pospuesto",
            "elapsed": None,
        }

    if normalized in {
        "cancelled",
        "canceled",
        "canc",
    }:

        return {
            "short": "CANC",
            "long": "Cancelado",
            "elapsed": None,
        }

    return {
        "short": "NS",
        "long": "Programado",
        "elapsed": None,
    }


# ============================================================
# SERVICIO
# ============================================================


class SportsDBService:

    def __init__(
        self,
    ):

        self.api_key = SPORTSDB_API_KEY

        self.base_url = SPORTSDB_BASE_URL

    # ========================================================
    # REQUEST
    # ========================================================

    def _get(
        self,
        endpoint,
        params=None,
        cache_seconds=SCHEDULE_CACHE_SECONDS,
    ):

        params = params or {}

        key = _cache_key(
            endpoint,
            params,
        )

        now = time.time()

        with _CACHE_LOCK:

            cached = _CACHE.get(key)

            if cached:

                age = now - cached["timestamp"]

                if age < cache_seconds:

                    return cached["data"]

        url = f"{self.base_url}/" f"{self.api_key}/" f"{endpoint}"

        try:

            response = _SESSION.get(
                url,
                params=params,
                timeout=15,
            )

            if not response.ok:

                raise RuntimeError(
                    "TheSportsDB respondió " f"HTTP {response.status_code}."
                )

            payload = response.json()

            with _CACHE_LOCK:

                _CACHE[key] = {
                    "timestamp": now,
                    "data": payload,
                }

            return payload

        except Exception:

            # =================================================
            # STALE CACHE
            # =================================================

            if cached:

                return cached["data"]

            raise

    # ========================================================
    # EVENTOS DE FECHA
    # ========================================================

    def _events_for_date(
        self,
        date_value,
    ):

        payload = self._get(
            "eventsday.php",
            params={
                "d": date_value,
                "l": SPORTSDB_LIGA_MX_ID,
            },
        )

        return payload.get("events") or []

    # ========================================================
    # NORMALIZAR EVENTO
    # ========================================================

    def _normalize_event(
        self,
        event,
    ):

        kickoff = _parse_datetime(event)

        status = _normalize_status(event)

        now = datetime.now(LOCAL_TIMEZONE)

        # ====================================================
        # VENTANA LIVE
        #
        # 20 min antes
        # hasta 3h15 después
        # ====================================================

        live_candidate = False

        if kickoff:

            live_window_start = kickoff - timedelta(minutes=20)

            live_window_end = kickoff + timedelta(
                hours=3,
                minutes=15,
            )

            live_candidate = live_window_start <= now <= live_window_end

        if status["short"] in {
            "LIVE",
            "HT",
        }:

            live_candidate = True

        if status["short"] == "FT":

            live_candidate = False

        # ====================================================
        # MINUTOS PARA INICIO
        # ====================================================

        minutes_to_start = None

        if kickoff:

            minutes_to_start = int((kickoff - now).total_seconds() / 60)

        return {
            "id": ("tsdb-" f"{event.get('idEvent')}"),
            "sportsdb_event_id": event.get("idEvent"),
            "source": "thesportsdb",
            "fixture_id": None,
            "date": (kickoff.isoformat() if kickoff else event.get("strTimestamp")),
            "date_local": (kickoff.date().isoformat() if kickoff else None),
            "time_local": (kickoff.strftime("%H:%M") if kickoff else None),
            "kickoff_timestamp": (int(kickoff.timestamp()) if kickoff else None),
            "minutes_to_start": minutes_to_start,
            "live_candidate": live_candidate,
            "live_verified": False,
            "live_data_source": None,
            "status": status,
            "league": {
                "id": SPORTSDB_LIGA_MX_ID,
                "name": event.get("strLeague") or "Liga MX",
                "round": (
                    f"Jornada " f"{event.get('intRound')}"
                    if event.get("intRound")
                    else None
                ),
                "season": event.get("strSeason"),
                "logo": event.get("strLeagueBadge"),
            },
            "home": {
                "id": event.get("idHomeTeam"),
                "name": normalize_team_name(event.get("strHomeTeam")),
                "logo": event.get("strHomeTeamBadge"),
                "goals": _to_int(event.get("intHomeScore")),
            },
            "away": {
                "id": event.get("idAwayTeam"),
                "name": normalize_team_name(event.get("strAwayTeam")),
                "logo": event.get("strAwayTeamBadge"),
                "goals": _to_int(event.get("intAwayScore")),
            },
            "venue": {
                "name": event.get("strVenue"),
                "city": None,
            },
        }

    # ========================================================
    # PARTIDOS DEL DÍA
    # ========================================================

    def get_matches(
        self,
        scope="today",
    ):

        now = datetime.now(LOCAL_TIMEZONE)

        local_today = now.date()

        # ====================================================
        # THE SPORTS DB USA FECHAS UTC
        #
        # Consultamos ayer/hoy/mañana
        # y después filtramos LOCALMENTE.
        # ====================================================

        source_dates = [
            (local_today - timedelta(days=1)).isoformat(),
            local_today.isoformat(),
            (local_today + timedelta(days=1)).isoformat(),
        ]

        raw_events = []

        for source_date in source_dates:

            try:

                raw_events.extend(self._events_for_date(source_date))

            except Exception as error:

                print(
                    "SPORTSDB ERROR:",
                    source_date,
                    error,
                )

        # ====================================================
        # NORMALIZAR
        # ====================================================

        normalized = [self._normalize_event(event) for event in raw_events]

        # ====================================================
        # DEDUPLICAR
        # ====================================================

        unique = {}

        for match in normalized:

            event_id = match.get("sportsdb_event_id")

            if not event_id:
                continue

            unique[str(event_id)] = match

        matches = list(unique.values())

        # ====================================================
        # FECHA LOCAL
        # ====================================================

        local_today_string = local_today.isoformat()

        matches = [
            match
            for match in matches
            if (match.get("date_local") == local_today_string)
        ]

        # ====================================================
        # VENTANA LIVE
        # ====================================================

        if scope == "live":

            matches = [
                match
                for match in matches
                if (
                    match.get("live_candidate")
                    or match.get(
                        "status",
                        {},
                    ).get("short")
                    in {
                        "LIVE",
                        "HT",
                    }
                )
            ]

        # ====================================================
        # ORDER
        # ====================================================

        matches.sort(key=lambda item: (item.get("kickoff_timestamp") or 0))

        return matches

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

# Diccionario de traducción temporal en caliente
EQUIVALENCIAS = {"Atlante": "Mazatlán"}

# RUTAS
SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent

load_dotenv(PROJECT_DIR / ".env")

# CONFIGURACION
SPORTSDB_API_KEY = os.getenv(
    "SPORTSDB_API_KEY",
    "123",
)

SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
SPORTSDB_LIGA_MX_ID = 4350

TIMEZONE_NAME = "America/Mazatlan"
LOCAL_TIMEZONE = ZoneInfo(TIMEZONE_NAME)

SCHEDULE_CACHE_SECONDS = 300

# HTTP
_SESSION = requests.Session()

# CACHE
_CACHE = {}
_CACHE_LOCK = threading.Lock()


# HELPERS
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


# FECHA/HORA
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

    # TIMESTAMP
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

    # FECHA LOCAL
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

    # FECHA GENERAL / UTC
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


# STATUS
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


# SERVICIO
class SportsDBService:

    def __init__(
        self,
    ):

        self.api_key = SPORTSDB_API_KEY
        self.base_url = SPORTSDB_BASE_URL

    # REQUEST
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

            # STALE CACHE
            if cached:
                return cached["data"]
            raise

    # EVENTOS DE FECHA
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

    # PROXIMO EVENTO DE LA LIGA
    def _next_league_events(
        self,
    ):
        payload = self._get(
            "eventsnextleague.php",
            params={
                "id": SPORTSDB_LIGA_MX_ID,
            },
        )

        return payload.get("events") or []

    def _previous_league_events(
        self,
    ):
        payload = self._get(
            "eventspastleague.php",
            params={
                "id": SPORTSDB_LIGA_MX_ID,
            },
        )

        return payload.get("events") or []

    def _get_current_round_context(
        self,
    ):
        next_events = self._next_league_events()
        previous_events = self._previous_league_events()

        next_event = next_events[0] if next_events else None
        previous_event = previous_events[0] if previous_events else None

        next_season = (
            str(next_event.get("strSeason") or "").strip() if next_event else ""
        )

        previous_season = (
            str(previous_event.get("strSeason") or "").strip() if previous_event else ""
        )

        previous_round = (
            _to_int(previous_event.get("intRound")) if previous_event else None
        )

        if (
            previous_round is not None
            and previous_season
            and previous_season == next_season
        ):
            return previous_round, previous_season

        if previous_round is not None and not next_event:
            return previous_round, previous_season

        if next_event:
            return None, next_season

        return None, None

    # PROXIMOS PARTIDOS
    def _get_next_round_matches(
        self,
    ):
        now = datetime.now(LOCAL_TIMEZONE)

        current_round, current_season = self._get_current_round_context()

        next_events = self._next_league_events()

        if not next_events:
            return []

        anchor_event = next_events[0]

        anchor_round = _to_int(anchor_event.get("intRound"))

        anchor_season = str(anchor_event.get("strSeason") or "").strip()

        anchor_kickoff = _parse_datetime(anchor_event)

        target_round = None
        target_season = None
        target_kickoff = None

        if current_round is None:

            target_round = anchor_round
            target_season = anchor_season
            target_kickoff = anchor_kickoff

        elif (
            anchor_round is not None
            and anchor_round > current_round
            and (not current_season or anchor_season == current_season)
        ):

            target_round = anchor_round
            target_season = anchor_season
            target_kickoff = anchor_kickoff

        else:

            for offset in range(0, 61):

                search_date = now.date() + timedelta(days=offset)

                try:

                    events = self._events_for_date(search_date.isoformat())

                except Exception as error:

                    print(
                        "SPORTSDB NEXT ROUND ERROR:",
                        search_date,
                        error,
                    )

                    continue

                candidates = []

                for event in events:

                    event_round = _to_int(event.get("intRound"))

                    event_season = str(event.get("strSeason") or "").strip()

                    kickoff = _parse_datetime(event)

                    if event_round is None:
                        continue

                    if event_round <= current_round:
                        continue

                    if current_season and event_season != current_season:
                        continue

                    if not kickoff:
                        continue

                    if kickoff <= now:
                        continue

                    candidates.append(
                        (
                            event_round,
                            kickoff,
                            event,
                        )
                    )

                if candidates:

                    candidates.sort(
                        key=lambda item: (
                            item[0],
                            item[1],
                        )
                    )

                    (
                        target_round,
                        target_kickoff,
                        target_event,
                    ) = candidates[0]

                    target_season = str(target_event.get("strSeason") or "").strip()

                    break

        if target_round is None or target_kickoff is None:
            return []

        anchor_date = target_kickoff.date()

        source_dates = [
            (anchor_date + timedelta(days=offset)).isoformat()
            for offset in range(-1, 10)
        ]

        unique = {}

        for source_date in source_dates:

            try:

                events = self._events_for_date(source_date)

            except Exception as error:

                print(
                    "SPORTSDB NEXT ROUND ERROR:",
                    source_date,
                    error,
                )

                continue

            for event in events:

                event_round = _to_int(event.get("intRound"))

                event_season = str(event.get("strSeason") or "").strip()

                if event_round != target_round:
                    continue

                if target_season and event_season != target_season:
                    continue

                match = self._normalize_event(event)

                event_id = match.get("sportsdb_event_id")

                if not event_id:
                    continue

                unique[str(event_id)] = match

        matches = list(unique.values())

        matches.sort(key=lambda item: (item.get("kickoff_timestamp") or 0))

        return matches

    # NORMALIZAR EVENTO
    def _normalize_event(
        self,
        event,
    ):

        kickoff = _parse_datetime(event)
        status = _normalize_status(event)
        now = datetime.now(LOCAL_TIMEZONE)

        # VENTANA EN VIVO
        # 20 min antes
        # hasta 3h15 después
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

        # MINUTOS PARA INICIO
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
                "name": EQUIVALENCIAS.get(
                    event.get("strHomeTeam"), event.get("strHomeTeam")
                ),
                "logo": event.get("strHomeTeamBadge"),
                "goals": _to_int(event.get("intHomeScore")),
            },
            "away": {
                "id": event.get("idAwayTeam"),
                "name": EQUIVALENCIAS.get(
                    event.get("strAwayTeam"), event.get("strAwayTeam")
                ),
                "logo": event.get("strAwayTeamBadge"),
                "goals": _to_int(event.get("intAwayScore")),
            },
            "venue": {
                "name": event.get("strVenue"),
                "city": None,
            },
        }

    def _get_upcoming_matches(
        self,
    ):
        now = datetime.now(LOCAL_TIMEZONE)

        current_round, current_season = self._get_current_round_context()

        if current_round is None:
            return []

        unique = {}

        for offset in range(0, 61):

            search_date = now.date() + timedelta(days=offset)

            try:

                events = self._events_for_date(search_date.isoformat())

            except Exception as error:

                print(
                    "SPORTSDB UPCOMING ERROR:",
                    search_date,
                    error,
                )

                continue

            for event in events:

                event_round = _to_int(event.get("intRound"))

                event_season = str(event.get("strSeason") or "").strip()

                if event_round != current_round:
                    continue

                if current_season and event_season != current_season:
                    continue

                match = self._normalize_event(event)

                kickoff_timestamp = match.get("kickoff_timestamp")

                if kickoff_timestamp is None or kickoff_timestamp <= int(
                    now.timestamp()
                ):
                    continue

                status = match.get(
                    "status",
                    {},
                ).get("short")

                if status in {
                    "FT",
                    "AET",
                    "PEN",
                    "CANC",
                }:
                    continue

                event_id = match.get("sportsdb_event_id")

                if not event_id:
                    continue

                unique[str(event_id)] = match

        matches = list(unique.values())

        matches.sort(key=lambda item: (item.get("kickoff_timestamp") or 0))

        return matches

    # PARTIDOS DEL DIA
    def get_matches(
        self,
        scope="today",
    ):

        if scope == "next":
            return self._get_next_round_matches()

        if scope == "upcoming":
            return self._get_upcoming_matches()

        now = datetime.now(LOCAL_TIMEZONE)
        local_today = now.date()

        # THE SPORTS DB USA FECHAS UTC
        # Consultamos ayer/hoy/mañana
        # y después filtramos LOCALMENTE.

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

        # NORMALIZAR
        normalized = [self._normalize_event(event) for event in raw_events]

        # DEDUPLICAR
        unique = {}

        for match in normalized:
            event_id = match.get("sportsdb_event_id")

            if not event_id:
                continue

            unique[str(event_id)] = match

        matches = list(unique.values())

        # FECHA LOCAL
        local_today_string = local_today.isoformat()

        matches = [
            match
            for match in matches
            if (match.get("date_local") == local_today_string)
        ]

        # VENTANA LIVE
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

        # ORDER
        matches.sort(key=lambda item: (item.get("kickoff_timestamp") or 0))

        return matches

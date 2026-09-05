import threading

from datetime import (
    datetime,
)

from zoneinfo import ZoneInfo

# ============================================================
# CONFIG
# ============================================================

TIMEZONE = ZoneInfo("America/Mazatlan")


FINAL_STATUSES = {
    "FT",
    "AET",
    "PEN",
}


# ============================================================
# SERVICE
# ============================================================


class DatasetSyncService:

    def __init__(
        self,
        live_service,
        history_service,
    ):

        self.live_service = live_service

        self.history_service = history_service

        self._lock = threading.Lock()

    # ========================================================
    # ¿ESTAMOS CERCA DEL FINAL DE ALGÚN PARTIDO?
    # ========================================================

    def _should_sync_today(
        self,
    ):

        try:

            matches = self.live_service.sportsdb.get_matches(scope="today")

        except Exception:

            return False

        if not matches:

            return False

        now_timestamp = datetime.now(TIMEZONE).timestamp()

        for match in matches:

            kickoff = match.get("kickoff_timestamp")

            if not kickoff:

                continue

            # =================================================
            # DATA SYNC
            #
            # No necesitamos consumir API todo el partido.
            #
            # Empezamos aproximadamente 95 minutos
            # después del kickoff.
            #
            # Y dejamos margen suficiente por tiempo añadido,
            # suspensiones, etc.
            # =================================================

            sync_start = kickoff + (95 * 60)

            sync_end = kickoff + (4 * 60 * 60)

            if sync_start <= now_timestamp <= sync_end:

                return True

        return False

    # ========================================================
    # SINCRONIZAR HOY
    # ========================================================

    def sync_today(
        self,
        force=False,
    ):

        if not self._lock.acquire(blocking=False):

            return {
                "status": "busy",
            }

        try:

            if not force and not self._should_sync_today():

                return {
                    "status": "waiting",
                    "message": "No hay partidos en ventana de finalización.",
                }

            date_value = datetime.now(TIMEZONE).date().isoformat()

            # =================================================
            # UNA CONSULTA DE API-FOOTBALL
            #
            # Obtiene TODOS los fixtures de Liga MX que
            # API-Football devuelve para esta fecha.
            # =================================================

            fixtures = self.live_service.get_liga_mx_fixtures_by_date(date_value)

            saved = []
            duplicates = []
            pending = []
            unfinished = []

            for fixture in fixtures:

                api_fixture = fixture.get("fixture", {})

                fixture_id = api_fixture.get("id")

                status = api_fixture.get("status", {}).get("short")

                if status not in FINAL_STATUSES:

                    unfinished.append(fixture_id)

                    continue

                if fixture_id and self.history_service.has_fixture(fixture_id):

                    duplicates.append(fixture_id)

                    continue

                # =================================================
                # AHORA SÍ OBTENEMOS DETALLE COMPLETO
                #
                # Solo ocurre una vez cuando el partido termina.
                # =================================================

                detail = self.live_service.get_fixture_detail(fixture_id)

                result = self.history_service.save_finished_match(detail)

                action = result.get("action")

                if action == "saved":

                    saved.append(result)

                elif action == "duplicate":

                    duplicates.append(fixture_id)

                elif action == "pending":

                    pending.append(result)

            return {
                "status": "completed",
                "date": date_value,
                "fixtures_found": len(fixtures),
                "saved": saved,
                "saved_count": len(saved),
                "duplicates": duplicates,
                "pending": pending,
                "unfinished": unfinished,
            }

        finally:

            self._lock.release()

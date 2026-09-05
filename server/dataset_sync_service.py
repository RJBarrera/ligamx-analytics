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

            # ====================================================
            # 1. REINTENTAR FIXTURES PENDIENTES
            # ====================================================

            pending_retry = []

            pending_fixture_ids = self.history_service.get_pending_fixture_ids()

            for fixture_id in pending_fixture_ids:

                try:

                    # =============================================
                    # SI YA EXISTE EN EL HISTÓRICO,
                    # NO VOLVER A INSERTARLO.
                    # =============================================

                    if self.history_service.has_fixture(fixture_id):

                        pending_retry.append(
                            {
                                "fixture_id": fixture_id,
                                "result": {
                                    "action": "duplicate",
                                },
                            }
                        )

                        continue

                    # =============================================
                    # VOLVER A CONSULTAR EL DETALLE COMPLETO
                    # =============================================

                    detail = self.live_service.get_fixture_detail(fixture_id)

                    # =============================================
                    # VOLVER A INTENTAR GUARDAR
                    # =============================================

                    result = self.history_service.save_finished_match(detail)

                    pending_retry.append(
                        {
                            "fixture_id": fixture_id,
                            "result": result,
                        }
                    )

                except Exception as error:

                    pending_retry.append(
                        {
                            "fixture_id": fixture_id,
                            "result": {
                                "action": "error",
                                "error": str(error),
                            },
                        }
                    )

            # ====================================================
            # 2. VALIDAR SI HAY PARTIDOS EN VENTANA DE FINALIZACIÓN
            #
            # IMPORTANTE:
            #
            # aunque no haya partidos de hoy en ventana,
            # los pendientes anteriores YA SE REINTENTARON.
            # ====================================================

            if not force and not self._should_sync_today():

                return {
                    "status": "waiting",
                    "message": "No hay partidos en ventana de finalización.",
                    "pending_retry": pending_retry,
                }

            # ====================================================
            # 3. FECHA ACTUAL
            # ====================================================

            date_value = datetime.now(TIMEZONE).date().isoformat()

            # ====================================================
            # 4. UNA CONSULTA DE API-FOOTBALL
            #
            # Obtiene todos los fixtures disponibles de Liga MX
            # para la fecha actual.
            # ====================================================

            fixtures = self.live_service.get_liga_mx_fixtures_by_date(date_value)

            # ====================================================
            # 5. CONTENEDORES DE RESULTADO
            # ====================================================

            saved = []

            duplicates = []

            pending = []

            unfinished = []

            # ====================================================
            # 6. PROCESAR FIXTURES DE HOY
            # ====================================================

            for fixture in fixtures:

                api_fixture = fixture.get(
                    "fixture",
                    {},
                )

                fixture_id = api_fixture.get("id")

                status = api_fixture.get(
                    "status",
                    {},
                ).get("short")

                # =============================================
                # TODAVÍA NO TERMINA
                # =============================================

                if status not in FINAL_STATUSES:

                    unfinished.append(fixture_id)

                    continue

                # =============================================
                # YA EXISTE EN EL CSV
                # =============================================

                if fixture_id and self.history_service.has_fixture(fixture_id):

                    duplicates.append(fixture_id)

                    continue

                # =============================================
                # OBTENER DETALLE COMPLETO
                #
                # Solo cuando ya terminó.
                # =============================================

                detail = self.live_service.get_fixture_detail(fixture_id)

                # =============================================
                # INTENTAR GUARDAR
                # =============================================

                result = self.history_service.save_finished_match(detail)

                action = result.get("action")

                if action == "saved":

                    saved.append(result)

                elif action == "duplicate":

                    duplicates.append(fixture_id)

                elif action == "pending":

                    pending.append(result)

            # ====================================================
            # 7. RESPONSE
            # ====================================================

            return {
                "status": "completed",
                "date": date_value,
                "pending_retry": pending_retry,
                "fixtures_found": len(fixtures),
                "saved": saved,
                "saved_count": len(saved),
                "duplicates": duplicates,
                "pending": pending,
                "unfinished": unfinished,
            }

        finally:

            self._lock.release()

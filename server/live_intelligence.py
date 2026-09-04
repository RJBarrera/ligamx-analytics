import math
import threading
import unicodedata
from collections import defaultdict

from scipy.stats import poisson

# ============================================================
# HISTÓRICO TEMPORAL DE PARTIDOS LIVE
# ============================================================

_LIVE_HISTORY = defaultdict(list)

_HISTORY_LOCK = threading.Lock()


# ============================================================
# UTILIDADES
# ============================================================


def _number(
    value,
    default=0.0,
):

    if value is None:
        return default

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(value)

    text = str(value).strip()

    if text.endswith("%"):
        text = text[:-1]

    try:

        return float(text)

    except ValueError:

        return default


def _normalize_name(
    value,
):

    value = unicodedata.normalize(
        "NFD",
        str(
            value or "",
        ),
    )

    value = "".join(char for char in value if (unicodedata.category(char) != "Mn"))

    value = (
        value.lower()
        .replace(
            ".",
            " ",
        )
        .replace(
            "-",
            " ",
        )
    )

    return " ".join(value.split())


# ============================================================
# ESTADÍSTICA
# ============================================================


def _stat(
    detail,
    side,
    name,
):

    return _number(
        detail.get(
            "statistics",
            {},
        )
        .get(
            side,
            {},
        )
        .get(
            "values",
            {},
        )
        .get(name)
    )


# ============================================================
# SNAPSHOT
# ============================================================


def _create_snapshot(
    detail,
):

    elapsed = detail.get(
        "status",
        {},
    ).get("elapsed")

    if elapsed is None:

        return None

    return {
        "minute": int(elapsed),
        "home_goals": _number(
            detail.get(
                "home",
                {},
            ).get("goals")
        ),
        "away_goals": _number(
            detail.get(
                "away",
                {},
            ).get("goals")
        ),
        "home_shots": _stat(
            detail,
            "home",
            "Total Shots",
        ),
        "away_shots": _stat(
            detail,
            "away",
            "Total Shots",
        ),
        "home_sot": _stat(
            detail,
            "home",
            "Shots on Goal",
        ),
        "away_sot": _stat(
            detail,
            "away",
            "Shots on Goal",
        ),
        "home_corners": _stat(
            detail,
            "home",
            "Corner Kicks",
        ),
        "away_corners": _stat(
            detail,
            "away",
            "Corner Kicks",
        ),
        "home_possession": _stat(
            detail,
            "home",
            "Ball Possession",
        ),
        "away_possession": _stat(
            detail,
            "away",
            "Ball Possession",
        ),
    }


# ============================================================
# GUARDAR SNAPSHOT
# ============================================================


def _record_snapshot(
    detail,
):

    fixture_id = detail.get("id")

    snapshot = _create_snapshot(detail)

    if not fixture_id or not snapshot:

        return []

    with _HISTORY_LOCK:

        history = _LIVE_HISTORY[fixture_id]

        if history:

            last = history[-1]

            # Evitar duplicados exactos.
            if last == snapshot:

                return list(history)

        history.append(snapshot)

        # Solo necesitamos una ventana razonable.
        if len(history) > 60:

            del history[:-60]

        return list(history)


# ============================================================
# SCORE DE PRESIÓN
# ============================================================


def _pressure_score(
    stats,
    side,
):

    return (
        (
            stats.get(
                f"{side}_sot",
                0,
            )
            * 4.0
        )
        + (
            stats.get(
                f"{side}_shots",
                0,
            )
            * 1.35
        )
        + (
            stats.get(
                f"{side}_corners",
                0,
            )
            * 1.75
        )
        + (
            stats.get(
                f"{side}_goals",
                0,
            )
            * 5.0
        )
        + (
            stats.get(
                f"{side}_possession",
                0,
            )
            * 0.04
        )
    )


# ============================================================
# DELTA ENTRE SNAPSHOTS
# ============================================================


def _snapshot_delta(
    current,
    previous,
):

    delta = {
        "minute": current["minute"],
        "window": max(
            1,
            current["minute"] - previous["minute"],
        ),
    }

    for key in (
        "home_goals",
        "away_goals",
        "home_shots",
        "away_shots",
        "home_sot",
        "away_sot",
        "home_corners",
        "away_corners",
    ):

        delta[key] = max(
            0,
            current.get(
                key,
                0,
            )
            - previous.get(
                key,
                0,
            ),
        )

    # Para posesión utilizamos el dato actual.
    delta["home_possession"] = current.get(
        "home_possession",
        0,
    )

    delta["away_possession"] = current.get(
        "away_possession",
        0,
    )

    return delta


# ============================================================
# MOMENTUM
# ============================================================


def _calculate_momentum(
    history,
):

    if not history:

        return {
            "home": 50,
            "away": 50,
            "window": "Sin datos suficientes",
            "trend": [],
        }

    current = history[-1]

    # ========================================================
    # BUSCAR APROXIMADAMENTE 10 MINUTOS ATRÁS
    # ========================================================

    target_minute = max(
        0,
        current["minute"] - 10,
    )

    previous = None

    for snapshot in reversed(history[:-1]):

        if snapshot["minute"] <= target_minute:

            previous = snapshot

            break

    # ========================================================
    # SI AÚN NO HAY HISTORIA, USAR TODO EL PARTIDO
    # ========================================================

    if previous:

        source = _snapshot_delta(
            current,
            previous,
        )

        label = f"Últimos " f"{source['window']} min"

    else:

        source = current

        label = "Presión acumulada"

    home_score = _pressure_score(
        source,
        "home",
    )

    away_score = _pressure_score(
        source,
        "away",
    )

    total = home_score + away_score

    if total <= 0:

        home_pct = 50.0
        away_pct = 50.0

    else:

        home_pct = home_score / total * 100

        away_pct = 100 - home_pct

    # ========================================================
    # HISTÓRICO VISUAL
    # ========================================================

    trend = []

    for snapshot in history:

        h_score = _pressure_score(
            snapshot,
            "home",
        )

        a_score = _pressure_score(
            snapshot,
            "away",
        )

        total_score = h_score + a_score

        if total_score <= 0:

            h_pct = 50
            a_pct = 50

        else:

            h_pct = h_score / total_score * 100

            a_pct = 100 - h_pct

        trend.append(
            {
                "minute": snapshot["minute"],
                "home": round(
                    h_pct,
                    1,
                ),
                "away": round(
                    a_pct,
                    1,
                ),
            }
        )

    return {
        "home": round(
            home_pct,
            1,
        ),
        "away": round(
            away_pct,
            1,
        ),
        "window": label,
        "trend": trend,
    }


# ============================================================
# RESOLVER EQUIPO DEL MODELO
# ============================================================


def _resolve_model_team(
    api_name,
    teams,
):

    api_key = _normalize_name(api_name)

    # ========================================================
    # COINCIDENCIA EXACTA NORMALIZADA
    # ========================================================

    for team in teams:

        if _normalize_name(team) == api_key:

            return team

    # ========================================================
    # ALIASES
    # ========================================================

    aliases = {
        "america": "club america",
        "club america": "club america",
        "pumas unam": "unam pumas",
        "unam pumas": "unam pumas",
        "atletico san luis": "atletico san luis",
        "chivas": "guadalajara chivas",
    }

    target = aliases.get(api_key)

    if target:

        for team in teams:

            if _normalize_name(team) == target:

                return team

    return None


# ============================================================
# PREMATCH DESDE DIXON-COLES
# ============================================================


def _prematch_prediction(
    detail,
    state,
):

    if not state:

        return None

    model = state.get("dc_model")

    if model is None:

        return None

    teams = (
        getattr(
            model,
            "teams",
            [],
        )
        or []
    )

    home = _resolve_model_team(
        detail["home"]["name"],
        teams,
    )

    away = _resolve_model_team(
        detail["away"]["name"],
        teams,
    )

    if not home or not away:

        return None

    try:

        prediction = model.predict_match(
            home,
            away,
        )

    except Exception:

        return None

    return {
        "model_home": home,
        "model_away": away,
        "expected_goals_home": _number(prediction.get("expected_goals_home")),
        "expected_goals_away": _number(prediction.get("expected_goals_away")),
        "probabilities": {
            "home": _number(
                prediction.get(
                    "1X2",
                    {},
                ).get("Home")
            ),
            "draw": _number(
                prediction.get(
                    "1X2",
                    {},
                ).get("Draw")
            ),
            "away": _number(
                prediction.get(
                    "1X2",
                    {},
                ).get("Away")
            ),
        },
    }


# ============================================================
# PROYECCIÓN LIVE
# ============================================================


def _live_projection(
    detail,
    prematch,
):

    if not prematch:

        return None

    elapsed = detail.get(
        "status",
        {},
    ).get("elapsed")

    if elapsed is None:

        return None

    elapsed = max(
        0,
        min(
            90,
            int(elapsed),
        ),
    )

    current_home = int(_number(detail["home"]["goals"]))

    current_away = int(_number(detail["away"]["goals"]))

    remaining_fraction = (
        max(
            0,
            90 - elapsed,
        )
        / 90
    )

    remaining_home_xg = prematch["expected_goals_home"] * remaining_fraction

    remaining_away_xg = prematch["expected_goals_away"] * remaining_fraction

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0

    max_remaining_goals = 7

    for home_extra in range(max_remaining_goals + 1):

        home_probability = poisson.pmf(
            home_extra,
            remaining_home_xg,
        )

        for away_extra in range(max_remaining_goals + 1):

            away_probability = poisson.pmf(
                away_extra,
                remaining_away_xg,
            )

            probability = home_probability * away_probability

            final_home = current_home + home_extra

            final_away = current_away + away_extra

            if final_home > final_away:

                p_home += probability

            elif final_home == final_away:

                p_draw += probability

            else:

                p_away += probability

    total = p_home + p_draw + p_away

    if total > 0:

        p_home /= total
        p_draw /= total
        p_away /= total

    return {
        "method": "Score + tiempo restante + Dixon-Coles",
        "minute": elapsed,
        "remaining_expected_goals": {
            "home": round(
                remaining_home_xg,
                3,
            ),
            "away": round(
                remaining_away_xg,
                3,
            ),
        },
        "probabilities": {
            "home": round(
                p_home,
                4,
            ),
            "draw": round(
                p_draw,
                4,
            ),
            "away": round(
                p_away,
                4,
            ),
        },
    }


# ============================================================
# CAMBIOS VS PREMATCH
# ============================================================


def _probability_shift(
    prematch,
    live,
):

    if not prematch or not live:

        return None

    output = {}

    for side in (
        "home",
        "draw",
        "away",
    ):

        before = prematch["probabilities"][side]

        now = live["probabilities"][side]

        output[side] = {
            "prematch": round(
                before,
                4,
            ),
            "live": round(
                now,
                4,
            ),
            "change": round(
                now - before,
                4,
            ),
        }

    return output


# ============================================================
# SEÑALES
# ============================================================


def _signals(
    detail,
    momentum,
):

    signals = []

    home_name = detail["home"]["name"]

    away_name = detail["away"]["name"]

    # ========================================================
    # MOMENTUM
    # ========================================================

    if momentum["home"] >= 65:

        signals.append(
            {
                "type": "momentum",
                "level": "high",
                "title": f"Presión de {home_name}",
                "description": "El equipo local concentra "
                "la mayor actividad ofensiva "
                "del periodo analizado.",
            }
        )

    elif momentum["away"] >= 65:

        signals.append(
            {
                "type": "momentum",
                "level": "high",
                "title": f"Presión de {away_name}",
                "description": "El visitante concentra "
                "la mayor actividad ofensiva "
                "del periodo analizado.",
            }
        )

    # ========================================================
    # CÓRNERS
    # ========================================================

    corners = _stat(
        detail,
        "home",
        "Corner Kicks",
    ) + _stat(
        detail,
        "away",
        "Corner Kicks",
    )

    if corners >= 8:

        signals.append(
            {
                "type": "corners",
                "level": "medium",
                "title": "Volumen alto de córners",
                "description": f"El encuentro acumula "
                f"{int(corners)} tiros de esquina.",
            }
        )

    # ========================================================
    # TIROS A PUERTA
    # ========================================================

    shots_on_goal = _stat(
        detail,
        "home",
        "Shots on Goal",
    ) + _stat(
        detail,
        "away",
        "Shots on Goal",
    )

    if shots_on_goal >= 8:

        signals.append(
            {
                "type": "attack",
                "level": "medium",
                "title": "Partido de alta producción",
                "description": f"Se registran "
                f"{int(shots_on_goal)} "
                "tiros a portería.",
            }
        )

    # ========================================================
    # TARJETAS
    # ========================================================

    cards = (
        _stat(
            detail,
            "home",
            "Yellow Cards",
        )
        + _stat(
            detail,
            "away",
            "Yellow Cards",
        )
        + _stat(
            detail,
            "home",
            "Red Cards",
        )
        + _stat(
            detail,
            "away",
            "Red Cards",
        )
    )

    if cards >= 5:

        signals.append(
            {
                "type": "cards",
                "level": "medium",
                "title": "Intensidad disciplinaria",
                "description": f"El partido acumula " f"{int(cards)} tarjetas.",
            }
        )

    return signals[:5]


# ============================================================
# ENTRY POINT
# ============================================================


def build_live_intelligence(
    detail,
    state=None,
):

    history = _record_snapshot(detail)

    momentum = _calculate_momentum(history)

    prematch = _prematch_prediction(
        detail,
        state,
    )

    live = _live_projection(
        detail,
        prematch,
    )

    shift = _probability_shift(
        prematch,
        live,
    )

    return {
        "momentum": momentum,
        "prematch": prematch,
        "live_projection": live,
        "probability_shift": shift,
        "signals": _signals(
            detail,
            momentum,
        ),
    }

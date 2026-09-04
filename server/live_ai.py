import json
import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent

PROJECT_DIR = SERVER_DIR.parent


load_dotenv(PROJECT_DIR / ".env")


OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna",
)


# ============================================================
# OPENAI OPCIONAL
# ============================================================

try:

    from openai import OpenAI

except ImportError:

    OpenAI = None


# ============================================================
# FORMATEAR PORCENTAJE
# ============================================================


def _pct(
    value,
):

    if value is None:
        return "N/D"

    return f"{float(value) * 100:.1f}%"


# ============================================================
# ANALISTA LOCAL
# ============================================================


def _local_analysis(
    detail,
    intelligence,
    question,
):

    home = detail["home"]["name"]

    away = detail["away"]["name"]

    home_goals = detail["home"]["goals"]

    away_goals = detail["away"]["goals"]

    minute = (
        detail.get(
            "status",
            {},
        ).get("elapsed")
        or 0
    )

    momentum = intelligence.get(
        "momentum",
        {},
    )

    home_momentum = float(
        momentum.get(
            "home",
            50,
        )
    )

    away_momentum = float(
        momentum.get(
            "away",
            50,
        )
    )

    if home_momentum > away_momentum + 10:

        dominant = home

        dominance_text = (
            f"{home} concentra " f"{home_momentum:.1f}% " "del índice de presión."
        )

    elif away_momentum > home_momentum + 10:

        dominant = away

        dominance_text = (
            f"{away} concentra " f"{away_momentum:.1f}% " "del índice de presión."
        )

    else:

        dominant = None

        dominance_text = "La presión reciente se mantiene " "relativamente equilibrada."

    live = intelligence.get("live_projection")

    probability_text = ""

    if live:

        probabilities = live["probabilities"]

        options = [
            (
                home,
                probabilities["home"],
            ),
            (
                "Empate",
                probabilities["draw"],
            ),
            (
                away,
                probabilities["away"],
            ),
        ]

        leader = max(
            options,
            key=lambda item: item[1],
        )

        probability_text = (
            f" La proyección live sitúa "
            f"a {leader[0]} como el escenario "
            f"más probable con "
            f"{_pct(leader[1])}."
        )

    signals = intelligence.get(
        "signals",
        [],
    )

    signal_text = ""

    if signals:

        signal_text = (
            " Señales detectadas: "
            + "; ".join(signal["title"] for signal in signals[:3])
            + "."
        )

    question_lower = question.strip().lower()

    if "domina" in question_lower or "mejor" in question_lower:

        intro = dominance_text

    elif "cambio" in question_lower or "prematch" in question_lower:

        shift = intelligence.get("probability_shift")

        if shift:

            home_change = shift["home"]["change"] * 100

            away_change = shift["away"]["change"] * 100

            intro = (
                f"Respecto al pre-match, "
                f"{home} cambió "
                f"{home_change:+.1f} puntos "
                f"porcentuales y "
                f"{away} "
                f"{away_change:+.1f}."
            )

        else:

            intro = (
                "Todavía no existe una comparación "
                "pre-match disponible para este encuentro."
            )

    else:

        intro = (
            f"Al minuto {minute}, "
            f"{home} {home_goals}-{away_goals} "
            f"{away}. "
            f"{dominance_text}"
        )

    return (
        f"{intro}"
        f"{probability_text}"
        f"{signal_text} "
        "La lectura es estadística y puede cambiar "
        "conforme ingresen nuevos eventos."
    )


# ============================================================
# OPENAI
# ============================================================


def _openai_analysis(
    detail,
    intelligence,
    question,
):

    if not OPENAI_API_KEY or OpenAI is None:

        return None

    client = OpenAI(
        api_key=OPENAI_API_KEY,
    )

    snapshot = {
        "partido": {
            "minuto": detail.get(
                "status",
                {},
            ).get("elapsed"),
            "local": detail.get("home"),
            "visitante": detail.get("away"),
            "arbitro": detail.get("referee"),
        },
        "estadisticas": detail.get("statistics"),
        "eventos": detail.get(
            "events",
            [],
        )[-15:],
        "intelligence": intelligence,
    }

    instructions = """
Eres MatchLab AI Analyst, analista especializado en Liga MX.

Reglas obligatorias:

1. Usa exclusivamente la información JSON recibida.
2. Nunca inventes estadísticas, eventos, jugadores o probabilidades.
3. Si un dato no está disponible, dilo claramente.
4. Diferencia siempre datos reales del partido de estimaciones del modelo.
5. No prometas resultados ni presentes apuestas como seguras.
6. Responde en español de México.
7. Sé breve, profesional y analítico.
8. Prioriza cambios de dinámica, momentum, marcador, tiros,
   córners, disciplina y cambios pre-match vs live.
9. No repitas todos los datos; interpreta los más importantes.
10. Máximo 180 palabras.
"""

    input_text = (
        "DATOS DEL PARTIDO:\n"
        + json.dumps(
            snapshot,
            ensure_ascii=False,
            default=str,
        )
        + "\n\nPREGUNTA DEL USUARIO:\n"
        + question
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions,
        input=input_text,
        max_output_tokens=450,
    )

    return response.output_text.strip()


# ============================================================
# ENTRY POINT
# ============================================================


def answer_live_question(
    detail,
    intelligence,
    question,
):

    question = str(
        question or "",
    ).strip()

    if not question:

        question = "Resume lo más importante " "del partido en este momento."

    # ========================================================
    # INTENTAR IA EXTERNA
    # ========================================================

    try:

        generated = _openai_analysis(
            detail,
            intelligence,
            question,
        )

        if generated:

            return {
                "provider": "openai",
                "answer": generated,
            }

    except Exception as exc:

        print(
            "MatchLab AI fallback:",
            exc,
        )

    # ========================================================
    # FALLBACK LOCAL
    # ========================================================

    return {
        "provider": "local",
        "answer": _local_analysis(
            detail,
            intelligence,
            question,
        ),
    }

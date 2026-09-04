"""api_server"""

import os
from contextlib import asynccontextmanager
import time

from pathlib import Path
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from live_service import (
    LiveFootballService,
    get_quota_status,
)
from live_intelligence import build_live_intelligence
from live_ai import answer_live_question

from prediccion_ligamx import (
    DixonColesModel,
    SpecialMarketsModel,
    analizar_h2h,
)

## Configuración
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

## Directorios
SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent

## FrontEnd Compilado
FRONTEND_CANDIDATES = [
    # Proyecto normal
    PROJECT_DIR / "dist",
    # Release compilado
    PROJECT_DIR / "web",
]
FRONTEND_DIR = None

for candidate in FRONTEND_CANDIDATES:
    if candidate.is_dir():
        FRONTEND_DIR = candidate
        break

CSV_PATH = os.path.join(
    BASE_DIR,
    "historial_ligamx_2023.csv",
)

## Equivalencias
EQUIVALENCIAS = {
    "Atlante": "Mazatlán",
}

## Estado Global
STATE = {
    "df": None,
    "dc_model": None,
    "spec_model": None,
    "equipos": [],
    "arbitros": [],
}

# ============================================================
# LIVE CENTER
# ============================================================

LIVE_SERVICE = LiveFootballService()


class LiveAIRequest(BaseModel):
    question: str = ""


## Modelo Petición
class PrediccionRequest(BaseModel):
    """Modelo Petición"""

    local: str
    visitante: str
    arbitro: str


class ResolveLiveRequest(BaseModel):
    event_id: str | None = None
    date: str
    home: str
    away: str


class LiveAIRequest(BaseModel):
    question: str = ""


def convertir_json(valor):
    """Convierte recursivamente tipos de Numpy y contenedores a formatos compatibles con JSON"""

    if isinstance(valor, dict):
        return {key: convertir_json(value) for key, value in valor.items()}

    if isinstance(valor, (list, tuple)):
        return [convertir_json(item) for item in valor]

    if isinstance(valor, np.ndarray):
        return valor.tolist()

    if isinstance(valor, np.integer):
        return int(valor)

    if isinstance(valor, np.floating):
        return None if np.isnan(valor) else float(valor)

    return valor


def obtener_valores_unicos(serie):
    """Limpieza de catálogo"""

    valores = {}

    for valor in serie:
        if pd.isna(valor):
            continue

        texto = str(valor).strip()
        if not texto:
            continue

        normalizado = texto.lower()
        if normalizado in [
            "nan",
            "null",
            "none",
            "n/a",
        ]:
            continue

        if normalizado not in valores:
            valores[normalizado] = texto

    resultado = list(valores.values())
    resultado.sort(key=lambda item: item.casefold())

    return resultado


def inicializar_modelos():
    """INICIALIZAR SISTEMA"""

    print("\n" + "=" * 50)
    print("⚽ MATCHLAB - INICIANDO MOTOR ESTADÍSTICO")
    print("=" * 50)

    ## Validar CSV
    if not os.path.isfile(CSV_PATH):
        raise FileNotFoundError(f"No se encontró el CSV: {CSV_PATH}")

    print(f"📂 CSV: {CSV_PATH}")

    ## Cargar CSV
    df = pd.read_csv(CSV_PATH)

    if df.empty:
        raise RuntimeError("El CSV no contiene registros.")

    ## Validar columnas
    columnas_obligatorias = [
        "home_team",
        "away_team",
        "referee",
        "home_goals",
        "away_goals",
        "home_corners",
        "away_corners",
        "total_corners",
        "home_cards",
        "away_cards",
        "total_cards",
        "date",
    ]

    faltantes = [
        columna for columna in columnas_obligatorias if columna not in df.columns
    ]

    if faltantes:
        raise RuntimeError("Faltan columnas obligatorias: " + ", ".join(faltantes))

    print(f"✅ Partidos cargados: {len(df)}")

    ## Catálogo de equipos
    equipos = obtener_valores_unicos(df["home_team"])

    ## Catálogo de arbitros
    arbitros = obtener_valores_unicos(df["referee"])

    ## Desconocido siempre al inicio
    arbitros = [arbitro for arbitro in arbitros if arbitro.casefold() != "desconocido"]
    arbitros.insert(0, "Desconocido")

    print(f"✅ Equipos disponibles: {len(equipos)}")
    print(f"✅ Árbitros disponibles: {len(arbitros)}")

    ## Entrenamiento de modelo Dixon-Coles
    print("\n⚙️ Entrenando Dixon-Coles...")
    tiempo_inicio_dc = time.time()
    dc_model = DixonColesModel()
    dc_model.fit(df.copy())
    # print("✅ Dixon-Coles preparado.")
    tiempo_dc = time.time() - tiempo_inicio_dc
    print(f"✅ Dixon-Coles preparado en {tiempo_dc:.2f} segundos.")

    ## Entrenamiento de mercados especiales
    print("⚙️ Preparando mercados de córners y tarjetas...")
    tiempo_inicio_sm = time.time()
    spec_model = SpecialMarketsModel()
    spec_model.fit(df.copy())
    # print("✅ Mercados especiales preparados.")
    tiempo_sm = time.time() - tiempo_inicio_sm
    print(f"✅ Mercados especiales preparados en {tiempo_sm:.2f} segundos.")

    ##Guardado en memoria
    STATE["df"] = df
    STATE["dc_model"] = dc_model
    STATE["spec_model"] = spec_model
    STATE["equipos"] = equipos
    STATE["arbitros"] = arbitros

    print("\n" + "=" * 50)
    print("🟢 MOTOR LISTO")
    print("=" * 50 + "\n")


## Lifespan FastAPI
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan FastAPI"""

    inicializar_modelos()
    yield


## FastAPI
app = FastAPI(
    title="MatchLab API",
    version="1.0.0",
    lifespan=lifespan,
)

## CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=(r"http://(localhost|127\.0\.0\.1):\d+"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


## Health
@app.get("/api/health")
def health():
    """Valida si el api esta viva"""

    return {
        "success": True,
        "status": "READY",
        "partidos": (len(STATE["df"]) if STATE["df"] is not None else 0),
        "equipos": len(STATE["equipos"]),
        "arbitros": len(STATE["arbitros"]),
    }


## Catálogos
@app.get("/api/catalogos")
def obtener_catalogos():
    """Obtiene catálogos"""

    return {
        "success": True,
        "equipos": STATE["equipos"],
        "arbitros": STATE["arbitros"],
        "totales": {
            "equipos": len(STATE["equipos"]),
            "arbitros": len(STATE["arbitros"]),
        },
    }


## Predicción
@app.post("/api/prediccion")
def calcular_prediccion(request: PrediccionRequest):
    """Ejecuta calculos de predicciones"""

    ## Parámetros
    local = request.local.strip()
    visitante = request.visitante.strip()
    arbitro = request.arbitro.strip()

    ## Validaciones
    if not local:
        raise HTTPException(
            status_code=400,
            detail=("El equipo local es obligatorio."),
        )

    if not visitante:
        raise HTTPException(
            status_code=400,
            detail=("El equipo visitante es obligatorio."),
        )

    if not arbitro:
        raise HTTPException(
            status_code=400,
            detail=("El árbitro es obligatorio."),
        )

    if local.casefold() == visitante.casefold():
        raise HTTPException(
            status_code=400,
            detail=("El equipo local y visitante " "no pueden ser iguales."),
        )

    ## Validar Equipos
    equipos_validos = {equipo.casefold() for equipo in STATE["equipos"]}

    if local.casefold() not in equipos_validos:
        raise HTTPException(
            status_code=400,
            detail=(f"El equipo local '{local}' " "no existe en el histórico."),
        )

    if visitante.casefold() not in equipos_validos:
        raise HTTPException(
            status_code=400,
            detail=(f"El equipo visitante '{visitante}' " "no existe en el histórico."),
        )

    ## Equivalencias
    local_modelo = EQUIVALENCIAS.get(
        local,
        local,
    )

    visitante_modelo = EQUIVALENCIAS.get(
        visitante,
        visitante,
    )

    try:
        df = STATE["df"]
        dc_model = STATE["dc_model"]
        spec_model = STATE["spec_model"]

        ## H2H
        h2h = analizar_h2h(
            df,
            local_modelo,
            visitante_modelo,
        )

        ## Goles
        goles = dc_model.predict_match(
            local_modelo,
            visitante_modelo,
        )

        ## Córners
        corners = spec_model.predict_corners(
            local_modelo,
            visitante_modelo,
        )

        ## Tarjetas
        cards = spec_model.predict_cards(
            local_modelo,
            visitante_modelo,
            referee=arbitro,
        )

        ## Respuesta
        resultado = {
            "success": True,
            "partido": {
                "local": local,
                "visitante": visitante,
                "arbitro": arbitro,
            },
            "modelo": {
                "local": local_modelo,
                "visitante": visitante_modelo,
            },
            "h2h": {
                "resumen": h2h,
            },
            "goles": goles,
            "corners": corners,
            "tarjetas": cards,
        }

        return convertir_json(resultado)

    except Exception as error:

        print("❌ ERROR DE PREDICCIÓN:")
        print(error)
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


# ============================================================
# LIVE - LISTADO
#
# THE SPORTS DB
# ============================================================


# ============================================================
# LIVE CENTER
# ============================================================


@app.get("/api/live")
def obtener_partidos_live(
    scope: str = Query(
        default="today",
        pattern="^(live|today)$",
    ),
):

    try:

        result = LIVE_SERVICE.get_matches(scope=scope)

        return {
            "success": True,
            "scope": scope,
            **result,
        }

    except Exception as error:

        print(
            "ERROR LIVE CENTER:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# QUOTA
# ============================================================


@app.get("/api/live/quota/status")
def obtener_live_quota():

    return {
        "success": True,
        "quota": get_quota_status(),
    }


# ============================================================
# LIVE - RESOLVER PARTIDO
#
# THE SPORTS DB -> API FOOTBALL
#
# DEBE IR ANTES DE /{fixture_id}
# ============================================================


@app.post("/api/live/resolve")
def resolver_live_match(
    request: ResolveLiveRequest,
):

    try:

        result = LIVE_SERVICE.resolve_match(
            date=request.date,
            home=request.home,
            away=request.away,
        )

        return {
            "success": True,
            **result,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# LIVE - DETALLE
# ============================================================


@app.get("/api/live/{fixture_id}")
def obtener_detalle_live(
    fixture_id: int,
):

    try:

        detail = LIVE_SERVICE.get_fixture_detail(fixture_id)

        intelligence = build_live_intelligence(
            detail,
            STATE,
        )

        return {
            "success": True,
            "provider": "api-football",
            "data": {
                **detail,
                "intelligence": intelligence,
            },
        }

    except Exception as error:

        print(
            "ERROR LIVE DETAIL:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# LIVE - MATCHLAB AI
# ============================================================


@app.post("/api/live/{fixture_id}/ai")
def consultar_live_ai(
    fixture_id: int,
    request: LiveAIRequest,
):

    try:

        detail = LIVE_SERVICE.get_fixture_detail(fixture_id)

        intelligence = build_live_intelligence(
            detail,
            STATE,
        )

        response = answer_live_question(
            detail,
            intelligence,
            request.question,
        )

        return {
            "success": True,
            **response,
        }

    except Exception as error:

        print(
            "ERROR LIVE AI:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


## FrontEnd React
if FRONTEND_DIR is not None:

    print(f"🌐 Frontend encontrado: {FRONTEND_DIR}")
    app.mount(
        "/",
        StaticFiles(
            directory=str(FRONTEND_DIR),
            html=True,
        ),
        name="frontend",
    )

else:

    print("ℹ️ Frontend compilado no encontrado.")
    print("   En desarrollo utiliza: npm run dev")

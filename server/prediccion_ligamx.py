import os
import sys
import time
from datetime import datetime
import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from team_identity import normalize_history_teams, normalize_team_name

# ==========================================
# 1. CONFIGURACION
# ==========================================
API_KEY = "4d8aa137f38c36e55a3e1adcc5e203dc"  # Principal
BASE_URL = "https://v3.football.api-sports.io"
LIGA_MX_ID = 262


# ==========================================
# 2. CLIENTE DE EXTRACCION DE DATOS
# ==========================================
class LigaMXDataFetcher:
    def __init__(self, api_key):
        self.headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": api_key,
        }

    def _get(self, endpoint, params, retries=3):
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)

                # Si es exitoso
                if response.status_code == 200:
                    json_data = response.json()

                    # NUEVO: Revisar si la API devolvio un error en el texto (ej. limite diario)
                    api_errors = json_data.get("errors", [])
                    if api_errors:
                        print(f"Error de la API: {api_errors}")
                        return []
                    time.sleep(
                        6.5
                    )  # <-- Pausa obligatoria de 6.5s para no superar 10 req/minuto
                    return json_data.get("response", [])

                # Si topamos con el limite de la API (Error 429)
                elif response.status_code == 429:
                    print(
                        f"Limite de API alcanzado (Error 429). Pausando 15 segundos antes de reintentar... (Intento {attempt+1}/{retries})"
                    )
                    time.sleep(15)  # Pausa larga para que la API libere nuestra IP
                    continue

                else:
                    print(f"Error API: {response.status_code}")
                    return []

            except Exception as e:
                print(f"Error de conexion: {e}. Reintentando en 5s...")
                time.sleep(5)

        print("❌ Se agotaron los reintentos para esta peticion.")
        return []

    def actualizar_historico(self, seasons=[2023, 2024, 2025], limite_descargas=40):
        """
        Lee el CSV actual, identifica que partidos ya tienes, y SOLO
        descarga los que falten. Protege tu limite de API diario.
        """
        archivo_local = "historial_ligamx_2023.csv"

        # 1. Cargar historial existente para saber que IDs ya tenemos
        if os.path.exists(archivo_local):
            df_existente = pd.read_csv(archivo_local)
            # Guardamos los IDs que ya tenemos en un set para busqueda rapida
            ids_descargados = set(df_existente["fixture_id"].astype(int).tolist())
            print(f"✅ Historial local encontrado con {len(ids_descargados)} partidos.")
        else:
            df_existente = pd.DataFrame()
            ids_descargados = set()
            print("⚠️ No se encontro historial. Se creara uno nuevo.")

        nuevos_datos = []
        descargas_actuales = 0

        for season in seasons:
            print(f"Consultando calendario de la temporada {season}...")
            fixtures = self._get(
                "fixtures", {"league": str(LIGA_MX_ID), "season": str(season)}
            )

            # Filtrar solo los partidos que ya terminaron (FT)
            terminados = [
                f for f in fixtures if f["fixture"]["status"]["short"] == "FT"
            ]

            for fix in terminados:
                fix_id = fix["fixture"]["id"]

                # 2. Si el partido ya esta en el CSV, lo saltamos
                if fix_id in ids_descargados:
                    continue

                # 3. Limite de seguridad para no agotar la API gratuita
                if descargas_actuales >= limite_descargas:
                    print(
                        f"🛑 Limite de seguridad alcanzado ({limite_descargas} descargas). Ejecuta de nuevo mañana para seguir alimentando la base."
                    )
                    break

                home = normalize_team_name(fix["teams"]["home"]["name"])
                away = normalize_team_name(fix["teams"]["away"]["name"])
                print(f"📥 Descargando partido nuevo: {home} vs {away}...")

                # Extraer estadisticas
                stats = self._get("fixtures/statistics", {"fixture": str(fix_id)})

                h_corners, a_corners, h_yellow, a_yellow, h_red, a_red = (
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                )
                for team_stat in stats:
                    is_home = team_stat["team"]["name"] == home
                    s_dict = {
                        s["type"]: s["value"]
                        for s in team_stat.get("statistics", [])
                        if s["value"] is not None
                    }

                    if is_home:
                        h_corners = s_dict.get("Corner Kicks", 0)
                        h_yellow = s_dict.get("Yellow Cards", 0)
                        h_red = s_dict.get("Red Cards", 0)
                    else:
                        a_corners = s_dict.get("Corner Kicks", 0)
                        a_yellow = s_dict.get("Yellow Cards", 0)
                        a_red = s_dict.get("Red Cards", 0)

                nuevos_datos.append(
                    {
                        "fixture_id": fix_id,
                        "date": fix["fixture"]["date"],
                        "referee": fix["fixture"].get("referee", "Desconocido"),
                        "home_team": home,
                        "away_team": away,
                        "home_goals": fix["goals"]["home"],
                        "away_goals": fix["goals"]["away"],
                        "home_corners": h_corners,
                        "away_corners": a_corners,
                        "total_corners": h_corners + a_corners,
                        "home_cards": h_yellow + (h_red * 2),
                        "away_cards": a_yellow + (a_red * 2),
                        "total_cards": (h_yellow + a_yellow) + ((h_red + a_red) * 2),
                    }
                )

                descargas_actuales += 1

            if descargas_actuales >= limite_descargas:
                break

        # 4. Combinar datos viejos con nuevos y guardar
        if nuevos_datos:
            df_nuevos = pd.DataFrame(nuevos_datos)
            df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
            df_final.to_csv(archivo_local, index=False)
            print(
                f"✅ Se añadieron {len(df_nuevos)} partidos nuevos al historial de forma permanente."
            )
            return df_final
        else:
            print(
                "✅ El historial esta al dia. No hay partidos nuevos terminados para descargar."
            )
            return df_existente

    def obtener_partidos_por_fecha(self, fecha):
        """Busca partidos programados para una fecha YYYY-MM-DD."""
        print(f"Buscando cartelera para la fecha: {fecha}...")

        params = {
            "league": str(LIGA_MX_ID),
            "season": fecha[:4],
            "date": fecha,
            "timezone": "America/Mazatlan",
        }

        fixtures = self._get("fixtures", params)

        partidos = []
        for fix in fixtures:
            partidos.append(
                {
                    "home_team": normalize_team_name(fix["teams"]["home"]["name"]),
                    "away_team": normalize_team_name(fix["teams"]["away"]["name"]),
                    "referee": fix["fixture"].get("referee", "Desconocido"),
                }
            )
        return partidos


def analizar_h2h(df, equipo_a, equipo_b):
    """Filtra el historial para obtener promedios de enfrentamientos directos (H2H)"""
    # Buscar partidos donde A fue local y B visitante, o viceversa
    h2h_df = df[
        ((df["home_team"] == equipo_a) & (df["away_team"] == equipo_b))
        | ((df["home_team"] == equipo_b) & (df["away_team"] == equipo_a))
    ]

    if h2h_df.empty:
        return "No hay registro de enfrentamientos recientes entre estos equipos."

    partidos = len(h2h_df)
    goles_promedio = (
        h2h_df["home_goals"].sum() + h2h_df["away_goals"].sum()
    ) / partidos
    corners_promedio = h2h_df["total_corners"].sum() / partidos
    tarjetas_promedio = h2h_df["total_cards"].sum() / partidos

    return f"Se han enfrentado {partidos} veces. Promedios H2H -> Goles: {goles_promedio:.1f} | Corners: {corners_promedio:.1f} | Tarjetas: {tarjetas_promedio:.1f}"


# ==========================================
# 3. MODELOS MATEMaTICOS
# ==========================================
class DixonColesModel:
    def __init__(self, decay_xi=0.003):
        self.decay_xi = decay_xi
        self.teams = []
        self.home_advantage = 0.25
        self.rho = -0.05
        self.attack = {}
        self.defense = {}

    def fit(self, df):
        self.teams = sorted(
            list(set(df["home_team"].unique()) | set(df["away_team"].unique()))
        )
        n = len(self.teams)
        team_idx = {team: i for i, team in enumerate(self.teams)}

        df["date"] = pd.to_datetime(df["date"], utc=True)
        max_date = df["date"].max()
        weights = np.exp(-self.decay_xi * (max_date - df["date"]).dt.days.values)

        init_params = np.concatenate([np.zeros(n - 1), np.zeros(n), [0.25], [-0.05]])

        # Pre-extraer datos
        h_idx = np.array([team_idx[t] for t in df["home_team"]])
        a_idx = np.array([team_idx[t] for t in df["away_team"]])
        x = df["home_goals"].values.astype(int)
        y = df["away_goals"].values.astype(int)
        w = weights  # weights es un array de numpy

        # Mascaras booleanas pre-calculadas para correccion rho
        mask_00 = (x == 0) & (y == 0)
        mask_01 = (x == 0) & (y == 1)
        mask_10 = (x == 1) & (y == 0)
        mask_11 = (x == 1) & (y == 1)

        def log_likelihood(params):
            alphas = np.append(params[: n - 1], -np.sum(params[: n - 1]))
            betas = params[n - 1 : 2 * n - 1]
            gamma = params[2 * n - 1]
            rho = params[2 * n]

            # Calculos Matriciales
            lambd = np.exp(alphas[h_idx] + betas[a_idx] + gamma)
            mu = np.exp(alphas[a_idx] + betas[h_idx])

            # Poisson base
            prob_ind = poisson.pmf(x, lambd) * poisson.pmf(y, mu)

            # Ajuste de Correlacion
            tau = np.ones_like(x, dtype=float)
            tau[mask_00] = 1 - (lambd[mask_00] * mu[mask_00] * rho)
            tau[mask_01] = 1 + (lambd[mask_01] * rho)
            tau[mask_10] = 1 + (mu[mask_10] * rho)
            tau[mask_11] = 1 - rho

            # Evitar logaritmos de cero
            p = np.maximum(prob_ind * tau, 1e-10)

            # Suma final ponderada por el decaimiento de tiempo
            ll = np.sum(w * np.log(p))

            return -ll

        res = minimize(log_likelihood, init_params, method="L-BFGS-B")

        alphas = np.append(res.x[: n - 1], -np.sum(res.x[: n - 1]))
        betas = res.x[n - 1 : 2 * n - 1]
        self.home_advantage, self.rho = res.x[2 * n - 1], res.x[2 * n]

        for i, team in enumerate(self.teams):
            self.attack[team], self.defense[team] = alphas[i], betas[i]

    def predict_match(self, home_team, away_team, max_goals=8):
        # Valores promedio si el equipo es nuevo (recien ascendido)
        att_h = self.attack.get(home_team, 0.0)
        def_h = self.defense.get(home_team, 0.0)
        att_a = self.attack.get(away_team, 0.0)
        def_a = self.defense.get(away_team, 0.0)

        lambd = np.exp(att_h + def_a + self.home_advantage)
        mu = np.exp(att_a + def_h)

        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                tau = 1.0
                if x == 0 and y == 0:
                    tau = 1 - (lambd * mu * self.rho)
                elif x == 0 and y == 1:
                    tau = 1 + (lambd * self.rho)
                elif x == 1 and y == 0:
                    tau = 1 + (mu * self.rho)
                elif x == 1 and y == 1:
                    tau = 1 - self.rho

                prob = poisson.pmf(x, lambd) * poisson.pmf(y, mu) * tau
                matrix[x, y] = max(0, prob)

        matrix /= matrix.sum()

        total_grid = np.fromfunction(lambda i, j: i + j, (max_goals + 1, max_goals + 1))

        # --- CALCULO: TOP 5 MARCADORES ---
        flat_indices = np.argsort(matrix.flatten())[::-1][:5]
        top_scores = {}
        for idx in flat_indices:
            hx, ay = np.unravel_index(idx, matrix.shape)
            top_scores[f"{hx}-{ay}"] = matrix[hx, ay]
        # ---------------------------------------

        return {
            "expected_goals_home": lambd,
            "expected_goals_away": mu,
            "1X2": {
                "Home": np.sum(np.tril(matrix, -1)),
                "Draw": np.sum(np.diag(matrix)),
                "Away": np.sum(np.triu(matrix, 1)),
            },
            "Over_Under": {
                "Over 1.5": np.sum(matrix[total_grid > 1.5]),
                "Under 1.5": np.sum(matrix[total_grid < 1.5]),
                "Over 2.5": np.sum(matrix[total_grid > 2.5]),
                "Under 2.5": np.sum(matrix[total_grid < 2.5]),
            },
            "BTTS": {"Yes": np.sum(matrix[1:, 1:]), "No": 1.0 - np.sum(matrix[1:, 1:])},
            "Top_Scores": top_scores,  # <--- Agregamos el Top 5 al resultado
        }


# Version 2 (Ponderacion Bayesiana y Separacion Local/Visitante)
class SpecialMarketsModel:
    def __init__(self):
        self.df_historico = None
        self.league_avg_cards = 4.5
        self.ref_bias = {}

    def fit(self, df):
        self.df_historico = df

        # Calcular el sesgo del árbitro (qué tanto se desvía del promedio de la liga)
        self.league_avg_cards = df["total_cards"].mean()
        if pd.isna(self.league_avg_cards) or self.league_avg_cards == 0:
            self.league_avg_cards = 4.5

        for ref, group in df.groupby("referee"):
            if len(group) >= 3:
                self.ref_bias[ref] = group["total_cards"].mean() / self.league_avg_cards
            else:
                self.ref_bias[ref] = 1.0

    def _obtener_promedios_especificos(self, equipo, es_local):
        """Calcula el rendimiento específico de un equipo dependiendo si es local o visitante."""
        df = self.df_historico
        if es_local:
            partidos = df[df["home_team"] == equipo]
            if partidos.empty:
                return 5.0, 2.0  # Valores por defecto
            corners = partidos["home_corners"].mean()
            cards = partidos["home_cards"].mean()
        else:
            partidos = df[df["away_team"] == equipo]
            if partidos.empty:
                return 5.0, 2.0
            corners = partidos["away_corners"].mean()
            cards = partidos["away_cards"].mean()

        return corners, cards

    def _obtener_h2h(self, home_team, away_team):
        """Calcula el promedio exacto de los enfrentamientos entre estos dos equipos."""
        df = self.df_historico
        h2h = df[
            ((df["home_team"] == home_team) & (df["away_team"] == away_team))
            | ((df["home_team"] == away_team) & (df["away_team"] == home_team))
        ]

        if len(h2h) == 0:
            return None, None

        avg_corners = h2h["total_corners"].mean()
        avg_cards = h2h["total_cards"].mean()
        return avg_corners, avg_cards

    def predict_corners(self, home_team, away_team):
        """Calcula promedio de corners"""
        # Fuerza específica (Local atacando vs Visitante defendiendo)
        corners_for_home, _ = self._obtener_promedios_especificos(
            home_team, es_local=True
        )
        corners_for_away, _ = self._obtener_promedios_especificos(
            away_team, es_local=False
        )

        # Expectativa base general
        base_exp = corners_for_home + corners_for_away

        # Factor H2H (Ponderación del 25% si existe historial)
        h2h_corners, _ = self._obtener_h2h(home_team, away_team)
        if h2h_corners is not None:
            total_exp = (base_exp * 0.75) + (h2h_corners * 0.25)
        else:
            total_exp = base_exp

        # Distribuir la expectativa total ajustada hacia cada equipo
        if base_exp > 0:
            home_ratio = corners_for_home / base_exp
            away_ratio = corners_for_away / base_exp
        else:
            home_ratio, away_ratio = 0.5, 0.5

        home_exp = total_exp * home_ratio
        away_exp = total_exp * away_ratio

        return {
            "expected_total": total_exp,
            "expected_1H": total_exp * 0.45,
            # Mercados de partido completo y 1ra mitad
            "Over 9.5": 1 - poisson.cdf(9, total_exp),
            "Under 9.5": poisson.cdf(9, total_exp),
            "Over 4.5 1H": 1 - poisson.cdf(4, total_exp * 0.45),
            "Under 4.5 1H": poisson.cdf(4, total_exp * 0.45),
            # --- MERCADOS INDIVIDUALES POR EQUIPO ---
            "expected_home": home_exp,
            "expected_away": away_exp,
            # Local: Over/Under 4.5 y 5.5 corners
            "Home_Over_4.5": 1 - poisson.cdf(4, home_exp),
            "Home_Under_4.5": poisson.cdf(4, home_exp),
            "Home_Over_5.5": 1 - poisson.cdf(5, home_exp),
            "Home_Under_5.5": poisson.cdf(5, home_exp),
            # Visitante: Over/Under 3.5 y 4.5 corners
            "Away_Over_3.5": 1 - poisson.cdf(3, away_exp),
            "Away_Under_3.5": poisson.cdf(3, away_exp),
            "Away_Over_4.5": 1 - poisson.cdf(4, away_exp),
            "Away_Under_4.5": poisson.cdf(4, away_exp),
        }

    def predict_cards(self, home_team, away_team, referee="Desconocido"):
        """Calcula promedio de tarjetas"""
        # Tarjetas específicas (Local recibiendo en casa + Visitante recibiendo fuera)
        _, cards_home = self._obtener_promedios_especificos(home_team, es_local=True)
        _, cards_away = self._obtener_promedios_especificos(away_team, es_local=False)

        base_cards = cards_home + cards_away

        # Factor H2H de fricción (Ponderación del 25%)
        _, h2h_cards = self._obtener_h2h(home_team, away_team)
        if h2h_cards is not None:
            expected_base_cards = (base_cards * 0.75) + (h2h_cards * 0.25)
        else:
            expected_base_cards = base_cards

        # Factor Árbitro multiplicador
        bias = self.ref_bias.get(referee, 1.0)
        final_expected_cards = expected_base_cards * bias

        return {
            "expected_total": final_expected_cards,
            "Over 4.5": 1 - poisson.cdf(4, final_expected_cards),
            "Under 4.5": poisson.cdf(4, final_expected_cards),
        }


# ==========================================
# 4. PIPELINE DE EJECUCIoN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    # --- FECHA QUE QUEREMOS PREDECIR ---
    FECHA_OBJETIVO = datetime.today().strftime("%Y-%m-%d")

    print("--- INICIANDO SISTEMA DE PREDICCION LIGA MX ---")

    # 1. Preparar datos historicos
    fetcher = LigaMXDataFetcher(api_key=API_KEY)

    # Si es la primera vez que se ejecuta, descargara datos. Si ya hay archivo, lo lee rapido.
    # df_historico = fetcher.descargar_historico(seasons=[2024, 2025])
    # Alimenta el CSV con hasta 40 partidos nuevos por ejecucion para cuidar tu API
    df_historico = fetcher.actualizar_historico(seasons=[2022], limite_descargas=0)

    if df_historico.empty:
        print(
            "\nERROR: No hay datos historicos disponibles (limite diario probablemente se agoto)."
        )
        print(
            "El programa se detendra. Intenta mañana cuando se renueven tus peticiones de la API."
        )

        sys.exit()

    # Unificar identidad histórica antes de entrenar los modelos.
    df_historico = normalize_history_teams(df_historico)

    # 2. Entrenar Modelos
    print("Entrenando modelos de probabilidad (Dixon-Coles, Corners, Tarjetas)...")
    dc_model = []
    spec_model = []
    # dc_model = DixonColesModel()
    # dc_model.fit(df_historico)

    # spec_model = SpecialMarketsModel()
    # spec_model.fit(df_historico)

    # 3. Buscar partidos de la fecha objetivo
    # partidos_hoy = fetcher.obtener_partidos_por_fecha(FECHA_OBJETIVO)

    # AGREGA ESTO PARA FORZAR EL PARTIDO:
    partidos_hoy = [
        # {
        #     "home_team": "Necaxa",
        #     "away_team": "Cruz Azul",
        #     "referee": "I. Lopez",
        # }
        # {
        #     "home_team": "Club Tijuana",
        #     "away_team": "U.N.A.M. - Pumas",
        #     "referee": "C. Ramos",
        # }
    ]

    # (Para asegurar que la prueba funcione aunque la API aun no tenga partidos en 2026)
    # if not partidos_hoy:
    #     print(f"\n⚠️ La API no devolvio partidos para el {FECHA_OBJETIVO}.")
    #     print(
    #         "Cargando el partido simulado solicitado: Necaxa vs Leon para demostracion..."
    #     )
    #     partidos_hoy = [
    #         {
    #             "home_team": "Club Necaxa",
    #             "away_team": "Club Leon",
    #             "referee": "M. Ortiz",
    #         }
    #     ]

    # Si no hay partidos, detenemos el programa educadamente
    if not partidos_hoy:
        print(
            f"\nNo hay partidos programados en la Liga MX para la fecha: {FECHA_OBJETIVO}."
        )
    else:
        print(
            f"\nSe encontraron {len(partidos_hoy)} partidos para el {FECHA_OBJETIVO}."
        )
        # Predecir cada partido encontrado
        for partido in partidos_hoy:
            local = partido["home_team"]
            visitante = partido["away_team"]
            arbitro = partido["referee"]

            local_modelo = normalize_team_name(local)
            visitante_modelo = normalize_team_name(visitante)

            print("\n" + "═" * 50)
            print(f"PREDICCION: {local} vs {visitante}")
            print(f"Arbitro Asignado: {arbitro}")

            # --- IMPRIMIR H2H ---
            # Asumiendo que tu variable con el historial se llama df_historico
            print("\n[HISTORIAL DIRECTO]")
            print(analizar_h2h(df_historico, local_modelo, visitante_modelo))
            print("═" * 50)

            goles = dc_model.predict_match(local_modelo, visitante_modelo)
            corners = spec_model.predict_corners(local_modelo, visitante_modelo)
            cards = spec_model.predict_cards(
                local_modelo, visitante_modelo, referee=arbitro
            )

            # --- IMPRIMIR TOP 5 MARCADORES ---
            print("[TOP 5 MARCADORES MAS PROBABLES]")
            for marcador, prob in goles["Top_Scores"].items():
                print(f"   Marcador {marcador}: {prob*100:.1f}%")
            print("═" * 35)

            print("\n[GOLES Y RESULTADO]")
            print(
                f"   Goles Esperados (xG) -> {local}: {goles['expected_goals_home']:.2f} | {visitante}: {goles['expected_goals_away']:.2f}"
            )

            print(f"\n   Prob. Victoria {local}: {goles['1X2']['Home']*100:.1f}%")
            print(f"   Prob. Empate:         {goles['1X2']['Draw']*100:.1f}%")
            print(f"   Prob. Victoria {visitante}: {goles['1X2']['Away']*100:.1f}%")
            print(f"   Ambos Anotan (Si):    {goles['BTTS']['Yes']*100:.1f}%")
            print(
                f"   Mas de 2.5 Goles:     {goles['Over_Under']['Over 2.5']*100:.1f}%"
            )
            print(
                f"   Menos de 2.5 Goles:   {goles['Over_Under']['Under 2.5']*100:.1f}%"
            )

            print("\n[TIROS DE ESQUINA]")
            print(f"   Totales Esperados:      {corners['expected_total']:.1f}")
            print(f"   Esperados 1ª Mitad:     {corners['expected_1H']:.1f}")
            print(f"   Prob. > 9.5 Corners:    {corners['Over 9.5']*100:.1f}%")
            print(f"   Prob. < 9.5 Corners:    {corners['Under 9.5']*100:.1f}%")
            print(f"   Prob. > 4.5 Corners 1T: {corners['Over 4.5 1H']*100:.1f}%")

            print(f"\n{local} (Local):")
            print(f"   Córners Esperados:   {corners['expected_home']:.1f}")
            print(f"   Prob. > 4.5 Córners: {corners['Home_Over_4.5']*100:.1f}%")
            print(f"   Prob. < 4.5 Córners: {corners['Home_Under_4.5']*100:.1f}%")

            print(f"\n{visitante} (Visitante):")
            print(f"   Córners Esperados:   {corners['expected_away']:.1f}")
            print(f"   Prob. > 3.5 Córners: {corners['Away_Over_3.5']*100:.1f}%")
            print(f"   Prob. < 3.5 Córners: {corners['Away_Under_3.5']*100:.1f}%")

            print("\n[TARJETAS]")
            print(
                f"   Tarjetas Esperadas (Ajustadas por {arbitro}): {cards['expected_total']:.1f}"
            )
            print(f"   Prob. > 4.5 Tarjetas: {cards['Over 4.5']*100:.1f}%")
            print(f"   Prob. < 4.5 Tarjetas: {cards['Under 4.5']*100:.1f}%")
            print("═" * 50)

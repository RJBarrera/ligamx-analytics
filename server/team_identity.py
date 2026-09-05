"""Identidad canónica de equipos para MatchLab."""

import unicodedata

# ============================================================
# IDENTIDAD ACTUAL DE EQUIPOS
# ============================================================
#
# El CSV histórico puede conservar nombres anteriores.
# MatchLab los unifica en memoria bajo el nombre actual.
#
# Mazatlán -> Atlante
# Atlante  -> Atlante
# ============================================================

TEAM_CANONICAL_NAMES = {
    "mazatlan": "Atlante",
    "atlante": "Atlante",
}


def _normalize_key(value):
    """Normaliza un nombre para buscarlo en el mapa de identidades."""

    if value is None:
        return ""

    text = str(value).strip()

    text = unicodedata.normalize("NFD", text)
    text = "".join(
        character for character in text if unicodedata.category(character) != "Mn"
    )

    return text.casefold()


def normalize_team_name(team_name):
    """Devuelve el nombre canónico/actual del equipo."""

    if team_name is None:
        return team_name

    clean_name = str(team_name).strip()

    if not clean_name:
        return clean_name

    key = _normalize_key(clean_name)

    return TEAM_CANONICAL_NAMES.get(key, clean_name)


def normalize_history_teams(df):
    """Normaliza local/visitante en una copia del DataFrame para el modelo."""

    normalized_df = df.copy()

    if "home_team" in normalized_df.columns:
        normalized_df["home_team"] = normalized_df["home_team"].apply(
            normalize_team_name
        )

    if "away_team" in normalized_df.columns:
        normalized_df["away_team"] = normalized_df["away_team"].apply(
            normalize_team_name
        )

    return normalized_df

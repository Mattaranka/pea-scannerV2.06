"""
Détection des points de swing (swing high / swing low) et calcul des niveaux
de retracement et d'extension de Fibonacci, pour du swing trading (horizon
3-15 jours). Volontairement PAS basé sur le plus haut/bas 52 semaines par
défaut (trop large pour ce type d'horizon) - voir select_fibonacci_range().
"""

import pandas as pd

from src import config


def find_swing_points(df: pd.DataFrame, n: int = 5) -> tuple[list, list]:
    """
    Repère les swing highs et swing lows : un jour dont le High (resp. Low)
    domine (resp. est dominé par) les `n` jours précédents ET les `n` jours
    suivants.

    Retourne (swing_highs, swing_lows), chacun une liste de tuples
    (date, prix) triée par date.
    """
    highs, lows = [], []
    high_vals, low_vals = df["High"].values, df["Low"].values
    index = df.index

    for i in range(n, len(df) - n):
        fenetre_high = high_vals[i - n:i + n + 1]
        if high_vals[i] == fenetre_high.max() and high_vals[i] > 0:
            if (high_vals[i] >= high_vals[i - n:i]).all() and (high_vals[i] >= high_vals[i + 1:i + n + 1]).all():
                highs.append((index[i], float(high_vals[i])))

        fenetre_low = low_vals[i - n:i + n + 1]
        if low_vals[i] == fenetre_low.min() and low_vals[i] > 0:
            if (low_vals[i] <= low_vals[i - n:i]).all() and (low_vals[i] <= low_vals[i + 1:i + n + 1]).all():
                lows.append((index[i], float(low_vals[i])))

    return highs, lows


def _determine_trend(df: pd.DataFrame) -> str:
    """Tendance simple basée sur la position du prix par rapport aux EMA9/EMA20."""
    curr = df.iloc[-1]
    if curr["Close"] > curr["EMA_20"] and curr["EMA_9"] > curr["EMA_20"]:
        return "bullish"
    return "bearish"


def select_fibonacci_range(df: pd.DataFrame, method: str = "recent") -> dict:
    """
    Détermine le swing_high et le swing_low à utiliser pour le calcul des
    niveaux de Fibonacci, selon la méthode choisie :

    - "recent" (Option A, recommandée pour le swing trading) : dernier
      mouvement directionnel significatif, fenêtre de recherche 60 jours.
    - "medium" (Option B, une des 3 échelles du multi-timeframe) : fenêtre
      de recherche 120 jours.
    - "52w" (Option C, position trading long terme) : plus haut/plus bas
      des 52 dernières semaines, sans détection de swing fine.

    Retourne un dict avec swing_high, swing_high_date, swing_low,
    swing_low_date, trend.
    """
    trend = _determine_trend(df)

    if method == "52w":
        fenetre = df.tail(config.HIGH_LOW_52W_WINDOW)
        swing_high_date, swing_high = fenetre["High"].idxmax(), float(fenetre["High"].max())
        swing_low_date, swing_low = fenetre["Low"].idxmin(), float(fenetre["Low"].min())
        return {
            "swing_high": swing_high, "swing_high_date": swing_high_date,
            "swing_low": swing_low, "swing_low_date": swing_low_date,
            "trend": trend,
        }

    lookback = config.FIB_RECENT_WINDOW if method == "recent" else config.FIB_MEDIUM_WINDOW
    fenetre = df.tail(lookback)
    highs, lows = find_swing_points(fenetre, n=config.SWING_N)

    if trend == "bullish":
        # On choisit d'abord le sommet du mouvement (swing high le plus haut récent),
        # puis le creux qui précède ce sommet (début du mouvement haussier).
        if highs:
            swing_high_date, swing_high = max(highs, key=lambda x: x[1])
        else:
            swing_high_date, swing_high = fenetre["High"].idxmax(), float(fenetre["High"].max())

        lows_avant = [l for l in lows if l[0] < swing_high_date]
        candidats = lows_avant or lows
        if candidats:
            swing_low_date, swing_low = min(candidats, key=lambda x: x[1])
        else:
            swing_low_date, swing_low = fenetre["Low"].idxmin(), float(fenetre["Low"].min())
    else:
        # Tendance baissière : on choisit d'abord le creux du mouvement, puis le
        # sommet qui le précède (début du mouvement baissier).
        if lows:
            swing_low_date, swing_low = min(lows, key=lambda x: x[1])
        else:
            swing_low_date, swing_low = fenetre["Low"].idxmin(), float(fenetre["Low"].min())

        highs_avant = [h for h in highs if h[0] < swing_low_date]
        candidats = highs_avant or highs
        if candidats:
            swing_high_date, swing_high = max(candidats, key=lambda x: x[1])
        else:
            swing_high_date, swing_high = fenetre["High"].idxmax(), float(fenetre["High"].max())

    return {
        "swing_high": swing_high, "swing_high_date": swing_high_date,
        "swing_low": swing_low, "swing_low_date": swing_low_date,
        "trend": trend,
    }


def calculate_fibonacci_levels(swing_high: float, swing_low: float, trend: str = "bullish") -> dict:
    """
    Calcule les niveaux de retracement (et d'extension si tendance haussière)
    à partir d'un swing_high et d'un swing_low donnés.
    """
    diff = swing_high - swing_low

    if trend == "bullish":
        levels = {
            "0%": swing_high,
            "23.6%": swing_high - 0.236 * diff,
            "38.2%": swing_high - 0.382 * diff,
            "50%": swing_high - 0.500 * diff,
            "61.8%": swing_high - 0.618 * diff,
            "78.6%": swing_high - 0.786 * diff,
            "100%": swing_low,
            "127.2%": swing_high + 0.272 * diff,
            "161.8%": swing_high + 0.618 * diff,
            "200%": swing_high + 1.000 * diff,
        }
    else:
        levels = {
            "0%": swing_low,
            "23.6%": swing_low + 0.236 * diff,
            "38.2%": swing_low + 0.382 * diff,
            "50%": swing_low + 0.500 * diff,
            "61.8%": swing_low + 0.618 * diff,
            "78.6%": swing_low + 0.786 * diff,
            "100%": swing_high,
        }

    levels["swing_high"] = swing_high
    levels["swing_low"] = swing_low
    levels["trend"] = trend
    return levels


# Couleurs suggérées pour l'affichage des niveaux sur le graphique.
FIB_LEVEL_COLORS = {
    "0%": "#888888",
    "23.6%": "#7fb3ff",
    "38.2%": "#3d7dd6",
    "50%": "#9b59b6",
    "61.8%": "#e67e22",   # golden ratio - niveau le plus important
    "78.6%": "#c0392b",
    "100%": "#888888",
    "127.2%": "#2ecc71",
    "161.8%": "#27ae60",
    "200%": "#1e8449",
}


def current_price_zone(current_price: float, levels: dict) -> str | None:
    """Indique si le prix actuel se trouve dans la zone d'achat 38.2%-61.8%."""
    bas, haut = sorted([levels["38.2%"], levels["61.8%"]])
    if bas <= current_price <= haut:
        return "ZONE D'ACHAT FIBONACCI (38.2%-61.8%)"
    return None

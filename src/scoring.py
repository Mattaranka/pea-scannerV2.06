"""
Système de scoring swing trading (achat), noté sur 100, réparti en 7 critères
pondérés : structure EMA (25), RSI (20), volume (15), ATR (10), MACD (10),
structure de prix (10), contexte de marché (10).

Chaque fonction score_xxx() implémente exactement le barème fourni en
spécification et retourne un entier (le score du critère). La fonction
compute_swing_score() orchestre l'ensemble et retourne le détail complet.

Le contexte de marché s'appuie sur un indice de référence (CAC 40 par
défaut, voir config.MARKET_INDEX_TICKER), téléchargé une seule fois par
scan (pas par action) car il est commun à toutes les actions du jour.
"""

import pandas as pd

from src import config


def _is_rising(series: pd.Series, n: int) -> bool:
    """True si les `n` dernières valeurs de la série sont strictement croissantes jour après jour."""
    tail = series.tail(n)
    if len(tail) < n:
        return False
    return bool((tail.diff().dropna() > 0).all())


def _is_falling(series: pd.Series, n: int) -> bool:
    """True si les `n` dernières valeurs de la série sont strictement décroissantes jour après jour."""
    tail = series.tail(n)
    if len(tail) < n:
        return False
    return bool((tail.diff().dropna() < 0).all())


def _check_bullish_rsi_divergence(df: pd.DataFrame, rsi_col: str, lookback: int = 10) -> bool:
    """
    Divergence haussière : sur les `lookback` derniers jours (hors aujourd'hui),
    si le plus bas du prix précédent est supérieur au plus bas d'aujourd'hui,
    mais que le RSI à ce moment-là était inférieur au RSI d'aujourd'hui.
    """
    if len(df) < lookback + 2:
        return False
    fenetre = df.iloc[-(lookback + 1):-1]
    if fenetre.empty:
        return False
    idx_min = fenetre["Low"].idxmin()
    low_precedent = fenetre.loc[idx_min, "Low"]
    rsi_precedent = fenetre.loc[idx_min, rsi_col]
    aujourdhui = df.iloc[-1]
    if pd.isna(rsi_precedent) or pd.isna(aujourdhui[rsi_col]):
        return False
    return bool(aujourdhui["Low"] < low_precedent and aujourdhui[rsi_col] > rsi_precedent)


# --- Critère 1 : Structure des EMA (25 pts) ---------------------------------------

def score_ema_structure(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 3
    curr, prev = df.iloc[-1], df.iloc[-2]
    ema9, ema20, ema200 = curr["EMA_9"], curr["EMA_20"], curr["EMA_200"]
    prix = curr["Close"]

    if pd.isna(ema9) or pd.isna(ema20) or pd.isna(ema200):
        return 3

    croise_hausse = prev["EMA_9"] < prev["EMA_20"] and ema9 > ema20

    if ema9 > ema20 and ema20 > ema200:
        score = 25
    elif ema9 > ema20 and prix > ema200:
        score = 20
    elif croise_hausse:
        score = 18
    elif prix > ema200 and ema9 < ema20:
        score = 12
    elif ema200 and abs(prix - ema200) / ema200 < 0.02:
        score = 8
    elif prix < ema200 and croise_hausse:
        score = 5
    elif ema9 < ema20 and ema20 < ema200:
        score = 0
    else:
        score = 3

    # Bonus pullback : tendance haussière alignée, mèche basse touchant l'EMA20, clôture au-dessus.
    if ema9 > ema20 > ema200 and curr["Low"] <= ema20 and prix > ema20:
        score = min(score + 3, 25)

    return score


# --- Critère 2 : RSI (20 pts) ------------------------------------------------------

def score_rsi(df: pd.DataFrame, rsi_period: int) -> int:
    rsi_col = f"RSI_{rsi_period}"
    rsi = df.iloc[-1][rsi_col]
    if pd.isna(rsi):
        return 0

    if 40 <= rsi <= 55:
        score = 20
    elif 55 < rsi <= 65:
        score = 17
    elif 30 <= rsi < 40:
        score = 15
    elif 65 < rsi <= 70:
        score = 10
    elif rsi < 30:
        score = 8
    elif 70 < rsi <= 80:
        score = 3
    else:  # rsi > 80
        score = 0

    if _check_bullish_rsi_divergence(df, rsi_col):
        score = min(score + 3, 20)

    return score


# --- Critère 3 : Volume (15 pts) --------------------------------------------------

def score_volume(df: pd.DataFrame, volume_ratio: float | None) -> int:
    if volume_ratio is None or len(df) < 3:
        return 4

    curr = df.iloc[-1]
    bougie_haussiere = curr["Close"] > curr["Open"]
    volume_hausse_3j = _is_rising(df["Volume"], 3)
    prix_hausse_3j = _is_rising(df["Close"], 3)
    prix_baisse_3j = _is_falling(df["Close"], 3)

    if volume_ratio > 1.5 and bougie_haussiere:
        return 15
    if volume_ratio > 1.2 and bougie_haussiere:
        return 12
    if volume_hausse_3j and prix_hausse_3j:
        return 10
    if volume_ratio < 0.8 and prix_baisse_3j:
        return 8
    if 0.8 <= volume_ratio <= 1.2:
        return 6
    if volume_ratio > 1.2 and not bougie_haussiere:
        return 2
    if volume_ratio < 0.5 and bougie_haussiere:
        return 0
    return 4


# --- Critère 4 : ATR (10 pts) ------------------------------------------------------

def score_atr(atr_ratio: float | None) -> int:
    if atr_ratio is None:
        return 5

    if 1.10 <= atr_ratio <= 1.30:
        return 10
    if atr_ratio < 0.80:
        return 8
    if 0.80 <= atr_ratio <= 1.10:
        return 7
    if 1.30 < atr_ratio <= 1.50:
        return 5
    if atr_ratio > 2.0:
        return 2
    if atr_ratio > 1.50:
        return 3
    return 5


# --- Critère 5 : MACD (10 pts) -----------------------------------------------------

def score_macd(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 3
    curr, prev = df.iloc[-1], df.iloc[-2]
    macd, signal, hist = curr["MACD"], curr["MACD_signal"], curr["MACD_hist"]
    hist_prev = prev["MACD_hist"]

    if pd.isna(macd) or pd.isna(signal) or pd.isna(hist_prev):
        return 3

    croise_hausse = prev["MACD"] <= prev["MACD_signal"] and macd > signal
    hist_en_hausse = hist > hist_prev

    if croise_hausse and hist_en_hausse:
        return 10
    if macd > signal and hist > 0 and hist > hist_prev:
        return 8
    if macd < signal and hist_en_hausse:
        return 6
    if macd > signal and hist > 0 and hist < hist_prev:
        return 4
    if macd < signal and hist < hist_prev:
        return 3
    if macd < signal and hist < 0 and hist < hist_prev:
        return 0
    return 3


# --- Critère 6 : Structure de prix - Support/Résistance (10 pts) ------------------

def score_price_structure(df: pd.DataFrame, volume_ratio: float | None) -> int:
    curr = df.iloc[-1]
    high20_prior, low20_prior = curr.get("high_20d_prior"), curr.get("low_20d_prior")
    high20, low20 = curr.get("high_20j"), curr.get("low_20j")
    close = curr["Close"]
    bougie_haussiere = close > curr["Open"]
    tendance_haussiere = not pd.isna(curr["EMA_9"]) and not pd.isna(curr["EMA_20"]) and curr["EMA_9"] > curr["EMA_20"]

    if pd.isna(high20) or pd.isna(low20) or high20 == low20:
        return 4

    position = (close - low20) / (high20 - low20)
    breakout_haussier = not pd.isna(high20_prior) and close > high20_prior
    breakdown = not pd.isna(low20_prior) and close < low20_prior
    pres_du_bas = position <= 0.05

    if breakout_haussier and volume_ratio is not None and volume_ratio > 1.2:
        return 10
    if pres_du_bas and bougie_haussiere:
        return 9
    if position > 0.6 and tendance_haussiere:
        return 7
    if 0.4 <= position <= 0.6:
        return 4
    if 0.9 <= position <= 1.0 and not breakout_haussier:
        return 2
    if breakdown:
        return 0
    return 4


# --- Critère 7 : Contexte de marché (10 pts) --------------------------------------

def fetch_market_context_df():
    """
    Télécharge et prépare les données de l'indice de référence (une seule
    fois par scan, partagé par toutes les actions). Retourne None en cas
    d'échec (le critère "contexte de marché" utilisera alors un score neutre).
    """
    from src.data_fetcher import fetch_history  # import local pour éviter une dépendance circulaire

    df = fetch_history(config.MARKET_INDEX_TICKER, config.HISTORY_PERIOD, config.HISTORY_INTERVAL)
    if df is None or len(df) < config.MARKET_EMA_LONG:
        return None

    from src.indicators import add_ema
    df = add_ema(df, config.MARKET_EMA_SHORT)
    df = add_ema(df, config.MARKET_EMA_MID)
    df = add_ema(df, config.MARKET_EMA_LONG)
    return df


def score_market_context(index_df) -> int:
    if index_df is None or index_df.empty:
        return 4  # cas par défaut si l'indice n'a pas pu être téléchargé

    curr = index_df.iloc[-1]
    prix = curr["Close"]
    ema20, ema50, ema200 = (
        curr[f"EMA_{config.MARKET_EMA_SHORT}"],
        curr[f"EMA_{config.MARKET_EMA_MID}"],
        curr[f"EMA_{config.MARKET_EMA_LONG}"],
    )

    if pd.isna(ema20) or pd.isna(ema50) or pd.isna(ema200):
        return 4

    if prix > ema20 and prix > ema50:
        return 10
    if prix > ema200 and (min(ema20, ema50) <= prix <= max(ema20, ema50)):
        return 7
    if min(ema50, ema200) <= prix <= max(ema50, ema200):
        return 5
    if prix < ema200 and prix > ema20:
        return 3
    if prix < ema20 and prix < ema50 and prix < ema200:
        return 0
    return 4


# --- Score total et interprétation -------------------------------------------------

def interpret_score(score_total: int) -> tuple[str, str, str]:
    """Retourne (signal, action recommandée, couleur) selon les seuils de config.SCORE_THRESHOLDS."""
    for seuil, signal, action, couleur in config.SCORE_THRESHOLDS:
        if score_total >= seuil:
            return signal, action, couleur
    return config.SCORE_THRESHOLDS[-1][1], config.SCORE_THRESHOLDS[-1][2], config.SCORE_THRESHOLDS[-1][3]


def compute_swing_score(df: pd.DataFrame, volume_ratio: float | None, atr_ratio: float | None, index_df) -> dict:
    """
    Calcule le score complet (7 critères + total + interprétation) pour une
    action donnée. `df` doit déjà contenir toutes les colonnes d'indicateurs
    (EMA9/20/200, RSI, ATR, MACD, high/low 20j...). `index_df` est le
    DataFrame de l'indice de référence, calculé une seule fois par scan.
    """
    s_ema = score_ema_structure(df)
    s_rsi = score_rsi(df, config.RSI_PERIOD)
    s_volume = score_volume(df, volume_ratio)
    s_atr = score_atr(atr_ratio)
    s_macd = score_macd(df)
    s_structure = score_price_structure(df, volume_ratio)
    s_marche = score_market_context(index_df)

    total = s_ema + s_rsi + s_volume + s_atr + s_macd + s_structure + s_marche
    signal, action, couleur = interpret_score(total)

    return {
        "score_ema": s_ema,
        "score_rsi_crit": s_rsi,
        "score_volume_crit": s_volume,
        "score_atr_crit": s_atr,
        "score_macd_crit": s_macd,
        "score_structure": s_structure,
        "score_marche": s_marche,
        "score_swing_total": total,
        "signal_swing": signal,
        "action_swing": action,
        "couleur_swing": couleur,
    }

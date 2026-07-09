"""
Orchestration du scan : pour chaque action de l'univers PEA, télécharge
l'historique, calcule les indicateurs, détecte les signaux, et construit
un tableau de résultats consolidé (incluant le score swing trading 0-100).
"""

import pandas as pd

from src import config
from src.data_fetcher import fetch_history
from src.indicators import (
    add_ema,
    detect_ema_crossover,
    add_rsi,
    add_volume_stats,
    add_range_stats,
    add_high_low_window,
    add_breakout_levels,
    detect_breakout,
    add_atr,
    add_atr_avg,
    add_macd,
    days_since_ema_crossover,
    days_since_breakout,
)
from src.scoring import compute_swing_score, fetch_market_context_df


def _safe_round(value, ndigits=3):
    """Retourne None si la valeur est NaN/absente (ex. historique trop court), sinon arrondit."""
    return None if pd.isna(value) else round(float(value), ndigits)


def scan_one_stock(stock: dict, index_df) -> dict | None:
    """Analyse une action et retourne une ligne de résultat, ou None si échec."""
    ticker = stock["ticker"]
    df = fetch_history(ticker, config.HISTORY_PERIOD, config.HISTORY_INTERVAL)

    # Minimum vital pour calculer les indicateurs de base (EMA9/20, RSI...).
    # L'EMA200, le 52 semaines, etc. peuvent rester incomplets (None) si
    # l'action est cotée depuis moins longtemps que la fenêtre demandée.
    if df is None or len(df) < config.EMA_LONG:
        return None

    df = add_ema(df, config.EMA_SHORT)
    df = add_ema(df, config.EMA_LONG)
    df = add_ema(df, config.EMA_TREND)
    df = add_rsi(df, config.RSI_PERIOD)
    df = add_volume_stats(df, config.VOLUME_AVG_PERIOD)
    df = add_range_stats(df, config.RANGE_PERIOD)
    df = add_high_low_window(df, config.HIGH_LOW_52W_WINDOW, "52s")
    df = add_high_low_window(df, config.BREAKOUT_PERIOD, "20j")
    df = add_breakout_levels(df, config.BREAKOUT_PERIOD)
    df = add_atr(df, config.ATR_PERIOD)
    df = add_atr_avg(df, config.ATR_PERIOD, config.ATR_AVG_PERIOD)
    df = add_macd(df, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)

    crossover = detect_ema_crossover(df, config.EMA_SHORT, config.EMA_LONG)
    cassure = detect_breakout(df, config.BREAKOUT_PERIOD)
    jours_depuis_croisement = days_since_ema_crossover(df, config.EMA_SHORT, config.EMA_LONG, config.SIGNAL_LOOKBACK_DAYS)
    jours_depuis_cassure = days_since_breakout(df, config.BREAKOUT_PERIOD, config.SIGNAL_LOOKBACK_DAYS)

    last = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"] if len(df) >= 2 else last["Close"]
    variation_pct = ((last["Close"] - prev_close) / prev_close) * 100 if prev_close else 0.0

    ema9, ema20, ema200 = last[f"EMA_{config.EMA_SHORT}"], last[f"EMA_{config.EMA_LONG}"], last[f"EMA_{config.EMA_TREND}"]

    volume_avg = last[f"volume_avg_{config.VOLUME_AVG_PERIOD}"]
    volume_ratio = (last["Volume"] / volume_avg) if volume_avg and not pd.isna(volume_avg) and volume_avg > 0 else None
    volume_confirme = bool(volume_ratio is not None and volume_ratio >= config.VOLUME_SPIKE_RATIO)

    rsi = last[f"RSI_{config.RSI_PERIOD}"]
    atr = last[f"ATR_{config.ATR_PERIOD}"]
    atr_avg = last[f"ATR_{config.ATR_PERIOD}_avg_{config.ATR_AVG_PERIOD}"]
    atr_ratio = (atr / atr_avg) if atr_avg and not pd.isna(atr_avg) and atr_avg > 0 else None

    score = compute_swing_score(
        df,
        volume_ratio=volume_ratio,
        atr_ratio=atr_ratio,
        index_df=index_df,
    )

    # Stop-loss / objectifs suggérés à partir de l'ATR (setup acheteur, le PEA
    # ne permettant pas la vente à découvert). Indicatif uniquement : à
    # ajuster selon le contexte (supports/résistances, actualité du titre...).
    stop_suggere = _safe_round(last["Close"] - config.ATR_STOP_MULTIPLIER * atr, 2) if not pd.isna(atr) else None
    objectif_suggere = _safe_round(last["Close"] + config.ATR_TARGET_MULTIPLIER * atr, 2) if not pd.isna(atr) else None

    return {
        "ticker": ticker,
        "nom": stock["nom"],
        "secteur": stock["secteur"],
        "dernier_cours": round(float(last["Close"]), 2),
        "variation_jour_pct": round(float(variation_pct), 2),
        "volume": int(last["Volume"]) if not pd.isna(last["Volume"]) else None,
        f"volume_moyen_{config.VOLUME_AVG_PERIOD}j": _safe_round(volume_avg, 0),
        "volume_ratio": _safe_round(volume_ratio, 2),
        f"ema_{config.EMA_SHORT}": _safe_round(ema9),
        f"ema_{config.EMA_LONG}": _safe_round(ema20),
        f"ema_{config.EMA_TREND}": _safe_round(ema200),
        f"rsi_{config.RSI_PERIOD}": _safe_round(rsi, 1),
        f"atr_{config.ATR_PERIOD}": _safe_round(atr, 3),
        "atr_ratio": _safe_round(atr_ratio, 2),
        f"variation_moyenne_{config.RANGE_PERIOD}j_pct": _safe_round(last[f"range_avg_{config.RANGE_PERIOD}"], 2),
        "plus_haut_52s": _safe_round(last["high_52s"], 2),
        "plus_bas_52s": _safe_round(last["low_52s"], 2),
        "plus_haut_20j": _safe_round(last["high_20j"], 2),
        "plus_bas_20j": _safe_round(last["low_20j"], 2),
        "croisement": crossover,                       # "haussier" / "baissier" / None
        "jours_depuis_croisement": jours_depuis_croisement,
        "cassure_20j": cassure,                        # "haussière" / "baissière" / None
        "jours_depuis_cassure": jours_depuis_cassure,
        "volume_confirme": volume_confirme,             # confirmation par un volume ≥ seuil
        # --- Score swing trading 0-100 (voir src/scoring.py) ---
        "score_ema": score["score_ema"],
        "score_rsi_crit": score["score_rsi_crit"],
        "score_volume_crit": score["score_volume_crit"],
        "score_atr_crit": score["score_atr_crit"],
        "score_macd_crit": score["score_macd_crit"],
        "score_structure": score["score_structure"],
        "score_marche": score["score_marche"],
        "score_swing_total": score["score_swing_total"],
        "signal_swing": score["signal_swing"],
        "action_swing": score["action_swing"],
        "couleur_swing": score["couleur_swing"],
        "stop_suggere": stop_suggere,
        "objectif_suggere": objectif_suggere,
        "date": last.name.strftime("%Y-%m-%d"),
    }


def run_scan(stocks: list[dict] | None = None) -> pd.DataFrame:
    """Exécute le scan complet sur l'univers d'actions et retourne un DataFrame."""
    stocks = stocks if stocks is not None else config.PEA_STOCKS
    results = []

    # Le contexte de marché (indice de référence) est commun à toutes les
    # actions du scan : on ne le télécharge et calcule qu'une seule fois.
    print(f"[scanner] Téléchargement de l'indice de référence ({config.MARKET_INDEX_TICKER})...")
    index_df = fetch_market_context_df()
    if index_df is None:
        print("[scanner] Indice de référence indisponible, le critère 'contexte de marché' utilisera un score neutre.")

    for stock in stocks:
        row = scan_one_stock(stock, index_df)
        if row is not None:
            results.append(row)
        else:
            print(f"[scanner] Ignoré (données indisponibles) : {stock['ticker']}")

    return pd.DataFrame(results)

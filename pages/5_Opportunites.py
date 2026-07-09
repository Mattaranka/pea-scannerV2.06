"""
Page dédiée : setups d'achat les plus intéressants pour du swing trading,
classés par le score swing trading (0-100, voir src/scoring.py) réparti en
7 critères : structure EMA, RSI, volume, ATR, MACD, structure de prix,
contexte de marché.

Le PEA ne permettant pas la vente à découvert, cette page se concentre sur
les setups acheteurs. Les signaux baissiers restent visibles sur les pages
dédiées (Croisements EMA, Cassures) comme signal de prudence / sortie sur
une position déjà ouverte.
"""

import os

import pandas as pd
import streamlit as st

from src import config
from src.chart import render_stock_chart

st.set_page_config(page_title="Opportunités - Scanner PEA", page_icon="🎯", layout="wide")
st.title("🎯 Opportunités de swing trading")
st.caption("Score swing trading sur 100 : structure EMA (25) + RSI (20) + volume (15) + ATR (10) "
           "+ MACD (10) + structure de prix (10) + contexte de marché (10).")

if not os.path.exists(config.SCAN_RESULTS_FILE):
    st.warning("Aucune donnée disponible pour le moment.")
    st.stop()


@st.cache_data(ttl=300)
def load_data(mtime: float) -> pd.DataFrame:
    return pd.read_csv(config.SCAN_RESULTS_FILE)


mtime = os.path.getmtime(config.SCAN_RESULTS_FILE)
df = load_data(mtime)

COULEUR_EMOJI = {
    "vert": "🟢", "vert clair": "🟢", "jaune": "🟡", "orange": "🟠", "rouge": "🔴",
}

seuil = st.slider("Score minimum affiché (sur 100)", min_value=0, max_value=100, value=config.SCORE_DISPLAY_MIN)

df_opp = df[df["score_swing_total"] >= seuil].copy().sort_values("score_swing_total", ascending=False)

if df_opp.empty:
    st.info("Aucune action n'atteint ce score aujourd'hui. Essaie d'abaisser le seuil.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Opportunités trouvées", len(df_opp))
col2.metric("Score moyen", round(df_opp["score_swing_total"].mean(), 1))
col3.metric("Meilleur score", int(df_opp["score_swing_total"].max()))

st.divider()

df_affiche = df_opp.copy()
df_affiche["Signal"] = [f"{COULEUR_EMOJI.get(c, '')} {s}" for s, c in zip(df_affiche["signal_swing"], df_affiche["couleur_swing"])]

st.dataframe(
    df_affiche[[
        "ticker", "nom", "secteur", "dernier_cours", "score_swing_total", "Signal",
        "score_ema", "score_rsi_crit", "score_volume_crit", "score_atr_crit",
        "score_macd_crit", "score_structure", "score_marche",
        "stop_suggere", "objectif_suggere",
    ]].rename(columns={
        "ticker": "Ticker",
        "nom": "Nom",
        "secteur": "Secteur",
        "dernier_cours": "Dernier cours (€)",
        "score_swing_total": "Score /100",
        "score_ema": "EMA /25",
        "score_rsi_crit": "RSI /20",
        "score_volume_crit": "Volume /15",
        "score_atr_crit": "ATR /10",
        "score_macd_crit": "MACD /10",
        "score_structure": "Structure /10",
        "score_marche": "Marché /10",
        "stop_suggere": "Stop suggéré (€)",
        "objectif_suggere": "Objectif suggéré (€)",
    }),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"⚠️ Stop et objectif sont calculés à partir de l'ATR{config.ATR_PERIOD} "
    f"(stop = cours − {config.ATR_STOP_MULTIPLIER}×ATR, objectif = cours + {config.ATR_TARGET_MULTIPLIER}×ATR). "
    "Ce sont des repères indicatifs basés sur la volatilité récente, pas une recommandation "
    "d'investissement — à ajuster selon le contexte du titre (supports/résistances, actualité)."
)

render_stock_chart(df_opp["ticker"].tolist(), key="opportunites")

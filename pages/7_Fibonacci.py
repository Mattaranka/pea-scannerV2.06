"""
Page dédiée : niveaux de retracement et d'extension de Fibonacci, calculés
à partir de swings détectés automatiquement (pas du 52 semaines par défaut,
trop large pour du swing trading) et affichés en lignes horizontales sur le
graphique.
"""

import os

import pandas as pd
import streamlit as st

from src import config
from src.chart import build_figure, fetch_and_prepare_chart_data, PERIODES_AFFICHAGE
from src.fibonacci import select_fibonacci_range, calculate_fibonacci_levels, current_price_zone

st.set_page_config(page_title="Fibonacci - Scanner PEA", page_icon="🌀", layout="wide")
st.title("🌀 Niveaux de Fibonacci")
st.caption(
    "Retracements et extensions calculés sur un swing récent (pas sur le 52 semaines, "
    "trop large pour un horizon de swing trading de quelques jours à quelques semaines)."
)

if not os.path.exists(config.SCAN_RESULTS_FILE):
    st.warning("Aucune donnée disponible pour le moment.")
    st.stop()


@st.cache_data(ttl=300)
def load_data(mtime: float) -> pd.DataFrame:
    return pd.read_csv(config.SCAN_RESULTS_FILE)


mtime = os.path.getmtime(config.SCAN_RESULTS_FILE)
df = load_data(mtime)

ticker_choisi = st.selectbox("Choisir une action", sorted(df["ticker"].tolist()))

st.divider()

methode_label = st.radio(
    "Méthode de calcul",
    options=["Option A — Swing récent", "Option B — Multi-timeframe", "Option C — 52 semaines"],
    horizontal=True,
    help=(
        "Option A (recommandée pour le swing trading) : dernier mouvement significatif, "
        "fenêtre 20-60 jours. Option B : superpose court/moyen/long terme. "
        "Option C : 52 semaines, utile seulement pour un horizon > 1 mois."
    ),
)

hist = fetch_and_prepare_chart_data(ticker_choisi)
if hist is None:
    st.warning("Impossible de récupérer l'historique pour cette action.")
    st.stop()

periode_choisie = st.select_slider("Période affichée sur le graphique", options=list(PERIODES_AFFICHAGE.keys()), value="6 mois")
hist_affiche = hist.tail(PERIODES_AFFICHAGE[periode_choisie])
prix_actuel = hist.iloc[-1]["Close"]


def _afficher_niveaux(rng: dict, titre: str):
    niveaux = calculate_fibonacci_levels(rng["swing_high"], rng["swing_low"], rng["trend"])
    st.markdown(f"**{titre}** — tendance détectée : {'haussière 🟢' if rng['trend'] == 'bullish' else 'baissière 🔴'}")
    st.caption(
        f"Swing high : {rng['swing_high']:.2f}€ ({rng['swing_high_date'].strftime('%d/%m/%Y') if hasattr(rng['swing_high_date'], 'strftime') else rng['swing_high_date']}) "
        f"— Swing low : {rng['swing_low']:.2f}€ ({rng['swing_low_date'].strftime('%d/%m/%Y') if hasattr(rng['swing_low_date'], 'strftime') else rng['swing_low_date']})"
    )

    lignes = [{"Niveau": label, "Prix (€)": round(valeur, 2)}
              for label, valeur in niveaux.items() if label not in ("trend", "swing_high", "swing_low")]
    st.dataframe(pd.DataFrame(lignes), use_container_width=True, hide_index=True)

    zone = current_price_zone(prix_actuel, niveaux)
    if zone:
        st.success(f"Prix actuel ({prix_actuel:.2f}€) → {zone}")

    return niveaux


if methode_label.startswith("Option A"):
    rng = select_fibonacci_range(hist, method="recent")
    niveaux = _afficher_niveaux(rng, "Swing récent (20-60 jours)")
    fig = build_figure(hist_affiche, show_ema9=True, show_ema20=True, show_ema200=False,
                        show_volume=True, show_rsi=True, fib_levels=niveaux, ticker=ticker_choisi)
    st.plotly_chart(fig, use_container_width=True)

elif methode_label.startswith("Option B"):
    st.info("Trois échelles superposées : plus il y a de convergence entre les niveaux, plus la zone est significative.")
    rng_court = select_fibonacci_range(hist, method="recent")
    rng_moyen = select_fibonacci_range(hist, method="medium")
    rng_long = select_fibonacci_range(hist, method="52w")

    col1, col2, col3 = st.columns(3)
    with col1:
        niveaux_court = _afficher_niveaux(rng_court, "Court terme (20-60j)")
    with col2:
        niveaux_moyen = _afficher_niveaux(rng_moyen, "Moyen terme (60-120j)")
    with col3:
        niveaux_long = _afficher_niveaux(rng_long, "Long terme (52 semaines)")

    # Sur le graphique, on superpose uniquement le niveau court terme pour la
    # lisibilité (les 3 échelles en même temps rendraient le graphique illisible) ;
    # les tableaux ci-dessus permettent de comparer les 3 échelles en détail.
    fig = build_figure(hist_affiche, show_ema9=True, show_ema20=True, show_ema200=False,
                        show_volume=True, show_rsi=True, fib_levels=niveaux_court, ticker=ticker_choisi)
    st.plotly_chart(fig, use_container_width=True)

else:  # Option C — 52 semaines
    rng = select_fibonacci_range(hist, method="52w")
    niveaux = _afficher_niveaux(rng, "52 semaines (position trading long terme)")
    fig = build_figure(hist_affiche, show_ema9=True, show_ema20=True, show_ema200=True,
                        show_volume=True, show_rsi=True, fib_levels=niveaux, ticker=ticker_choisi)
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    "⚠️ Les niveaux de Fibonacci identifient des zones de support/résistance *potentielles*, "
    "pas des garanties : à combiner avec les autres indicateurs (RSI, volume, score swing) "
    "avant toute décision."
)

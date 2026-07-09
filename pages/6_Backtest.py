"""
Page dédiée : performance historique constatée après chaque type de signal,
calculée à partir des archives quotidiennes accumulées dans data/history/.
"""

import glob
import os

import streamlit as st

from src import config
from src.backtest import run_backtest

st.set_page_config(page_title="Backtest - Scanner PEA", page_icon="🧪", layout="wide")
st.title("🧪 Backtest des signaux")
st.caption(
    "Performance réelle constatée après chaque signal, mesurée sur les archives quotidiennes "
    "accumulées jour après jour dans data/history/ (aucun téléchargement supplémentaire nécessaire)."
)

nb_archives = len(glob.glob(os.path.join(config.HISTORY_DIR, "*.csv")))

SEUIL_FIABILITE = 20  # nombre de signaux en dessous duquel on affiche un avertissement

if nb_archives == 0:
    st.warning(
        "Aucune archive disponible pour le moment. Le backtesting a besoin d'au moins "
        "quelques semaines de scans quotidiens accumulés pour donner des résultats "
        "exploitables — reviens plus tard."
    )
    st.stop()

if nb_archives < 15:
    st.info(
        f"Seulement **{nb_archives} jour(s)** de scan archivé(s) pour l'instant. Les statistiques "
        "ci-dessous vont s'affiner automatiquement à chaque scan quotidien — à interpréter avec "
        "prudence tant que le nombre de signaux reste faible."
    )


@st.cache_data(ttl=3600)
def load_backtest(nb_fichiers: int):
    """Le paramètre nb_fichiers sert uniquement à invalider le cache quand de
    nouvelles archives apparaissent (une par jour)."""
    return run_backtest()


df_resultats = load_backtest(nb_archives)

if df_resultats.empty:
    st.info("Pas encore assez de données exploitables pour calculer des statistiques.")
    st.stop()

for horizon in config.BACKTEST_HORIZONS:
    st.subheader(f"Horizon : {horizon} jours de bourse après le signal")
    sous_df = df_resultats[df_resultats["horizon_j"] == horizon].drop(columns="horizon_j")

    st.dataframe(
        sous_df.rename(columns={
            "signal": "Signal",
            "nb_signaux": "Nb signaux observés",
            "taux_reussite_pct": "Taux de réussite (%)",
            "gain_moyen_pct": "Gain moyen (%)",
            "gain_median_pct": "Gain médian (%)",
        }),
        use_container_width=True,
        hide_index=True,
    )

    nb_signaux_faibles = sous_df[sous_df["nb_signaux"] < SEUIL_FIABILITE]
    if not nb_signaux_faibles.empty:
        st.caption(
            f"⚠️ Signal(aux) avec moins de {SEUIL_FIABILITE} occurrences à cet horizon : "
            f"{', '.join(nb_signaux_faibles['signal'].tolist())} — statistique peu fiable pour l'instant."
        )

st.divider()
st.caption(
    "Le taux de réussite indique la proportion de signaux suivis d'une performance positive à "
    "l'horizon donné. Ces chiffres reflètent le passé récent de ton univers d'actions suivi : ils "
    "n'offrent aucune garantie sur les performances futures et ne constituent pas un conseil "
    "d'investissement."
)

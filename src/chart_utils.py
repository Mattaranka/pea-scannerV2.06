"""
Composant graphique réutilisable : sélecteur d'action + graphique
(chandelles + EMA9/EMA20/EMA200) sur les cours bruts.

Centralisé ici pour que chaque page (Croisements, RSI, Volumes, Cassures,
Opportunités...) puisse l'afficher sans dupliquer le code de téléchargement
et de tracé.
"""

import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from src import config


def render_stock_chart(tickers: list[str], key_suffix: str) -> None:
    """
    Affiche un sélecteur d'action parmi `tickers`, puis le graphique
    correspondant. `key_suffix` doit être unique par page pour éviter les
    conflits de clé de widget Streamlit (ex. "rsi", "volumes"...).
    """
    if len(tickers) == 0:
        return

    st.subheader("Visualiser une action")
    ticker_choisi = st.selectbox(
        "Choisir une action pour afficher son graphique",
        options=sorted(set(tickers)),
        key=f"chart_ticker_{key_suffix}",
    )

    if not ticker_choisi:
        return

    hist = yf.Ticker(ticker_choisi).history(
        period=config.HISTORY_PERIOD, interval=config.HISTORY_INTERVAL, auto_adjust=False
    )
    if hist.empty:
        st.warning("Données indisponibles pour cette action.")
        return

    hist[f"EMA_{config.EMA_SHORT}"] = hist["Close"].ewm(span=config.EMA_SHORT, adjust=False).mean()
    hist[f"EMA_{config.EMA_LONG}"] = hist["Close"].ewm(span=config.EMA_LONG, adjust=False).mean()
    hist[f"EMA_{config.EMA_TREND}"] = hist["Close"].ewm(span=config.EMA_TREND, adjust=False).mean()

    # Les EMA sont calculées sur l'historique complet (2 ans, nécessaire pour
    # leur stabilisation, en particulier l'EMA200) mais on n'affiche que les
    # 6 derniers mois pour que le graphique reste lisible.
    hist_affiche = hist.tail(130)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist_affiche.index, open=hist_affiche["Open"], high=hist_affiche["High"],
        low=hist_affiche["Low"], close=hist_affiche["Close"],
        name="Cours",
    ))
    fig.add_trace(go.Scatter(x=hist_affiche.index, y=hist_affiche[f"EMA_{config.EMA_SHORT}"],
                              name=f"EMA{config.EMA_SHORT}", line=dict(color="orange", width=1.5)))
    fig.add_trace(go.Scatter(x=hist_affiche.index, y=hist_affiche[f"EMA_{config.EMA_LONG}"],
                              name=f"EMA{config.EMA_LONG}", line=dict(color="blue", width=1.5)))
    fig.add_trace(go.Scatter(x=hist_affiche.index, y=hist_affiche[f"EMA_{config.EMA_TREND}"],
                              name=f"EMA{config.EMA_TREND}", line=dict(color="purple", width=1, dash="dot")))
    fig.update_layout(
        title=f"{ticker_choisi} — Cours et EMA{config.EMA_SHORT}/{config.EMA_LONG}/{config.EMA_TREND}",
        xaxis_rangeslider_visible=False,
        height=550,
    )
    st.plotly_chart(fig, use_container_width=True)

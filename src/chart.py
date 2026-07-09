"""
Composant de graphique réutilisable (chandelier + EMA9/EMA20/EMA200, volume
et RSI en sous-graphiques optionnels, niveaux de Fibonacci en surcouche),
partagé par toutes les pages Streamlit pour éviter de dupliquer le code de
récupération et de tracé.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from src import config
from src.indicators import add_ema, add_rsi

# Périodes d'affichage proposées, en nombre de jours de bourse (~jours ouvrés).
PERIODES_AFFICHAGE = {
    "5 jours": 5,
    "1 mois": 22,
    "3 mois": 65,
    "6 mois": 130,
    "1 an": 260,
}


def fetch_and_prepare_chart_data(ticker: str) -> pd.DataFrame | None:
    """Télécharge l'historique complet (2 ans) et calcule les indicateurs nécessaires à l'affichage."""
    hist = yf.Ticker(ticker).history(
        period=config.HISTORY_PERIOD, interval=config.HISTORY_INTERVAL, auto_adjust=False
    )
    if hist.empty:
        return None

    hist = add_ema(hist, config.EMA_SHORT)
    hist = add_ema(hist, config.EMA_LONG)
    hist = add_ema(hist, config.EMA_TREND)
    hist = add_rsi(hist, config.RSI_PERIOD)
    return hist


def build_figure(
    hist: pd.DataFrame,
    show_ema9: bool = True,
    show_ema20: bool = True,
    show_ema200: bool = False,
    show_volume: bool = False,
    show_rsi: bool = False,
    fib_levels: dict | None = None,
    ticker: str = "",
) -> go.Figure:
    """Construit la figure Plotly (chandelier + indicateurs sélectionnés + niveaux Fibonacci optionnels)."""
    nb_rows = 1 + int(show_volume) + int(show_rsi)
    if nb_rows == 1:
        row_heights = [1.0]
    elif nb_rows == 2:
        row_heights = [0.75, 0.25]
    else:
        row_heights = [0.6, 0.2, 0.2]

    fig = make_subplots(
        rows=nb_rows, cols=1, shared_xaxes=True,
        row_heights=row_heights, vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"],
        name="Cours",
    ), row=1, col=1)

    if show_ema9:
        fig.add_trace(go.Scatter(x=hist.index, y=hist[f"EMA_{config.EMA_SHORT}"],
                                  name=f"EMA{config.EMA_SHORT}", line=dict(color="orange", width=1.5)), row=1, col=1)
    if show_ema20:
        fig.add_trace(go.Scatter(x=hist.index, y=hist[f"EMA_{config.EMA_LONG}"],
                                  name=f"EMA{config.EMA_LONG}", line=dict(color="blue", width=1.5)), row=1, col=1)
    if show_ema200:
        fig.add_trace(go.Scatter(x=hist.index, y=hist[f"EMA_{config.EMA_TREND}"],
                                  name=f"EMA{config.EMA_TREND}", line=dict(color="purple", width=2)), row=1, col=1)

    if fib_levels:
        from src.fibonacci import FIB_LEVEL_COLORS
        for label, valeur in fib_levels.items():
            if label in ("trend", "swing_high", "swing_low"):
                continue
            couleur = FIB_LEVEL_COLORS.get(label, "#999999")
            largeur = 2 if label == "61.8%" else 1
            fig.add_hline(
                y=valeur, line_dash="dot", line_color=couleur, line_width=largeur,
                annotation_text=f"{label} ({valeur:.2f}€)", annotation_position="right",
                row=1, col=1,
            )

    current_row = 1
    if show_volume:
        current_row += 1
        couleurs_volume = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(hist["Close"], hist["Open"])]
        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], name="Volume", marker_color=couleurs_volume),
                      row=current_row, col=1)

    if show_rsi:
        current_row += 1
        rsi_col = f"RSI_{config.RSI_PERIOD}"
        fig.add_trace(go.Scatter(x=hist.index, y=hist[rsi_col], name=f"RSI{config.RSI_PERIOD}",
                                  line=dict(color="teal", width=1.5)), row=current_row, col=1)
        fig.add_hline(y=config.RSI_OVERBOUGHT, line_dash="dash", line_color="red", row=current_row, col=1)
        fig.add_hline(y=config.RSI_OVERSOLD, line_dash="dash", line_color="green", row=current_row, col=1)

    fig.update_layout(
        title=f"{ticker} — Cours" if ticker else "Cours",
        xaxis_rangeslider_visible=False,
        height=550 + 130 * (nb_rows - 1),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def render_stock_chart(tickers_disponibles: list[str], key: str, titre: str = "Visualiser une action") -> None:
    """
    Affiche un sélecteur d'action, des cases à cocher pour choisir les
    indicateurs affichés, un sélecteur de période, puis le graphique
    correspondant.

    `tickers_disponibles` : liste des tickers proposés dans le sélecteur.
    `key` : préfixe unique par page, pour éviter les conflits de widgets.
    """
    if not tickers_disponibles:
        return

    st.divider()
    st.subheader(titre)

    col_ticker, col_periode = st.columns([2, 1])
    with col_ticker:
        ticker_choisi = st.selectbox(
            "Choisir une action", sorted(set(tickers_disponibles)), key=f"selectbox_{key}",
        )
    with col_periode:
        periode_choisie = st.selectbox(
            "Période affichée", list(PERIODES_AFFICHAGE.keys()), index=3, key=f"periode_{key}",
        )

    col1, col2, col3, col4, col5 = st.columns(5)
    show_ema9 = col1.checkbox("EMA9", value=True, key=f"ema9_{key}")
    show_ema20 = col2.checkbox("EMA20", value=True, key=f"ema20_{key}")
    show_ema200 = col3.checkbox("EMA200", value=False, key=f"ema200_{key}")
    show_volume = col4.checkbox("Volume", value=False, key=f"volume_{key}")
    show_rsi = col5.checkbox("RSI", value=False, key=f"rsi_{key}")

    if not ticker_choisi:
        return

    hist = fetch_and_prepare_chart_data(ticker_choisi)
    if hist is None:
        st.warning("Impossible de récupérer l'historique pour cette action.")
        return

    nb_jours = PERIODES_AFFICHAGE[periode_choisie]
    hist_affiche = hist.tail(nb_jours)

    fig = build_figure(
        hist_affiche, show_ema9=show_ema9, show_ema20=show_ema20,
        show_ema200=show_ema200, show_volume=show_volume, show_rsi=show_rsi, ticker=ticker_choisi,
    )
    st.plotly_chart(fig, use_container_width=True)

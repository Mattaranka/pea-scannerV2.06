"""
Backtesting des signaux du scanner.

Principe : chaque fichier de data/history/ est une photo d'une séance de
scan, avec le cours de clôture et les signaux détectés ce jour-là pour
chaque action. En comparant le cours d'un jour de signal au cours du même
ticker N archives (= N séances de scan) plus loin, on obtient la
performance réelle constatée après ce signal - sans avoir besoin de
retélécharger quoi que ce soit : tout est déjà dans les archives.

Limite à garder en tête : les statistiques ne deviennent fiables qu'après
plusieurs semaines d'accumulation (quelques dizaines de signaux par
catégorie au minimum). Avec un historique jeune, les résultats affichés
peuvent être bruités - c'est normal et volontairement affiché tel quel,
avec le nombre de signaux à l'appui pour juger de la fiabilité.
"""

import glob
import os

import pandas as pd

from src import config


def load_history() -> pd.DataFrame:
    """Charge et concatène toutes les archives quotidiennes disponibles."""
    fichiers = sorted(glob.glob(os.path.join(config.HISTORY_DIR, "*.csv")))
    frames = []
    for fichier in fichiers:
        try:
            frame = pd.read_csv(fichier)
            if "date" in frame.columns and not frame.empty:
                frames.append(frame)
        except Exception as exc:  # noqa: BLE001 - on ignore un fichier corrompu et on continue
            print(f"[backtest] Impossible de lire {fichier}: {exc}")

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)
    df_all["date"] = pd.to_datetime(df_all["date"])
    # Une même action peut apparaître plusieurs fois pour une même date si le
    # workflow a été relancé manuellement le même jour : on ne garde que la
    # dernière version dans ce cas.
    df_all = df_all.drop_duplicates(subset=["ticker", "date"], keep="last")
    return df_all.sort_values(["ticker", "date"]).reset_index(drop=True)


def compute_forward_returns(df_all: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """
    Ajoute, pour chaque ligne (= un jour donné pour un ticker donné), la
    performance en % constatée `horizon` séances de scan plus loin, pour
    chaque horizon de `horizons`. Les lignes trop récentes (pour lesquelles
    on n'a pas encore assez de séances futures archivées) obtiennent NaN.
    """
    df_all = df_all.sort_values(["ticker", "date"]).reset_index(drop=True)
    for horizon in horizons:
        prix_futur = df_all.groupby("ticker")["dernier_cours"].shift(-horizon)
        df_all[f"forward_return_{horizon}j_pct"] = (
            (prix_futur - df_all["dernier_cours"]) / df_all["dernier_cours"] * 100
        )
    return df_all


def _resume_signal(df_all: pd.DataFrame, masque: pd.Series, label: str, horizons: list[int]) -> list[dict]:
    """Calcule les statistiques (nb de signaux, taux de réussite, gain moyen/médian) pour un signal donné."""
    sous_ensemble = df_all[masque]
    lignes = []
    for horizon in horizons:
        col = f"forward_return_{horizon}j_pct"
        valeurs = sous_ensemble[col].dropna() if col in sous_ensemble.columns else pd.Series(dtype=float)
        if valeurs.empty:
            lignes.append({
                "signal": label, "horizon_j": horizon, "nb_signaux": 0,
                "taux_reussite_pct": None, "gain_moyen_pct": None, "gain_median_pct": None,
            })
        else:
            lignes.append({
                "signal": label,
                "horizon_j": horizon,
                "nb_signaux": int(len(valeurs)),
                "taux_reussite_pct": round(float((valeurs > 0).mean() * 100), 1),
                "gain_moyen_pct": round(float(valeurs.mean()), 2),
                "gain_median_pct": round(float(valeurs.median()), 2),
            })
    return lignes


def run_backtest(horizons: list[int] | None = None) -> pd.DataFrame:
    """
    Exécute le backtesting complet sur l'historique archivé et retourne un
    DataFrame de synthèse (une ligne par combinaison signal × horizon).
    """
    horizons = horizons or config.BACKTEST_HORIZONS
    df_all = load_history()
    if df_all.empty:
        return pd.DataFrame()

    df_all = compute_forward_returns(df_all, horizons)

    # Colonnes potentiellement absentes sur les archives les plus anciennes
    # (créées avant l'ajout d'une fonctionnalité) : on les crée à None pour
    # que les comparaisons ci-dessous ne plantent pas et écartent simplement
    # ces lignes plus anciennes des signaux concernés.
    for col in ["croisement", "cassure_20j", "score_swing_total"]:
        if col not in df_all.columns:
            df_all[col] = None

    signaux = {
        "Croisement haussier": df_all["croisement"] == "haussier",
        "Croisement baissier": df_all["croisement"] == "baissier",
        "Cassure haussière": df_all["cassure_20j"] == "haussière",
        "Cassure baissière": df_all["cassure_20j"] == "baissière",
        f"Score swing ≥ {config.SCORE_DISPLAY_MIN}": df_all["score_swing_total"] >= config.SCORE_DISPLAY_MIN,
    }

    lignes = []
    for label, masque in signaux.items():
        lignes.extend(_resume_signal(df_all, masque, label, horizons))

    return pd.DataFrame(lignes)

# Scanner PEA

Scanner d'actions françaises éligibles au PEA, avec mise à jour automatique
quotidienne, détection de signaux techniques, score swing trading sur 100
et niveaux de Fibonacci.

## Fonctionnement

1. Chaque jour à 18h30 (heure de Paris, jours ouvrés), un **GitHub Actions**
   télécharge 2 ans de données pour toutes les actions listées dans
   `src/config.py` ainsi que pour l'indice de référence (CAC 40), calcule
   les indicateurs techniques et le score swing trading. Les résultats sont
   sauvegardés dans `data/scan_results.csv` (toujours écrasé, c'est la photo
   du jour) **et** archivés dans `data/history/AAAA-MM-JJ.csv` (jamais
   écrasé) pour le backtesting. Le tout est commité automatiquement.
2. L'application **Streamlit** lit ce fichier et l'affiche sur plusieurs pages :
   - `app.py` : vue d'ensemble de toutes les actions suivies
   - `pages/1_Croisements_EMA.py` : actions ayant eu un croisement EMA9/EMA20
   - `pages/2_RSI.py` : actions en zone de surachat/survente
   - `pages/3_Volumes.py` : actions dont le volume dépasse 1,5× leur moyenne
   - `pages/4_Cassures.py` : actions ayant cassé leur plus haut/bas 20 jours
   - `pages/5_Opportunites.py` : setups classés par **score swing trading /100**
   - `pages/6_Backtest.py` : performance historique réelle de chaque signal
   - `pages/7_Fibonacci.py` : niveaux de Fibonacci (3 méthodes au choix)

   Chaque page (sauf le backtest) inclut un graphique cours + EMA9/20/200
   avec sélecteur d'action, de période (5j/1mois/3mois/6mois/1an) et cases
   à cocher pour afficher/masquer EMA, volume et RSI, via le composant
   partagé `src/chart.py`.

### Score swing trading (0-100)

Remplace l'ancien "score de tendance". Réparti en 7 critères pondérés,
calculés dans `src/scoring.py` :

| Critère | Points max |
|---|---|
| Structure des EMA (9/20/200) | 25 |
| RSI (14) | 20 |
| Volume | 15 |
| ATR (volatilité) | 10 |
| MACD | 10 |
| Structure de prix (support/résistance 20j) | 10 |
| Contexte de marché (indice CAC 40) | 10 |

Le score total détermine un signal et une couleur :

| Score | Signal | Couleur |
|---|---|---|
| ≥ 80 | EXCELLENT | 🟢 vert |
| ≥ 65 | BON | 🟢 vert clair |
| ≥ 50 | MODÉRÉ | 🟡 jaune |
| ≥ 35 | FAIBLE | 🟠 orange |
| < 35 | DÉFAVORABLE | 🔴 rouge |

Détail complet du barème (bonus pullback, divergence RSI, seuils MACD...)
directement dans `src/scoring.py`, avec un commentaire par règle.

### Niveaux de Fibonacci

`src/fibonacci.py` détecte les swing highs/lows (un point domine les 5 jours
avant/après) et calcule les retracements (23,6% / 38,2% / 50% / 61,8% /
78,6%) et extensions (127,2% / 161,8% / 200%). Trois méthodes disponibles
sur `pages/7_Fibonacci.py` :

- **Option A (recommandée)** : swing récent, fenêtre 20-60 jours — la plus
  adaptée à un horizon de swing trading de quelques jours à quelques semaines.
- **Option B** : superpose court/moyen/long terme (les zones de convergence
  entre échelles sont les plus significatives).
- **Option C** : 52 semaines — utile seulement pour un horizon > 1 mois.

Le 52 semaines n'est volontairement **pas** le calcul par défaut : trop
large, il donnerait des niveaux trop espacés pour du swing trading.

### Autres indicateurs

- **EMA9 / EMA20 / EMA200**, RSI14, ATR14, MACD(12,26,9)
- **Volume du jour**, volume moyen 20 jours, ratio jour/moyenne
- **Variation moyenne 14 jours** (amplitude haut-bas, volatilité récente)
- **Plus haut/bas 52 semaines et 20 jours**, détection de cassure
- **Stop-loss / objectif suggérés** à partir de l'ATR (cours ∓ multiple d'ATR)
- **Fraîcheur du signal** (`jours_depuis_croisement`, `jours_depuis_cassure`) :
  un signal garde sa pertinence quelques jours, pas seulement le jour même

### Backtesting

`src/backtest.py` exploite les archives quotidiennes de `data/history/` pour
mesurer, sans téléchargement supplémentaire, la performance réelle constatée
après chaque type de signal, sur plusieurs horizons (2, 5, 10 jours de bourse
par défaut). Les statistiques deviennent fiables après plusieurs semaines
d'accumulation ; `pages/6_Backtest.py` affiche un avertissement tant que
l'historique est jeune.

Aucune infrastructure à gérer : tout tourne sur GitHub (calcul) et Streamlit
Community Cloud (affichage), gratuitement.

## Mise en place (100% en ligne, aucune installation locale nécessaire)

### 1. Créer le dépôt GitHub

- Va sur https://github.com/new
- Crée un nouveau dépôt (public ou privé), par exemple `pea-scanner`
- Utilise GitHub Desktop (recommandé pour les mises à jour ultérieures) ou
  "Add file > Upload files" en conservant l'arborescence des dossiers.

### 2. Vérifier les permissions du workflow

- **Settings > Actions > General > Workflow permissions**
- Sélectionne **"Read and write permissions"**, sauvegarde.

### 3. Lancer un premier scan manuel

- Onglet **Actions** → workflow **"Mise à jour quotidienne des données PEA"**
  → **"Run workflow"**.

### 4. Déployer l'application Streamlit

- https://share.streamlit.io → **"New app"** → dépôt `pea-scanner`, branche
  `main`, fichier principal `app.py`
- Vérifie la version Python (**3.11**) dans "Advanced settings", ou laisse
  le fichier `runtime.txt` fourni s'en charger automatiquement.

À partir de là, l'application se met à jour automatiquement chaque jour.

## Étendre le projet

- **Ajouter des actions** : compléter `PEA_STOCKS` dans `src/config.py`
- **Ajouter un indicateur** : nouvelle fonction dans `src/indicators.py`,
  appelée depuis `src/scanner.py`
- **Ajuster le barème de score** : tout est dans `src/scoring.py`, une
  fonction par critère
- **Ajouter une page** : nouveau fichier dans `pages/` (détection automatique
  par Streamlit)

## Structure du projet

```
pea-scanner/
├── .github/workflows/update_data.yml   # planification du scan quotidien
├── data/                                # résultats + archives quotidiennes
├── src/
│   ├── config.py                        # liste des actions + tous les paramètres
│   ├── data_fetcher.py                  # téléchargement yfinance (+ retry)
│   ├── indicators.py                    # indicateurs de base (EMA, RSI, ATR, MACD...)
│   ├── scoring.py                       # score swing trading 0-100 (7 critères)
│   ├── fibonacci.py                     # détection de swings + niveaux Fibonacci
│   ├── chart.py                         # graphique partagé (EMA/volume/RSI/Fibonacci)
│   ├── scanner.py                       # orchestration du scan quotidien
│   └── backtest.py                      # performance historique des signaux
├── scripts/daily_update.py              # point d'entrée du job GitHub Actions
├── app.py                               # page d'accueil Streamlit
├── pages/                               # 1_Croisements_EMA, 2_RSI, 3_Volumes,
│                                         # 4_Cassures, 5_Opportunites, 6_Backtest,
│                                         # 7_Fibonacci
└── requirements.txt
```

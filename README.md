# Character Network Project

![CI](https://github.com/la9ba3/R-seaux-de-Personnages/actions/workflows/ci.yaml/badge.svg)

App en ligne (Render): https://reseaux-de-personnages.onrender.com

## Interface web simple

Lancement local:

```powershell
.\.venv\Scripts\python.exe src/web_app.py
```

Puis ouvre `http://127.0.0.1:8000`.

Usage:
- Colle un texte dans le champ d'entree.
- Clique sur **Analyser le texte**.
- Clique sur **Texte de demo** pour charger rapidement un exemple.
- Optionnel: active **Analyse auto (0.8s)** pour relancer l'analyse pendant la frappe.

Reglage des aretes:
- `src/config.py` -> `interaction_min_weight`
- `1` = mode permissif
- `2` = mode strict

## Generation des sorties

Pour generer le CSV de soumission:

```powershell
.\.venv\Scripts\python.exe scripts/run_all_chapters.py
```

Sortie: `data/submissions/submission.csv`

Pour generer les graphes PNG:

```powershell
.\.venv\Scripts\python.exe scripts/export_graph_figures.py
```

Sortie: `outputs/figures/`

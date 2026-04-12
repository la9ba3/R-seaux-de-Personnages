# Character Network Project

## Interface web simple

Lancement:

```powershell
.\.venv\Scripts\python.exe src/web_app.py
```

Puis ouvre:

`http://127.0.0.1:8000`

Usage:

- Colle un texte dans le champ d'entree.
- Clique sur **Analyser le texte** (analyse dynamique sans rechargement).
- Optionnel: active **Analyse auto (0.8s)** pour relancer l'analyse pendant la frappe.
- L'interface affiche les statistiques, le graphe (image) et la liste des personnages detectes.

Reglage des aretes:

- `src/config.py` -> `interaction_min_weight`
- `1` = mode permissif (plus d'aretes, utile pour demo/test)
- `2` = mode strict (proche du comportement initial)

## Variantes leaderboard

Pour generer plusieurs CSV candidats rapidement:

```powershell
.\.venv\Scripts\python.exe scripts/generate_submission_variants.py
```

Les fichiers sont ecrits dans `data/submissions/`:

- `submission_v_current.csv`
- `submission_v_weight2.csv`
- `submission_v_keep_spacy.csv`

Note: toutes ces variantes gardent `cooccurrence_window=25` (contrainte cahier des charges).

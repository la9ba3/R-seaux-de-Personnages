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

Polarite des relations:
- `src/config.py` -> `polarity_enabled`
- lexique: `data/polarity/dictionnaire_polarite_fr.txt`
- les aretes gardent leur `weight` de cooccurrence et gagnent `polarity`, `sentiment`, `polarity_width`

## Pipeline de soumission

Le pipeline complet est dans `src/main.py` et suit ces etapes:

1. Lecture du chapitre `.txt.preprocessed`, nettoyage des espaces et construction du `doc_id` Kaggle (`lca0`, `paf0`, etc.).
2. Extraction NER avec spaCy `fr_core_news_lg`.
3. Ajout de mentions par regles: titres, roles, recuperation de noms dans les entites bruitees, listes de personnages.
4. Nettoyage et filtrage des mentions. Les filtres stricts suppriment les faux personnages.
5. Alignement des mentions sur les tokens du chapitre.
6. Resolution des alias, avec fusion optionnelle d'alias connus pour les personnages recurrents.
7. Suppression des personnages faibles avant construction des relations.
8. Extraction des interactions par cooccurrence dans une fenetre de 25 tokens.
9. Ajout optionnel de la polarite sur les aretes avec le lexique `data/polarity/dictionnaire_polarite_fr.txt`.
10. Construction du graphe NetworkX, export GraphML, puis generation du CSV.

Dernier score public obtenu avec `submission.csv`: `0.61871`.

Les livrables de soutenance (article, presentation et soumission finale) sont fournis
separement du depot de code afin de garder le projet propre.



## Generation des sorties

Pour regenerer la soumission finale:

```powershell
.\.venv\Scripts\python.exe scripts/generate_final_submission.py
```

Sortie: `data/submissions/submission.csv`


Pour generer les graphes PNG:

```powershell
.\.venv\Scripts\python.exe scripts/export_graph_figures.py
```

Sortie: `outputs/figures/`

Les scripts d'export de graphes utilisent la meme configuration que la
soumission finale: filtres stricts, alias connus et export complet des alias.

Pour generer les graphes PNG par chapitre avec polarite:

```powershell
.\.venv\Scripts\python.exe scripts/export_polarity_graph_figures.py
```

Sortie: `outputs/figures_polarity/`

Pour generer un graphe global combine avec polarite:

```powershell
.\.venv\Scripts\python.exe scripts/export_combined_polarity_graph.py
```

Sorties:
- `outputs/figures_polarity/combined_polarity_graph.png`
- `outputs/figures_polarity/combined_polarity_graph.graphml`

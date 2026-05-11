from pathlib import Path
import argparse
import sys

# Permet d'importer les modules du dossier src/ et les helpers scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.append(str(SRC_DIR))
sys.path.append(str(SCRIPTS_DIR))

from config import validate_config
from export_graph_figures import (
    build_figure_path,
    draw_graph,
    ensure_dir,
    iter_chapter_files,
    simplify_graph_for_visualization,
)
from generate_final_submission import build_final_submission_config
from main import run_pipeline
from ner import load_ner_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genere les graphes de personnages par chapitre avec polarite."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum de chapitres a traiter (utile pour un test rapide).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_final_submission_config()
    config["polarity_enabled"] = True
    validate_config(config)

    raw_dir = Path(config["data_raw_dir"])
    figures_dir = Path(config["outputs_figures_dir"]).parent / "figures_polarity"
    books = config["books"]
    extension = config["chapter_file_extension"]

    ensure_dir(figures_dir)

    total_files = 0
    success_count = 0
    error_count = 0

    print(f"[INFO] Chargement du modele spaCy: {config['ner_model']}")
    model = load_ner_model(config["ner_model"])

    print("=== Generation des graphes avec polarite par chapitre ===")

    for chapter_file in iter_chapter_files(raw_dir, books, extension):
        if args.limit is not None and total_files >= args.limit:
            break

        total_files += 1
        print(f"\n[INFO] Traitement : {chapter_file}")

        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)
            doc_id = result["doc_id"]
            graph = result["graph"]

            graph_for_plot = simplify_graph_for_visualization(graph, min_degree=0)
            output_path = build_figure_path(doc_id, figures_dir)
            draw_graph(
                graph_for_plot,
                title=f"Graphe de personnages avec polarite - {doc_id}",
                output_path=output_path,
            )

            positive_edges = sum(
                1 for _, _, data in graph.edges(data=True) if data.get("polarity", 0) > 0
            )
            negative_edges = sum(
                1 for _, _, data in graph.edges(data=True) if data.get("polarity", 0) < 0
            )

            success_count += 1
            print(
                f"[OK] {doc_id} | "
                f"noeuds={graph.number_of_nodes()} | "
                f"aretes={graph.number_of_edges()} | "
                f"positives={positive_edges} | "
                f"negatives={negative_edges} | "
                f"image={output_path.name}"
            )

        except Exception as error:
            error_count += 1
            print(f"[ERROR] Echec sur {chapter_file} : {error}")

    print("\n=== Termine ===")
    print(f"Fichiers detectes : {total_files}")
    print(f"Succes : {success_count}")
    print(f"Erreurs : {error_count}")
    print(f"Dossier de sortie : {figures_dir}")


if __name__ == "__main__":
    main()

from pathlib import Path
import sys

# Permet d'importer les modules du dossier src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.append(str(SRC_DIR))

from config import get_default_config, validate_config
from export import build_submission_row, export_submission_csv, graph_to_graphml_string
from main import run_pipeline
from ner import load_ner_model
from run_all_chapters import iter_chapter_files


def build_final_submission_config() -> dict:
    config = get_default_config()
    config["submission_filename"] = "submission.csv"
    config["strict_ner_filters"] = True
    config["known_aliases_enabled"] = True
    config["export_all_aliases"] = True
    config["keep_singleton_sources"] = [
        source
        for source in config["keep_singleton_sources"]
        if source != "rule_role"
    ]
    return config


def main() -> None:
    config = build_final_submission_config()
    validate_config(config)

    raw_dir = Path(config["data_raw_dir"])
    books = config["books"]
    extension = config["chapter_file_extension"]

    rows = []
    total_files = 0
    success_count = 0
    error_count = 0

    print(f"[INFO] Chargement du modele spaCy: {config['ner_model']}")
    model = load_ner_model(config["ner_model"])

    print("=== Generation de la soumission finale ===")

    for chapter_file in iter_chapter_files(raw_dir, books, extension):
        total_files += 1
        print(f"\n[INFO] Traitement : {chapter_file}")

        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)

            graphml_content = graph_to_graphml_string(result["graph"])
            rows.append(build_submission_row(result["doc_id"], graphml_content))

            success_count += 1
            print(
                f"[OK] {result['doc_id']} | "
                f"mentions={len(result['mentions'])} | "
                f"personnages={len(result['characters'])} | "
                f"interactions={len(result['interactions'])}"
            )

        except Exception as error:
            error_count += 1
            print(f"[ERROR] Echec sur {chapter_file} : {error}")

    output_csv = Path(config["data_submissions_dir"]) / config["submission_filename"]
    export_submission_csv(rows, str(output_csv))

    print("\n=== Termine ===")
    print(f"Fichiers detectes : {total_files}")
    print(f"Succes : {success_count}")
    print(f"Erreurs : {error_count}")
    print(f"CSV genere : {output_csv}")


if __name__ == "__main__":
    main()

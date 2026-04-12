from pathlib import Path
import sys

# Permet d'importer les modules du dossier src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.append(str(SRC_DIR))

from config import get_default_config, validate_config
from main import run_pipeline
from export import graph_to_graphml_string, build_submission_row, export_submission_csv
from ner import load_ner_model


def iter_chapter_files(raw_dir: Path, books: list[str], extension: str):
    """
    Itère sur tous les fichiers chapitres des livres configurés.
    """
    for book in books:
        book_dir = raw_dir / book
        if not book_dir.exists():
            print(f"[WARN] Dossier introuvable : {book_dir}")
            continue

        chapter_files = sorted(book_dir.glob(f"*{extension}"))
        for chapter_file in chapter_files:
            yield chapter_file


def main() -> None:
    config = get_default_config()
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

    print("=== Lancement du traitement de tous les chapitres ===")

    for chapter_file in iter_chapter_files(raw_dir, books, extension):
        total_files += 1
        print(f"\n[INFO] Traitement : {chapter_file}")

        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)

            graphml_content = graph_to_graphml_string(result["graph"])
            row = build_submission_row(result["doc_id"], graphml_content)
            rows.append(row)

            success_count += 1

            print(
                f"[OK] {result['doc_id']} | "
                f"mentions={len(result['mentions'])} | "
                f"personnages={len(result['characters'])} | "
                f"interactions={len(result['interactions'])}"
            )

        except Exception as e:
            error_count += 1
            print(f"[ERROR] Échec sur {chapter_file} : {e}")

    output_csv = Path(config["data_submissions_dir"]) / config["submission_filename"]
    export_submission_csv(rows, str(output_csv))

    print("\n=== Terminé ===")
    print(f"Fichiers détectés : {total_files}")
    print(f"Succès : {success_count}")
    print(f"Erreurs : {error_count}")
    print(f"CSV généré : {output_csv}")


if __name__ == "__main__":
    main()

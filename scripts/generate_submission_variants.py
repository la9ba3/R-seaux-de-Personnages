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
    for book in books:
        book_dir = raw_dir / book
        if not book_dir.exists():
            print(f"[WARN] Dossier introuvable : {book_dir}")
            continue

        chapter_files = sorted(book_dir.glob(f"*{extension}"))
        for chapter_file in chapter_files:
            yield chapter_file


def build_variant_configs(base_config: dict) -> list[tuple[str, dict]]:
    variants = []

    current = dict(base_config)
    # Contrainte cahier des charges: fenetre fixee a 25.
    current["cooccurrence_window"] = 25
    variants.append(("submission_v_current.csv", current))

    strict_edges = dict(base_config)
    strict_edges["cooccurrence_window"] = 25
    strict_edges["interaction_min_weight"] = 2
    variants.append(("submission_v_weight2.csv", strict_edges))

    keep_spacy_singletons = dict(base_config)
    keep_spacy_singletons["cooccurrence_window"] = 25
    keep_spacy_singletons["keep_singleton_sources"] = list(base_config["keep_singleton_sources"]) + ["spacy"]
    variants.append(("submission_v_keep_spacy.csv", keep_spacy_singletons))

    return variants


def run_variant(config: dict, model, output_csv: Path) -> tuple[int, int, int]:
    raw_dir = Path(config["data_raw_dir"])
    books = config["books"]
    extension = config["chapter_file_extension"]

    rows = []
    success_count = 0
    error_count = 0
    total_edges = 0

    for chapter_file in iter_chapter_files(raw_dir, books, extension):
        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)
            graphml_content = graph_to_graphml_string(result["graph"])
            row = build_submission_row(result["doc_id"], graphml_content)
            rows.append(row)
            success_count += 1
            total_edges += result["graph"].number_of_edges()
        except Exception as error:
            error_count += 1
            print(f"[ERROR] {chapter_file}: {error}")

    export_submission_csv(rows, str(output_csv))
    return success_count, error_count, total_edges


def main() -> None:
    base_config = get_default_config()
    validate_config(base_config)

    print(f"[INFO] Chargement du modele spaCy: {base_config['ner_model']}")
    model = load_ner_model(base_config["ner_model"])

    submissions_dir = Path(base_config["data_submissions_dir"])
    variant_configs = build_variant_configs(base_config)

    print("=== Generation des variantes de soumission ===")
    for filename, variant_config in variant_configs:
        validate_config(variant_config)
        output_csv = submissions_dir / filename
        print(f"\n[INFO] Variante: {filename}")
        print(
            f"[INFO] cooccurrence_window={variant_config['cooccurrence_window']} | "
            f"interaction_min_weight={variant_config['interaction_min_weight']} | "
            f"keep_singleton_sources={variant_config['keep_singleton_sources']}"
        )
        success_count, error_count, total_edges = run_variant(variant_config, model, output_csv)
        print(
            f"[OK] {filename} | chapitres_ok={success_count} | erreurs={error_count} | "
            f"aretes_total={total_edges}"
        )
        print(f"[OK] CSV: {output_csv}")

    print("\n=== Termine ===")


if __name__ == "__main__":
    main()

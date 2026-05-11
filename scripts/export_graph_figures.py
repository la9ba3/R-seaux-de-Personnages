from pathlib import Path
import sys

import matplotlib.pyplot as plt
import networkx as nx

# Permet d'importer les modules du dossier src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.append(str(SRC_DIR))
sys.path.append(str(SCRIPTS_DIR))

from config import validate_config
from generate_final_submission import build_final_submission_config
from main import run_pipeline
from ner import load_ner_model


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_figure_path(doc_id: str, figures_dir: Path) -> Path:
    """
    Transforme un doc_id Kaggle (ex: lca0, paf3) en chemin png.
    """
    return figures_dir / f"{doc_id}.png"


def simplify_graph_for_visualization(graph: nx.Graph, min_degree: int = 0) -> nx.Graph:
    """
    Optionnel : permet de retirer les nœuds trop faibles pour rendre la figure plus lisible.
    Pour l'instant, on retire seulement les nœuds de degré < min_degree.
    """
    if min_degree <= 0:
        return graph.copy()

    nodes_to_keep = [node for node, degree in graph.degree() if degree >= min_degree]
    return graph.subgraph(nodes_to_keep).copy()


def draw_graph(graph: nx.Graph, title: str, output_path: Path) -> None:
    """
    Dessine et sauvegarde le graphe dans un fichier PNG.
    """
    if graph.number_of_nodes() == 0:
        print(f"[WARN] Graphe vide, image non générée : {output_path}")
        return

    plt.figure(figsize=(14, 10))

    # Positionnement
    pos = nx.spring_layout(graph, seed=42, k=1.2)

    # Taille des noeuds basée sur le degré
    degrees = dict(graph.degree())
    node_sizes = [500 + 250 * degrees[node] for node in graph.nodes()]

    # Largeur des arêtes basée sur leur poids
    edge_widths = []
    edge_colors = []
    for u, v, data in graph.edges(data=True):
        weight = data.get("weight", 1)
        polarity = data.get("polarity", 0)
        if polarity > 0:
            edge_colors.append("#2E8B57")
            edge_widths.append(1.0 + 0.8 * abs(polarity))
        elif polarity < 0:
            edge_colors.append("#B22222")
            edge_widths.append(1.0 + 0.8 * abs(polarity))
        else:
            edge_colors.append("#777777")
            edge_widths.append(1.0 + 0.6 * weight)

    # Labels = nom canonique exporté dans "label"
    labels = {
        node: data.get("label", node)
        for node, data in graph.nodes(data=True)
    }

    nx.draw_networkx_nodes(
        graph,
        pos,
        node_size=node_sizes,
        alpha=0.85,
    )

    nx.draw_networkx_edges(
        graph,
        pos,
        width=edge_widths,
        alpha=0.5,
        edge_color=edge_colors,
    )

    nx.draw_networkx_labels(
        graph,
        pos,
        labels=labels,
        font_size=8,
    )

    plt.title(title)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


def iter_chapter_files(raw_dir: Path, books: list[str], extension: str):
    """
    Itère sur tous les fichiers chapitres configurés.
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
    config = build_final_submission_config()
    validate_config(config)

    raw_dir = Path(config["data_raw_dir"])
    figures_dir = Path(config["outputs_figures_dir"])
    books = config["books"]
    extension = config["chapter_file_extension"]

    ensure_dir(figures_dir)

    total_files = 0
    success_count = 0
    error_count = 0

    print(f"[INFO] Chargement du modele spaCy: {config['ner_model']}")
    model = load_ner_model(config["ner_model"])

    print("=== Génération des figures de graphes ===")

    for chapter_file in iter_chapter_files(raw_dir, books, extension):
        total_files += 1
        print(f"\n[INFO] Traitement : {chapter_file}")

        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)
            doc_id = result["doc_id"]
            graph = result["graph"]

            # Tu peux ajuster min_degree si tu veux des graphes plus lisibles
            graph_for_plot = simplify_graph_for_visualization(graph, min_degree=0)

            output_path = build_figure_path(doc_id, figures_dir)
            draw_graph(
                graph_for_plot,
                title=f"Graphe de personnages - {doc_id}",
                output_path=output_path,
            )

            success_count += 1
            print(
                f"[OK] {doc_id} | "
                f"noeuds={graph.number_of_nodes()} | "
                f"arêtes={graph.number_of_edges()} | "
                f"image={output_path.name}"
            )

        except Exception as e:
            error_count += 1
            print(f"[ERROR] Échec sur {chapter_file} : {e}")

    print("\n=== Terminé ===")
    print(f"Fichiers détectés : {total_files}")
    print(f"Succès : {success_count}")
    print(f"Erreurs : {error_count}")
    print(f"Dossier de sortie : {figures_dir}")


if __name__ == "__main__":
    main()

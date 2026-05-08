from __future__ import annotations

from pathlib import Path
import argparse
import math
import sys

import matplotlib.pyplot as plt
import networkx as nx

# Permet d'importer les modules du dossier src/ et les helpers scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.append(str(SRC_DIR))
sys.path.append(str(SCRIPTS_DIR))

from config import get_default_config, validate_config
from export_graph_figures import ensure_dir, iter_chapter_files
from main import run_pipeline
from ner import load_ner_model
from polarity import sentiment_label


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genere un graphe global combine avec polarite."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum de chapitres a traiter (utile pour un test rapide).",
    )
    parser.add_argument(
        "--min-degree",
        type=int,
        default=1,
        help="Degre minimal des noeuds conserves dans le PNG global.",
    )
    return parser.parse_args()


def clamp_polarity(value: int) -> int:
    return max(-3, min(3, value))


def _node_label(graph: nx.Graph, node_id: str) -> str:
    return graph.nodes[node_id].get("label", node_id)


def add_chapter_graph(combined_graph: nx.Graph, chapter_graph: nx.Graph, doc_id: str) -> None:
    """
    Ajoute un graphe de chapitre au graphe global.
    Les personnages sont fusionnes par nom canonique.
    """
    for _, data in chapter_graph.nodes(data=True):
        label = data.get("label")
        if not label:
            continue

        if not combined_graph.has_node(label):
            combined_graph.add_node(
                label,
                label=label,
                names=label,
                chapters_count=0,
                chapters="",
            )

        chapters = set(filter(None, combined_graph.nodes[label].get("chapters", "").split(",")))
        chapters.add(doc_id)
        combined_graph.nodes[label]["chapters"] = ",".join(sorted(chapters))
        combined_graph.nodes[label]["chapters_count"] = len(chapters)

    for source, target, data in chapter_graph.edges(data=True):
        source_label = _node_label(chapter_graph, source)
        target_label = _node_label(chapter_graph, target)
        if source_label == target_label:
            continue

        weight = int(data.get("weight", 1))
        polarity = int(data.get("polarity", 0))
        evidence = data.get("polarity_evidence", "")

        if not combined_graph.has_edge(source_label, target_label):
            combined_graph.add_edge(
                source_label,
                target_label,
                weight=0,
                polarity_total=0,
                polarity=0,
                sentiment="neutral",
                polarity_width=0,
                polarity_evidence="",
                chapters="",
                chapters_count=0,
            )

        edge = combined_graph[source_label][target_label]
        edge["weight"] += weight
        edge["polarity_total"] += polarity
        edge["polarity"] = clamp_polarity(edge["polarity_total"])
        edge["sentiment"] = sentiment_label(edge["polarity"])
        edge["polarity_width"] = abs(edge["polarity"])

        chapters = set(filter(None, edge.get("chapters", "").split(",")))
        chapters.add(doc_id)
        edge["chapters"] = ",".join(sorted(chapters))
        edge["chapters_count"] = len(chapters)

        evidence_terms = set(filter(None, edge.get("polarity_evidence", "").split(", ")))
        evidence_terms.update(filter(None, evidence.split(", ")))
        edge["polarity_evidence"] = ", ".join(sorted(evidence_terms))


def simplify_combined_graph(graph: nx.Graph, min_degree: int = 1) -> nx.Graph:
    if min_degree <= 0:
        return graph.copy()
    nodes_to_keep = [node for node, degree in graph.degree() if degree >= min_degree]
    return graph.subgraph(nodes_to_keep).copy()


def draw_combined_graph(graph: nx.Graph, output_path: Path) -> None:
    if graph.number_of_nodes() == 0:
        print(f"[WARN] Graphe global vide, image non generee : {output_path}")
        return

    plt.figure(figsize=(22, 16))
    position = nx.spring_layout(graph, seed=42, k=0.75, iterations=80)

    degrees = dict(graph.degree())
    node_sizes = [350 + 120 * degrees[node] for node in graph.nodes()]
    labels = {node: graph.nodes[node].get("label", node) for node in graph.nodes()}

    edge_colors = []
    edge_widths = []
    for _, _, data in graph.edges(data=True):
        polarity = int(data.get("polarity", 0))
        weight = max(1, int(data.get("weight", 1)))
        if polarity > 0:
            edge_colors.append("#2E8B57")
            edge_widths.append(1.0 + 0.9 * abs(polarity))
        elif polarity < 0:
            edge_colors.append("#B22222")
            edge_widths.append(1.0 + 0.9 * abs(polarity))
        else:
            edge_colors.append("#777777")
            edge_widths.append(0.8 + 0.7 * math.log1p(weight))

    nx.draw_networkx_nodes(
        graph,
        position,
        node_size=node_sizes,
        node_color="#4C78A8",
        alpha=0.85,
    )
    nx.draw_networkx_edges(
        graph,
        position,
        width=edge_widths,
        edge_color=edge_colors,
        alpha=0.45,
    )
    nx.draw_networkx_labels(
        graph,
        position,
        labels=labels,
        font_size=7,
    )

    plt.title("Graphe global des personnages avec polarite")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_args()
    config = get_default_config()
    config["polarity_enabled"] = True
    validate_config(config)

    figures_dir = Path(config["outputs_figures_dir"]).parent / "figures_polarity"
    output_png = figures_dir / "combined_polarity_graph.png"
    output_graphml = figures_dir / "combined_polarity_graph.graphml"

    ensure_dir(figures_dir)

    combined_graph = nx.Graph()
    total_files = 0
    success_count = 0
    error_count = 0

    print(f"[INFO] Chargement du modele spaCy: {config['ner_model']}")
    model = load_ner_model(config["ner_model"])

    print("=== Construction du graphe global avec polarite ===")

    for chapter_file in iter_chapter_files(
        Path(config["data_raw_dir"]),
        config["books"],
        config["chapter_file_extension"],
    ):
        if args.limit is not None and total_files >= args.limit:
            break

        total_files += 1
        print(f"\n[INFO] Traitement : {chapter_file}")

        try:
            result = run_pipeline(str(chapter_file), config, preloaded_model=model)
            add_chapter_graph(combined_graph, result["graph"], result["doc_id"])
            success_count += 1
            print(
                f"[OK] {result['doc_id']} | "
                f"noeuds_global={combined_graph.number_of_nodes()} | "
                f"aretes_global={combined_graph.number_of_edges()}"
            )
        except Exception as error:
            error_count += 1
            print(f"[ERROR] Echec sur {chapter_file} : {error}")

    graph_for_plot = simplify_combined_graph(combined_graph, min_degree=args.min_degree)
    draw_combined_graph(graph_for_plot, output_png)
    nx.write_graphml(combined_graph, output_graphml, encoding="utf-8", prettyprint=True)

    print("\n=== Termine ===")
    print(f"Fichiers detectes : {total_files}")
    print(f"Succes : {success_count}")
    print(f"Erreurs : {error_count}")
    print(f"Noeuds globaux : {combined_graph.number_of_nodes()}")
    print(f"Aretes globales : {combined_graph.number_of_edges()}")
    print(f"PNG : {output_png}")
    print(f"GraphML : {output_graphml}")


if __name__ == "__main__":
    main()

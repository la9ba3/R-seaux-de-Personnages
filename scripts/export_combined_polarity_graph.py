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

from alias_resolution import (
    KNOWN_ALIAS_TARGETS,
    KNOWN_CANONICAL_DISPLAY,
    normalize_mention,
)
from config import validate_config
from export_graph_figures import ensure_dir, iter_chapter_files
from generate_final_submission import build_final_submission_config
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


def _split_aliases(value: str) -> set[str]:
    return {alias.strip() for alias in value.split(";") if alias.strip()}


def _global_alias_key(label: str, names: str) -> str:
    aliases = {label}
    aliases.update(_split_aliases(names))

    keys = []
    for alias in aliases:
        key = normalize_mention(alias)
        if key:
            keys.append(KNOWN_ALIAS_TARGETS.get(key, key))

    known_keys = [key for key in keys if key in KNOWN_CANONICAL_DISPLAY]
    if known_keys:
        return sorted(
            set(known_keys),
            key=lambda key: (-len(key.split()), -len(key), key),
        )[0]

    return sorted(
        set(keys),
        key=lambda key: (-len(key.split()), -len(key), key),
    )[0] if keys else normalize_mention(label)


def _display_label(alias_key: str, fallback_label: str) -> str:
    if alias_key in KNOWN_CANONICAL_DISPLAY:
        return KNOWN_CANONICAL_DISPLAY[alias_key]
    return fallback_label


def _register_alias_indexes(combined_graph: nx.Graph, alias_key: str, global_label: str) -> None:
    alias_index = combined_graph.graph.setdefault("alias_key_to_label", {})
    last_name_index = combined_graph.graph.setdefault("last_name_to_label", {})

    alias_index[alias_key] = global_label

    words = alias_key.split()
    if len(words) < 2:
        return

    last_name = words[-1]
    if last_name not in last_name_index:
        last_name_index[last_name] = global_label
    elif last_name_index[last_name] != global_label:
        last_name_index[last_name] = ""


def _resolve_global_label(combined_graph: nx.Graph, alias_key: str, fallback_label: str) -> str:
    alias_index = combined_graph.graph.setdefault("alias_key_to_label", {})
    last_name_index = combined_graph.graph.setdefault("last_name_to_label", {})

    if alias_key in alias_index:
        return alias_index[alias_key]

    if len(alias_key.split()) == 1:
        global_label = last_name_index.get(alias_key)
        if global_label:
            alias_index[alias_key] = global_label
            return global_label

    return _display_label(alias_key, fallback_label)


def add_chapter_graph(combined_graph: nx.Graph, chapter_graph: nx.Graph, doc_id: str) -> None:
    """
    Ajoute un graphe de chapitre au graphe global.
    Les personnages sont fusionnes par alias normalise globalement.
    """
    node_to_global_label = {}

    for node_id, data in chapter_graph.nodes(data=True):
        label = data.get("label")
        if not label:
            continue
        names = data.get("names", label)
        alias_key = _global_alias_key(label, names)
        global_label = _resolve_global_label(combined_graph, alias_key, label)
        node_to_global_label[node_id] = global_label

        if not combined_graph.has_node(global_label):
            combined_graph.add_node(
                global_label,
                alias_key=alias_key,
                label=global_label,
                names="",
                chapters_count=0,
                chapters="",
            )
        _register_alias_indexes(combined_graph, alias_key, global_label)

        node_aliases = _split_aliases(combined_graph.nodes[global_label].get("names", ""))
        node_aliases.add(label)
        node_aliases.update(_split_aliases(names))
        combined_graph.nodes[global_label]["names"] = ";".join(sorted(node_aliases))

        chapters = set(filter(None, combined_graph.nodes[global_label].get("chapters", "").split(",")))
        chapters.add(doc_id)
        combined_graph.nodes[global_label]["chapters"] = ",".join(sorted(chapters))
        combined_graph.nodes[global_label]["chapters_count"] = len(chapters)

    for source, target, data in chapter_graph.edges(data=True):
        source_label = node_to_global_label.get(source, _node_label(chapter_graph, source))
        target_label = node_to_global_label.get(target, _node_label(chapter_graph, target))
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


def remove_internal_indexes(graph: nx.Graph) -> None:
    graph.graph.pop("alias_key_to_label", None)
    graph.graph.pop("last_name_to_label", None)


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
    config = build_final_submission_config()
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
    remove_internal_indexes(combined_graph)
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

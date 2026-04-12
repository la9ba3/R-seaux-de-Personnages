import csv
from io import BytesIO
from pathlib import Path
import networkx as nx


def graph_to_graphml_string(graph) -> str:
    """
    Convertit un graphe NetworkX en chaîne GraphML.
    """
    buffer = BytesIO()
    nx.write_graphml(graph, buffer, encoding="utf-8", prettyprint=True)
    graphml_bytes = buffer.getvalue()
    return graphml_bytes.decode("utf-8")


def export_graphml(graph, output_path: str) -> None:
    """
    Exporte le graphe dans un fichier GraphML.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, output_file, encoding="utf-8", prettyprint=True)


def build_submission_row(doc_id: str, graphml_content: str) -> dict:
    """
    Construit une ligne de soumission.
    """
    return {
        "ID": doc_id,
        "graphml": graphml_content,
    }


def export_submission_csv(rows: list[dict], output_path: str) -> None:
    """
    Exporte les lignes de soumission dans un CSV.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["ID", "graphml"])
        writer.writeheader()
        writer.writerows(rows)
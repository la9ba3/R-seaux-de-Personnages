import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import networkx as nx

from graph_builder import build_graph
from export_combined_polarity_graph import add_chapter_graph


class GraphExportTests(unittest.TestCase):
    def test_build_graph_can_export_all_aliases(self) -> None:
        graph = build_graph(
            [
                {
                    "character_id": "char_1",
                    "canonical_name": "R. Daneel Olivaw",
                    "aliases": ["Daneel", "R. Daneel", "R. Daneel Olivaw"],
                }
            ],
            [],
            export_aliases=True,
        )

        self.assertEqual(graph.nodes["char_1"]["label"], "R. Daneel Olivaw")
        self.assertEqual(
            graph.nodes["char_1"]["names"],
            "Daneel;R. Daneel;R. Daneel Olivaw",
        )

    def test_combined_graph_merges_global_aliases(self) -> None:
        first = nx.Graph()
        first.add_node("a", label="Seldon", names="Seldon")

        second = nx.Graph()
        second.add_node("b", label="Hari Seldon", names="Hari Seldon;Harri Seldon")

        combined = nx.Graph()
        add_chapter_graph(combined, first, "paf0")
        add_chapter_graph(combined, second, "paf1")

        self.assertEqual(list(combined.nodes), ["Hari Seldon"])
        self.assertEqual(combined.nodes["Hari Seldon"]["chapters_count"], 2)
        self.assertEqual(
            combined.nodes["Hari Seldon"]["names"],
            "Hari Seldon;Harri Seldon;Seldon",
        )

    def test_combined_graph_reuses_normalized_alias_key(self) -> None:
        first = nx.Graph()
        first.add_node("a", label="Dr Sarton", names="Dr Sarton;Le Dr Sarton")

        second = nx.Graph()
        second.add_node("b", label="Sarton", names="Sarton")

        combined = nx.Graph()
        add_chapter_graph(combined, first, "lca4")
        add_chapter_graph(combined, second, "lca17")

        self.assertEqual(list(combined.nodes), ["Dr Sarton"])
        self.assertEqual(combined.nodes["Dr Sarton"]["chapters_count"], 2)
        self.assertEqual(
            combined.nodes["Dr Sarton"]["names"],
            "Dr Sarton;Le Dr Sarton;Sarton",
        )

    def test_combined_graph_merges_short_form_into_unique_full_name(self) -> None:
        first = nx.Graph()
        first.add_node("a", label="Roj Nemennuh Sarton", names="Roj Nemennuh Sarton")

        second = nx.Graph()
        second.add_node("b", label="Dr Sarton", names="Dr Sarton")

        combined = nx.Graph()
        add_chapter_graph(combined, first, "lca0")
        add_chapter_graph(combined, second, "lca4")

        self.assertEqual(list(combined.nodes), ["Roj Nemennuh Sarton"])
        self.assertEqual(combined.nodes["Roj Nemennuh Sarton"]["chapters_count"], 2)
        self.assertEqual(
            combined.nodes["Roj Nemennuh Sarton"]["names"],
            "Dr Sarton;Roj Nemennuh Sarton",
        )


if __name__ == "__main__":
    unittest.main()

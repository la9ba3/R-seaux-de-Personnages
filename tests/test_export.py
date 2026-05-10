import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graph_builder import build_graph


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


if __name__ == "__main__":
    unittest.main()

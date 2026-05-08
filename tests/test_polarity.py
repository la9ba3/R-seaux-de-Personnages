import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from graph_builder import build_graph
from polarity import enrich_interactions_with_polarity, load_polarity_lexicon, score_context


class PolarityTests(unittest.TestCase):
    def test_score_context_uses_lexicon_and_clamps_score(self) -> None:
        lexicon = {"aider": 2, "respect": 1, "attaquer": -3}

        positive_score, positive_hits = score_context("Alice veut aider Bob avec respect.", lexicon)
        negative_score, negative_hits = score_context("Alice veut attaquer Bob.", {"attaquer": -3})

        self.assertEqual(positive_score, 3)
        self.assertEqual(positive_hits, ["aider", "respect"])
        self.assertEqual(negative_score, -3)
        self.assertEqual(negative_hits, ["attaquer"])

    def test_enrich_interactions_preserves_weight_and_adds_polarity(self) -> None:
        tokens = [
            {"text": "Alice", "index": 0},
            {"text": "aide", "index": 1},
            {"text": "Bob.", "index": 2},
        ]
        mentions = [
            {
                "character_id": "char_a",
                "start_token": 0,
                "end_token": 0,
            },
            {
                "character_id": "char_b",
                "start_token": 2,
                "end_token": 2,
            },
        ]
        interactions = [{"source": "char_a", "target": "char_b", "weight": 4}]

        enriched = enrich_interactions_with_polarity(
            interactions,
            mentions,
            tokens,
            {"aide": 2},
            window_size=5,
            context_window=1,
        )

        self.assertEqual(enriched[0]["weight"], 4)
        self.assertEqual(enriched[0]["polarity"], 2)
        self.assertEqual(enriched[0]["sentiment"], "positive")

        graph = build_graph(
            [
                {"character_id": "char_a", "canonical_name": "Alice"},
                {"character_id": "char_b", "canonical_name": "Bob"},
            ],
            enriched,
        )
        self.assertEqual(graph["char_a"]["char_b"]["weight"], 4)
        self.assertEqual(graph["char_a"]["char_b"]["polarity"], 2)

    def test_project_lexicon_loads_accentless_variants(self) -> None:
        lexicon = load_polarity_lexicon(PROJECT_ROOT / "data" / "polarity" / "dictionnaire_polarite_fr.txt")
        self.assertEqual(lexicon["aimer"], 3)
        self.assertEqual(lexicon["detester"], -3)
        self.assertEqual(lexicon["mepris"], -2)


if __name__ == "__main__":
    unittest.main()

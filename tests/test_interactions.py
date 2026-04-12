import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from interactions import extract_interactions_from_mentions


class InteractionsTests(unittest.TestCase):
    def test_permissive_mode_keeps_single_cooccurrence(self) -> None:
        mentions = [
            {"character_id": "char_a", "start_token": 0},
            {"character_id": "char_b", "start_token": 5},
            {"character_id": "char_c", "start_token": 80},
        ]

        interactions = extract_interactions_from_mentions(
            mentions,
            window_size=10,
            min_edge_weight=1,
        )
        self.assertEqual(len(interactions), 1)
        self.assertEqual(
            (interactions[0]["source"], interactions[0]["target"], interactions[0]["weight"]),
            ("char_a", "char_b", 1),
        )

    def test_weight_two_edge_is_kept(self) -> None:
        mentions = [
            {"character_id": "char_a", "start_token": 0},
            {"character_id": "char_b", "start_token": 5},
            {"character_id": "char_a", "start_token": 20},
            {"character_id": "char_b", "start_token": 25},
        ]

        interactions = extract_interactions_from_mentions(mentions, window_size=10)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["source"], "char_a")
        self.assertEqual(interactions[0]["target"], "char_b")
        self.assertEqual(interactions[0]["weight"], 2)

    def test_expanded_window_recovers_sparse_long_chapter(self) -> None:
        mentions = []
        for index in range(10):
            mentions.append({"character_id": "char_a", "start_token": index * 100})
            mentions.append({"character_id": "char_b", "start_token": index * 100 + 30})

        interactions = extract_interactions_from_mentions(mentions, window_size=25)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["weight"], 10)

    def test_last_resort_keeps_strongest_robust_edge(self) -> None:
        mentions = [
            {"character_id": "char_a", "start_token": 0},
            {"character_id": "char_a", "start_token": 100},
            {"character_id": "char_b", "start_token": 20},
            {"character_id": "char_b", "start_token": 220},
            {"character_id": "char_c", "start_token": 500},
            {"character_id": "char_c", "start_token": 900},
        ]

        interactions = extract_interactions_from_mentions(mentions, window_size=25)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(
            (interactions[0]["source"], interactions[0]["target"]),
            ("char_a", "char_b"),
        )


if __name__ == "__main__":
    unittest.main()

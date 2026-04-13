import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alias_resolution import resolve_aliases, strip_title


class AliasResolutionTests(unittest.TestCase):
    def test_strip_title_supports_extended_french_titles(self) -> None:
        self.assertEqual(strip_title("Docteur Seldon"), "Seldon")
        self.assertEqual(strip_title("Maître Seldon"), "Seldon")
        self.assertEqual(strip_title("M'dame Venabili"), "Venabili")

    def test_resolve_aliases_merges_titled_and_short_forms(self) -> None:
        mentions = [
            {"mention_id": "m1", "text": "Hari Seldon", "start_token": 0, "end_token": 1},
            {"mention_id": "m2", "text": "Hari Seldon", "start_token": 10, "end_token": 11},
            {"mention_id": "m3", "text": "Hari Seldon", "start_token": 20, "end_token": 21},
            {"mention_id": "m4", "text": "Docteur Seldon", "start_token": 30, "end_token": 31},
            {"mention_id": "m5", "text": "Maître Seldon", "start_token": 40, "end_token": 41},
            {"mention_id": "m6", "text": "Seldon", "start_token": 50, "end_token": 50},
        ]

        result = resolve_aliases(mentions)
        self.assertEqual(len(result["characters"]), 1)
        character = result["characters"][0]
        self.assertEqual(character["canonical_name"], "Hari Seldon")
        self.assertEqual(len(character["mention_ids"]), 6)

    def test_ambiguous_short_form_is_not_forced_into_one_character(self) -> None:
        mentions = [
            {"mention_id": "m1", "text": "Elijah Baley", "start_token": 0, "end_token": 1},
            {"mention_id": "m2", "text": "Elijah Baley", "start_token": 10, "end_token": 11},
            {"mention_id": "m3", "text": "Elijah Baley", "start_token": 20, "end_token": 21},
            {"mention_id": "m4", "text": "Bentley Baley", "start_token": 30, "end_token": 31},
            {"mention_id": "m5", "text": "Baley", "start_token": 40, "end_token": 40},
        ]

        result = resolve_aliases(mentions)
        characters = result["characters"]
        self.assertEqual(len(characters), 3)

        by_name = {character["canonical_name"]: character for character in characters}
        self.assertIn("Elijah Baley", by_name)
        self.assertIn("Bentley Baley", by_name)
        self.assertIn("Baley", by_name)
        self.assertEqual(len(by_name["Elijah Baley"]["mention_ids"]), 3)
        self.assertEqual(len(by_name["Bentley Baley"]["mention_ids"]), 1)

    def test_merges_initial_form_into_extended_name(self) -> None:
        mentions = [
            {"mention_id": "m1", "text": "R. Daneel Olivaw", "start_token": 0, "end_token": 2},
            {"mention_id": "m2", "text": "R. Daneel", "start_token": 10, "end_token": 11},
            {"mention_id": "m3", "text": "Daneel", "start_token": 20, "end_token": 20},
        ]

        result = resolve_aliases(mentions)
        self.assertEqual(len(result["characters"]), 1)
        self.assertEqual(len(result["characters"][0]["mention_ids"]), 3)
        self.assertIn("R. Daneel Olivaw", result["characters"][0]["aliases"])

    def test_drops_ambiguous_singleton_when_all_candidates_are_weak(self) -> None:
        mentions = [
            {"mention_id": "m1", "text": "Kiangtow Randa", "start_token": 0, "end_token": 1},
            {"mention_id": "m2", "text": "Lisung Randa", "start_token": 10, "end_token": 11},
            {"mention_id": "m3", "text": "Randa", "start_token": 20, "end_token": 20},
        ]

        result = resolve_aliases(mentions)
        names = sorted(character["canonical_name"] for character in result["characters"])
        self.assertEqual(names, ["Kiangtow Randa", "Lisung Randa"])


if __name__ == "__main__":
    unittest.main()

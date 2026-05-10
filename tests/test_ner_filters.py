import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ner import (
    clean_person_mention_text,
    is_valid_person_mention,
    extract_list_based_person_mentions,
    extract_salvaged_person_mentions,
)


class NerFiltersTests(unittest.TestCase):
    def test_clean_removes_dialog_suffixes(self) -> None:
        self.assertEqual(clean_person_mention_text("Cléon Ier qu’"), "Cléon Ier")
        self.assertEqual(clean_person_mention_text("Hélicon je"), "Hélicon")

    def test_clean_keeps_name_after_comma_prefix(self) -> None:
        self.assertEqual(clean_person_mention_text("Instantanement, Daneel"), "Daneel")

    def test_clean_removes_noisy_leading_word(self) -> None:
        self.assertEqual(clean_person_mention_text("Instantanement R. Daneel"), "R. Daneel")

    def test_rejects_narrative_like_mentions(self) -> None:
        self.assertFalse(is_valid_person_mention("Seldon grimaça"))
        self.assertFalse(is_valid_person_mention("Appelez-moi Davan"))
        self.assertFalse(is_valid_person_mention("Alice retrouva Lucas"))
        self.assertFalse(is_valid_person_mention("Monsieur"))

    def test_accepts_person_like_mentions(self) -> None:
        self.assertTrue(is_valid_person_mention("Hari Seldon"))
        self.assertTrue(is_valid_person_mention("Docteur Venabili"))
        self.assertTrue(is_valid_person_mention("Dors"))

    def test_strict_mode_rejects_known_non_characters(self) -> None:
        self.assertFalse(is_valid_person_mention("Spaciens", strict=True))
        self.assertFalse(is_valid_person_mention("Sacratorium de Mycogène", strict=True))
        self.assertFalse(is_valid_person_mention("GALACTICA2 Étouffant", strict=True))
        self.assertFalse(is_valid_person_mention("Madame le Maire", strict=True))

    def test_salvage_splits_noisy_spacy_entity(self) -> None:
        spacy_mentions = [
            {
                "mention_id": "m_spacy_0001",
                "text": "Alice retrouva Lucas",
                "start_char": 10,
                "end_char": 30,
                "label": "PER",
                "source": "spacy",
            }
        ]
        salvaged = extract_salvaged_person_mentions(spacy_mentions)
        texts = sorted(mention["text"] for mention in salvaged)
        self.assertEqual(texts, ["Alice", "Lucas"])

    def test_list_extraction_uses_anchor(self) -> None:
        text = "Alice retrouva Lucas, Emma, Gabriel et Chloe devant la gare."
        mentions = extract_list_based_person_mentions(text, anchor_words={"alice", "emma"})
        texts = sorted(mention["text"] for mention in mentions)
        self.assertEqual(texts, ["Chloe", "Emma", "Gabriel", "Lucas"])


if __name__ == "__main__":
    unittest.main()

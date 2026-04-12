from __future__ import annotations

from pathlib import Path
import re

import spacy


CORPUS_BLACKLIST = {
    "spacetown",
    "mondes exterieurs",
    "mondes extérieurs",
    "epoque medievale",
    "époque medievale",
    "epoque médiévale",
    "époque médiévale",
    "n m",
    "empire",
    "empire galactique",
    "ere galactique",
    "ère galactique",
    "trantor",
    "helicon",
    "helicon je",
    "dynastie entun",
    "marbre",
    "parc qu",
    "simplement qu",
    "grisnuage qu",
    "qu aurore qu",
    "insinuez vous qu",
    "évidemment qu",
    "evidemment qu",
    "pouvez vous qu",
    "montre qu",
    "je crois",
    "pret",
    "prêt",
    "oui",
    "je n ai",
    "est ce qu",
    "y etiez",
    "y étiez",
    "instint qu",
    "parce qu",
    "n an",
    "pourvu qu",
    "n avez qu",
    "s avise de l utiliser",
}

NARRATIVE_OR_DISCOURSE_WORDS = {
    "grommela",
    "marmonna",
    "grimaca",
    "grimaça",
    "sourit",
    "dit",
    "demanda",
    "repondit",
    "répondit",
    "ajouta",
    "observa",
    "lanca",
    "lança",
    "insinuez",
    "appelez",
    "simplement",
    "evidemment",
    "évidemment",
    "pouvez",
    "prenez",
    "veuillez",
    "incertitude",
    "crois",
    "galopa",
}

PRONOUN_OR_FUNCTION_TAILS = {
    "je",
    "tu",
    "il",
    "elle",
    "nous",
    "vous",
    "ils",
    "elles",
    "qu",
    "que",
    "n",
    "d",
    "l",
    "m",
    "t",
    "s",
    "c",
    "j",
}

TITLE_PATTERNS = [
    r"M\.",
    r"Mme",
    r"Mlle",
    r"Monsieur",
    r"Madame",
    r"Docteur",
    r"Dr",
    r"Professeur",
    r"Prof",
    r"Maitre",
    r"Maître",
    r"M['’]dame",
]

ROLE_PATTERNS = [
    r"Maire",
    r"Empereur",
    r"Ministre",
    r"Conseiller",
    r"Président",
    r"Présidente",
    r"Chancelier",
    r"Ambassadeur",
    r"Commissaire",
    r"Inspecteur",
]

NAME_TOKEN_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*|[IVXLCDM]+|[0-9]+(?:er|e)?"
)

TITLE_ONLY_WORDS = {
    "m",
    "mme",
    "mlle",
    "monsieur",
    "madame",
    "docteur",
    "dr",
    "professeur",
    "prof",
    "maitre",
    "maître",
}

ALLOWED_LOWER_NAME_PARTS = {
    "de",
    "du",
    "des",
    "d",
    "la",
    "le",
    "l",
    "van",
    "von",
    "di",
    "da",
    "del",
    "bin",
    "al",
    "el",
}

CAPITALIZED_NAME_PATTERN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+"
CAPITALIZED_NAME_RE = re.compile(CAPITALIZED_NAME_PATTERN)
ENUMERATION_NAME_RE = re.compile(
    rf"\b{CAPITALIZED_NAME_PATTERN}(?:\s*,\s*{CAPITALIZED_NAME_PATTERN})+\s*(?:,\s*)?(?:et|ou)\s+{CAPITALIZED_NAME_PATTERN}\b"
)


def _normalize_token(text: str) -> str:
    normalized = text.lower().strip().replace("’", "'")
    normalized = re.sub(r"[^a-zà-öø-ÿ0-9]", "", normalized)
    return normalized


def _normalize_name_part(text: str) -> str:
    cleaned = text.strip().replace("’", "'")
    cleaned = re.sub(r"^[^A-Za-zÀ-ÖØ-öø-ÿ]+", "", cleaned)
    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'\-]+$", "", cleaned)
    return cleaned


def _is_allowed_lower_part(raw_part: str, normalized_part: str) -> bool:
    if normalized_part in ALLOWED_LOWER_NAME_PARTS:
        return True
    # Cas d'Artagnan, l'Hermite...
    if re.match(r"^[dl]['’][A-ZÀ-ÖØ-Þ]", raw_part):
        return True
    return False


def load_antidictionary(path: str) -> set[str]:
    """
    Charge un antidictionnaire depuis un fichier texte.
    Ignore :
    - les lignes vides
    - les lignes de commentaire commençant par '#'
    """
    file_path = Path(path)
    if not file_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent
        file_path = project_root / path

    if not file_path.exists():
        return set()

    words = set()
    with file_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.add(line.lower())
    return words


ANTI_DICTIONARY = load_antidictionary("fonctionnels_fr.txt")


def clean_person_mention_text(text: str) -> str:
    """
    Nettoie les mentions candidates en supprimant des artefacts de dialogue.
    """
    cleaned = text.strip()

    cleaned = re.sub(r"^[\"'«»“”()\[\]{}.,;:!?]+", "", cleaned)
    cleaned = re.sub(r"[\"'«»“”()\[\]{}.,;:!?]+$", "", cleaned)

    cleaned = re.sub(r"\s+(?:[ndlstcjqu]|qu)['’]\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    while len(words) > 1:
        tail = _normalize_token(words[-1])
        if not tail:
            words.pop()
            continue
        if tail in PRONOUN_OR_FUNCTION_TAILS or tail in ANTI_DICTIONARY:
            words.pop()
            continue
        break

    return " ".join(words).strip()


def normalize_for_antidictionary(text: str) -> str:
    """
    Normalise légèrement une mention pour comparaison avec les listes de rejet.
    """
    normalized = clean_person_mention_text(text).strip().lower()
    normalized = re.sub(r"[^\w\sà-öø-ÿ]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def has_title(text: str) -> bool:
    title_regex = r"^(?:%s)\b" % "|".join(TITLE_PATTERNS)
    return re.search(title_regex, text.strip()) is not None


def is_role_mention(text: str) -> bool:
    role_regex = r"(?:%s)" % "|".join(ROLE_PATTERNS)
    pattern = re.compile(rf"^(?:le|la|l['’]|Le|La|L['’])\s*{role_regex}$")
    return pattern.search(text.strip()) is not None


def starts_like_proper_name(text: str) -> bool:
    stripped = text.strip()
    if re.match(r"^[A-ZÀ-ÖØ-Þ]", stripped):
        return True
    if re.match(r"^[A-ZÀ-ÖØ-Þ]\.$", stripped):
        return True
    if re.match(r"^[A-ZÀ-ÖØ-Þ]\.\s+[A-ZÀ-ÖØ-Þ]", stripped):
        return True
    return False


def contains_narrative_or_discourse_word(text: str) -> bool:
    for word in NAME_TOKEN_RE.findall(text):
        normalized_word = _normalize_token(word)
        if normalized_word in NARRATIVE_OR_DISCOURSE_WORDS:
            return True
        for chunk in re.split(r"[-'’]", word):
            if _normalize_token(chunk) in NARRATIVE_OR_DISCOURSE_WORDS:
                return True
    return False


def extract_name_tokens(text: str) -> list[str]:
    return NAME_TOKEN_RE.findall(text)


def has_plausible_name_shape(text: str) -> bool:
    cleaned = clean_person_mention_text(text)
    if not cleaned:
        return False

    raw_parts = [part for part in cleaned.split() if part]
    parts = [_normalize_name_part(part) for part in raw_parts]
    parts = [part for part in parts if part]
    if not parts:
        return False

    normalized_parts = [_normalize_token(part).rstrip(".") for part in parts]
    if len(normalized_parts) == 1 and normalized_parts[0] in TITLE_ONLY_WORDS:
        return False

    for raw_part, normalized in zip(raw_parts, normalized_parts):
        if not normalized:
            return False
        if raw_part[0].islower() and not _is_allowed_lower_part(raw_part, normalized):
            return False

    return True


def load_ner_model(model_name: str):
    """
    Charge un modèle spaCy pour la reconnaissance d'entités nommées.
    """
    return spacy.load(model_name)


def extract_person_mentions(text: str, model) -> list[dict]:
    """
    Extrait les entités de type personne via spaCy.
    Retourne une liste de mentions avec offsets caractères.
    """
    document = model(text)
    mentions = []

    mention_count = 1
    for entity in document.ents:
        if entity.label_ != "PER":
            continue
        mentions.append(
            {
                "mention_id": f"m_spacy_{mention_count:04d}",
                "text": entity.text,
                "start_char": entity.start_char,
                "end_char": entity.end_char,
                "label": entity.label_,
                "source": "spacy",
            }
        )
        mention_count += 1

    return mentions


def extract_rule_based_person_mentions(text: str) -> list[dict]:
    """
    Extrait des mentions de personnes par règles simples.
    """
    mentions = []
    mention_count = 1

    title_regex = r"(?:%s)" % "|".join(TITLE_PATTERNS)
    pattern_title_name = re.compile(
        rf"\b({title_regex})\s+([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)*)"
    )

    for match in pattern_title_name.finditer(text):
        mentions.append(
            {
                "mention_id": f"m_rule_{mention_count:04d}",
                "text": match.group(0).strip(),
                "start_char": match.start(),
                "end_char": match.end(),
                "label": "PER",
                "source": "rule_title",
            }
        )
        mention_count += 1

    role_regex = r"(?:%s)" % "|".join(ROLE_PATTERNS)
    pattern_role = re.compile(rf"\b((?:le|la|l['’]|Le|La|L['’])\s*({role_regex}))\b")

    for match in pattern_role.finditer(text):
        mentions.append(
            {
                "mention_id": f"m_rule_{mention_count:04d}",
                "text": match.group(1).strip(),
                "start_char": match.start(1),
                "end_char": match.end(1),
                "label": "PER",
                "source": "rule_role",
            }
        )
        mention_count += 1

    return mentions


def deduplicate_mentions(mentions: list[dict]) -> list[dict]:
    """
    Supprime les doublons exacts sur (text, start_char, end_char).
    """
    seen = set()
    deduped = []

    for mention in mentions:
        key = (
            mention["text"].strip(),
            mention["start_char"],
            mention["end_char"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mention)

    return deduped


def build_anchor_words(mentions: list[dict]) -> set[str]:
    anchor_words = set()
    for mention in mentions:
        for match in CAPITALIZED_NAME_RE.finditer(mention["text"]):
            anchor_words.add(match.group(0).lower())
    return anchor_words


def extract_salvaged_person_mentions(spacy_mentions: list[dict]) -> list[dict]:
    """
    Découpe les mentions spaCy bruitées en noms propres capitalisés.
    Exemple: "Alice retrouva Lucas" -> "Alice", "Lucas".
    """
    mentions = []
    mention_count = 1

    for mention in spacy_mentions:
        mention_text = mention["text"]
        if is_valid_person_mention(mention_text):
            continue

        for match in CAPITALIZED_NAME_RE.finditer(mention_text):
            candidate = match.group(0)
            if not is_valid_person_mention(candidate):
                continue
            mentions.append(
                {
                    "mention_id": f"m_salv_{mention_count:04d}",
                    "text": candidate,
                    "start_char": mention["start_char"] + match.start(),
                    "end_char": mention["start_char"] + match.end(),
                    "label": "PER",
                    "source": "rule_salvage",
                }
            )
            mention_count += 1

    return mentions


def extract_list_based_person_mentions(text: str, anchor_words: set[str]) -> list[dict]:
    """
    Extrait les prénoms dans les énumérations de type "X, Y, Z et W".
    Le bloc n'est retenu que si au moins un item est déjà ancré par spaCy.
    """
    mentions = []
    mention_count = 1

    for list_match in ENUMERATION_NAME_RE.finditer(text):
        list_text = list_match.group(0)
        items = []
        for item_match in CAPITALIZED_NAME_RE.finditer(list_text):
            item_text = item_match.group(0)
            items.append(
                (
                    item_text,
                    list_match.start() + item_match.start(),
                    list_match.start() + item_match.end(),
                )
            )

        if len(items) < 3:
            continue
        if not any(item_text.lower() in anchor_words for item_text, _, _ in items):
            continue

        for item_text, start_char, end_char in items:
            if not is_valid_person_mention(item_text):
                continue
            mentions.append(
                {
                    "mention_id": f"m_list_{mention_count:04d}",
                    "text": item_text,
                    "start_char": start_char,
                    "end_char": end_char,
                    "label": "PER",
                    "source": "rule_list",
                }
            )
            mention_count += 1

    return mentions


def build_enriched_person_mentions(
    text: str,
    spacy_mentions: list[dict],
    rule_mentions: list[dict],
) -> list[dict]:
    """
    Combine spaCy + règles + heuristiques d'enrichissement.
    """
    anchor_words = build_anchor_words(spacy_mentions)
    salvaged_mentions = extract_salvaged_person_mentions(spacy_mentions)
    list_mentions = extract_list_based_person_mentions(text, anchor_words)
    return deduplicate_mentions(spacy_mentions + rule_mentions + salvaged_mentions + list_mentions)


def is_valid_person_mention(text: str) -> bool:
    """
    Vérifie si une mention ressemble à un nom de personne exploitable.
    """
    if not text:
        return False

    cleaned = clean_person_mention_text(text)
    if not cleaned:
        return False

    normalized = normalize_for_antidictionary(cleaned)
    if not normalized:
        return False

    if normalized in CORPUS_BLACKLIST:
        return False

    if normalized in ANTI_DICTIONARY:
        return False

    if len(cleaned) < 2:
        return False

    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", cleaned):
        return False

    if re.fullmatch(r"[\W_]+", cleaned):
        return False

    if contains_narrative_or_discourse_word(cleaned):
        return False

    if not has_plausible_name_shape(cleaned):
        return False

    words = extract_name_tokens(cleaned)
    if not words:
        return False

    normalized_words = [_normalize_token(word) for word in words]
    if any(word in PRONOUN_OR_FUNCTION_TAILS for word in normalized_words):
        return False

    if len(words) > 1 and normalized_words[-1] in ANTI_DICTIONARY:
        return False

    noisy_fragments = {"n", "d", "l", "m", "t", "s", "c", "j", "qu"}
    if any(word in noisy_fragments for word in normalized_words):
        return False

    if has_title(cleaned):
        return True

    if is_role_mention(cleaned):
        return True

    if len(words) >= 2:
        return starts_like_proper_name(cleaned)

    single_word = words[0]
    if len(single_word) < 3:
        return False

    if not starts_like_proper_name(cleaned):
        return False

    return True


def filter_person_mentions(mentions: list[dict]) -> list[dict]:
    """
    Filtre les mentions de personnes pour supprimer les faux positifs évidents.
    """
    filtered = []

    for mention in mentions:
        text = clean_person_mention_text(mention["text"])
        if not text:
            continue

        normalized_text = normalize_for_antidictionary(text)
        if normalized_text in CORPUS_BLACKLIST:
            continue

        if not is_valid_person_mention(text):
            continue

        filtered.append(
            {
                "mention_id": mention["mention_id"],
                "text": text,
                "start_char": mention["start_char"],
                "end_char": mention["end_char"],
                "label": mention["label"],
                "source": mention.get("source", "unknown"),
            }
        )

    return filtered


def align_mentions_to_tokens(mentions: list[dict], tokens: list[dict]) -> list[dict]:
    """
    Aligne les mentions extraites sur les tokens de preprocessing.
    """
    aligned_mentions = []

    token_positions = []
    current_pos = 0

    for token in tokens:
        token_text = token["text"]
        start = current_pos
        end = start + len(token_text)

        token_positions.append(
            {
                "index": token["index"],
                "text": token_text,
                "start_char": start,
                "end_char": end,
            }
        )
        current_pos = end + 1

    for mention in mentions:
        mention_start = mention["start_char"]
        mention_end = mention["end_char"]

        matched_tokens = []
        for token in token_positions:
            token_start = token["start_char"]
            token_end = token["end_char"]

            if token_end > mention_start and token_start < mention_end:
                matched_tokens.append(token["index"])

        if not matched_tokens:
            continue

        aligned_mentions.append(
            {
                "mention_id": mention["mention_id"],
                "text": mention["text"],
                "start_token": min(matched_tokens),
                "end_token": max(matched_tokens),
                "label": mention["label"],
                "source": mention.get("source", "unknown"),
            }
        )

    return aligned_mentions

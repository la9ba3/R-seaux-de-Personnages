from __future__ import annotations

from pathlib import Path
import re
import unicodedata

from utils import sort_pair


TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*")
SENTENCE_END_RE = re.compile(r"[.!?;:]$")


def _repair_mojibake(text: str) -> str:
    """
    Corrige les artefacts frequents de type 'mÃ©pris' quand c'est possible.
    """
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_polarity_term(text: str) -> str:
    candidate = _repair_mojibake(text.strip().lower())
    candidate = candidate.replace("’", "'")
    candidate = _strip_accents(candidate)
    candidate = re.sub(r"[^a-z0-9'\-\s]", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate.strip()


def _term_variants(text: str) -> set[str]:
    variants = set()
    for candidate in {text, _repair_mojibake(text)}:
        normalized = normalize_polarity_term(candidate)
        if normalized:
            variants.add(normalized)
            variants.add(normalized.replace("'", " "))
            variants.add(normalized.replace("-", " "))

    expanded = set(variants)
    for variant in variants:
        if " " in variant:
            continue
        if variant.endswith("er") and len(variant) > 4:
            stem = variant[:-2]
            expanded.update(
                {
                    f"{stem}e",
                    f"{stem}es",
                    f"{stem}ent",
                    f"{stem}ait",
                    f"{stem}aient",
                    f"{stem}a",
                    f"{stem}e",
                }
            )
        elif variant.endswith("ir") and len(variant) > 4:
            stem = variant[:-2]
            expanded.update({f"{stem}it", f"{stem}issent", f"{stem}i"})

    return {variant.strip() for variant in expanded if variant.strip()}


def load_polarity_lexicon(path: str | Path) -> dict[str, int]:
    """
    Charge un dictionnaire de polarite au format 'terme : score'.
    Les scores sont bornes dans [-3, 3].
    """
    lexicon_path = Path(path)
    if not lexicon_path.exists():
        return {}

    lexicon: dict[str, int] = {}
    with lexicon_path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"Ligne de polarite invalide {line_number}: {raw_line.rstrip()}")

            term, raw_score = line.split(":", maxsplit=1)
            score = int(raw_score.strip())
            score = max(-3, min(3, score))
            for variant in _term_variants(term):
                lexicon[variant] = score

    return lexicon


def _context_bounds(tokens: list[dict], left: int, right: int, padding: int) -> tuple[int, int]:
    start = max(0, left - padding)
    end = min(len(tokens) - 1, right + padding)

    while start > 0 and not SENTENCE_END_RE.search(tokens[start - 1]["text"]):
        if left - start >= padding:
            break
        start -= 1

    while end < len(tokens) - 1 and not SENTENCE_END_RE.search(tokens[end]["text"]):
        if end - right >= padding:
            break
        end += 1

    return start, end


def _context_text(tokens: list[dict], start: int, end: int) -> str:
    return " ".join(token["text"] for token in tokens[start : end + 1])


def score_context(context: str, lexicon: dict[str, int]) -> tuple[int, list[str]]:
    """
    Calcule un score discret [-3, 3] pour un contexte textuel.
    """
    if not context or not lexicon:
        return 0, []

    normalized_context = normalize_polarity_term(context)
    token_counts: dict[str, int] = {}
    for token in TOKEN_RE.findall(context):
        for variant in _term_variants(token):
            token_counts[variant] = token_counts.get(variant, 0) + 1

    total = 0
    hits = []
    for term, score in lexicon.items():
        if " " in term:
            if re.search(rf"\b{re.escape(term)}\b", normalized_context):
                total += score
                hits.append(term)
        elif term in token_counts:
            total += score * token_counts[term]
            hits.append(term)

    return max(-3, min(3, total)), sorted(set(hits))


def _iter_close_mention_pairs(
    resolved_mentions: list[dict],
    window_size: int,
):
    sorted_mentions = sorted(resolved_mentions, key=lambda mention: mention["start_token"])
    for i, first in enumerate(sorted_mentions):
        for second in sorted_mentions[i + 1 :]:
            if second["start_token"] - first["start_token"] > window_size:
                break
            if first["character_id"] == second["character_id"]:
                continue
            yield first, second


def sentiment_label(score: int) -> str:
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def enrich_interactions_with_polarity(
    interactions: list[dict],
    resolved_mentions: list[dict],
    tokens: list[dict],
    lexicon: dict[str, int],
    window_size: int,
    context_window: int = 8,
) -> list[dict]:
    """
    Ajoute une polarite aux interactions sans modifier leur poids de cooccurrence.
    """
    if not interactions:
        return []

    allowed_pairs = {
        sort_pair(interaction["source"], interaction["target"])
        for interaction in interactions
    }
    pair_scores = {pair: 0 for pair in allowed_pairs}
    pair_hits = {pair: set() for pair in allowed_pairs}

    for first, second in _iter_close_mention_pairs(resolved_mentions, window_size):
        pair = sort_pair(first["character_id"], second["character_id"])
        if pair not in allowed_pairs:
            continue

        left = min(first["start_token"], second["start_token"])
        right = max(first["end_token"], second["end_token"])
        start, end = _context_bounds(tokens, left, right, context_window)
        score, hits = score_context(_context_text(tokens, start, end), lexicon)

        pair_scores[pair] += score
        pair_hits[pair].update(hits)

    enriched = []
    for interaction in interactions:
        pair = sort_pair(interaction["source"], interaction["target"])
        polarity = max(-3, min(3, pair_scores.get(pair, 0)))
        enriched_interaction = dict(interaction)
        enriched_interaction["polarity"] = polarity
        enriched_interaction["sentiment"] = sentiment_label(polarity)
        enriched_interaction["polarity_width"] = abs(polarity)
        enriched_interaction["polarity_evidence"] = ", ".join(sorted(pair_hits.get(pair, set())))
        enriched.append(enriched_interaction)

    return enriched

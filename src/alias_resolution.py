from __future__ import annotations

import re
import unicodedata


TITLE_PATTERNS = [
    r"^Le\s+",
    r"^La\s+",
    r"^L['’]\s*",
    r"^M\.\s+",
    r"^Mme\s+",
    r"^Mlle\s+",
    r"^Monsieur\s+",
    r"^Madame\s+",
    r"^Docteur\s+",
    r"^Dr\s+",
    r"^Professeur\s+",
    r"^Prof\s+",
    r"^Maitre\s+",
    r"^Maître\s+",
    r"^Maitresse\s+",
    r"^Maîtresse\s+",
    r"^M['’]dame\s+",
]

KNOWN_ALIAS_TARGETS = {
    "baley": "elijah baley",
    "daneel": "r daneel olivaw",
    "daneel olivaw": "r daneel olivaw",
    "demerzel": "eto demerzel",
    "dors": "dors venabili",
    "enderby": "julius enderby",
    "eto demerzel": "eto demerzel",
    "lije baley": "elijah baley",
    "maitresse venabili": "dors venabili",
    "maîtresse venabili": "dors venabili",
    "maître venabili": "dors venabili",
    "r daneel": "r daneel olivaw",
    "r daneel olivaw": "r daneel olivaw",
}

KNOWN_CANONICAL_DISPLAY = {
    "elijah baley": "Elijah Baley",
    "dors venabili": "Dors Venabili",
    "eto demerzel": "Eto Demerzel",
    "julius enderby": "Julius Enderby",
    "r daneel olivaw": "R. Daneel Olivaw",
}


def fold_alias_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower().strip())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    without_accents = without_accents.replace("â€™", "'").replace("’", "'")
    without_accents = re.sub(r"[^a-z0-9'\-\s]", " ", without_accents)
    without_accents = re.sub(r"['\-]", " ", without_accents)
    without_accents = re.sub(r"\s+", " ", without_accents)
    return without_accents.strip()


def strip_title(name: str) -> str:
    """
    Retire un titre en début de mention.
    """
    cleaned = name.strip()

    changed = True
    while changed:
        changed = False
        for pattern in TITLE_PATTERNS:
            new_value = re.sub(pattern, "", cleaned).strip()
            if new_value != cleaned:
                cleaned = new_value
                changed = True

    return cleaned


def is_title_form(name: str) -> bool:
    for pattern in TITLE_PATTERNS:
        if re.match(pattern, name.strip()):
            return True
    return False


def normalize_mention(mention: str) -> str:
    """
    Normalise une mention pour faciliter le regroupement.
    """
    mention = strip_title(mention)
    return fold_alias_key(mention)


def choose_canonical_name(alias_group: list[str], normalized_key: str | None = None) -> str:
    """
    Choisit un canonical_name stable et lisible pour l'export.
    """
    if not alias_group:
        return ""

    if normalized_key in KNOWN_CANONICAL_DISPLAY:
        return KNOWN_CANONICAL_DISPLAY[normalized_key]

    def cleaned(alias: str) -> str:
        return strip_title(alias).strip()

    def has_bad_chars(alias: str) -> bool:
        return re.search(r"[!?;:/\\]", alias) is not None

    def is_clean_token(token: str) -> bool:
        return re.match(r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*$", token) is not None

    def quality_score(alias: str) -> tuple[int, int, int, int, str]:
        base = cleaned(alias)
        words = [word for word in base.split() if word]
        word_count = len(words)

        with_title_penalty = 1 if is_title_form(alias) else 0

        if word_count == 2:
            count_penalty = 0
        elif word_count == 3:
            count_penalty = 1
        elif word_count == 1:
            count_penalty = 2
        else:
            count_penalty = 3

        cleanliness_penalty = 0 if words and all(is_clean_token(word) for word in words) else 1
        length_penalty = len(base)
        return (
            with_title_penalty,
            count_penalty,
            cleanliness_penalty,
            length_penalty,
            base,
        )

    plausible_aliases = [alias for alias in alias_group if not has_bad_chars(alias)]
    if not plausible_aliases:
        plausible_aliases = alias_group[:]

    return min(plausible_aliases, key=quality_score)


def build_initial_groups(mentions: list[dict]) -> dict:
    """
    Regroupement exact par forme normalisée.
    """
    groups = {}
    for mention in mentions:
        normalized = normalize_mention(mention["text"])
        if not normalized:
            continue
        groups.setdefault(normalized, []).append(mention)
    return groups


def apply_known_alias_targets(groups: dict) -> dict:
    """
    Regroupe quelques alias fréquents du corpus vers une clé canonique connue.
    """
    merged = {}
    for key, values in groups.items():
        target = KNOWN_ALIAS_TARGETS.get(key, key)
        merged.setdefault(target, []).extend(values)
    return merged


def merge_groups_by_last_name(groups: dict) -> dict:
    """
    Fusionne un singleton vers un nom complet unique partageant le même nom.
    """
    normalized_keys = list(groups.keys())
    merged = {key: list(values) for key, values in groups.items()}

    long_forms = [key for key in normalized_keys if len(key.split()) >= 2]
    short_forms = [key for key in normalized_keys if len(key.split()) == 1]

    for short_form in short_forms:
        if short_form not in merged:
            continue

        targets = []
        for long_form in long_forms:
            if long_form not in merged:
                continue
            if long_form.split()[-1] == short_form:
                targets.append(long_form)

        if len(targets) == 1:
            target = targets[0]
            merged[target].extend(merged[short_form])
            del merged[short_form]

    return merged


def merge_groups_by_first_name(groups: dict) -> dict:
    """
    Fusionne un singleton vers un nom complet unique partageant le prénom.
    """
    normalized_keys = list(groups.keys())
    merged = {key: list(values) for key, values in groups.items()}

    long_forms = [key for key in normalized_keys if len(key.split()) >= 2]
    short_forms = [key for key in normalized_keys if len(key.split()) == 1]

    for short_form in short_forms:
        if short_form not in merged:
            continue

        targets = []
        for long_form in long_forms:
            if long_form not in merged:
                continue
            if long_form.split()[0] == short_form:
                targets.append(long_form)

        if len(targets) == 1:
            target = targets[0]
            merged[target].extend(merged[short_form])
            del merged[short_form]

    return merged


def merge_groups_by_initial_prefix(groups: dict) -> dict:
    """
    Fusionne une forme courte "R Daneel" vers "R Daneel Olivaw" si la cible est unique.
    """
    normalized_keys = list(groups.keys())
    merged = {key: list(values) for key, values in groups.items()}

    short_forms = [
        key
        for key in normalized_keys
        if len(key.split()) == 2 and len(key.split()[0]) == 1
    ]
    long_forms = [key for key in normalized_keys if len(key.split()) >= 3]

    for short_form in short_forms:
        if short_form not in merged:
            continue

        short_words = short_form.split()
        initial = short_words[0]
        pivot = short_words[1]
        targets = []

        for long_form in long_forms:
            if long_form not in merged:
                continue

            long_words = long_form.split()
            if len(long_words[0]) == 1 and long_words[0] == initial and long_words[1] == pivot:
                targets.append(long_form)

        if len(targets) == 1:
            target = targets[0]
            merged[target].extend(merged[short_form])
            del merged[short_form]

    return merged


def levenshtein_distance(a: str, b: str) -> int:
    """
    Calcule la distance de Levenshtein entre deux chaînes.
    """
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if char_a == char_b else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def is_strong_anchor(normalized_name: str) -> bool:
    words = normalized_name.split()
    if len(words) >= 2:
        return True
    if len(words) == 1 and len(words[0]) >= 6:
        return True
    return False


def merge_groups_by_similarity(groups: dict) -> dict:
    """
    Fusion fuzzy prudente vers des ancres fortes.
    """
    normalized_keys = list(groups.keys())
    merged = {key: list(values) for key, values in groups.items()}

    short_forms = [key for key in normalized_keys if len(key.split()) == 1]
    anchors = [key for key in normalized_keys if is_strong_anchor(key)]

    for short_form in short_forms:
        if short_form not in merged or len(short_form) < 4:
            continue

        candidates = []
        for anchor in anchors:
            if anchor not in merged or anchor == short_form:
                continue

            anchor_words = anchor.split()

            if short_form in anchor_words:
                candidates.append((anchor, 0))
                continue

            first_word = anchor_words[0]
            last_word = anchor_words[-1]
            best_dist = min(
                levenshtein_distance(short_form, first_word),
                levenshtein_distance(short_form, last_word),
            )

            if len(anchor_words) <= 2:
                best_dist = min(best_dist, levenshtein_distance(short_form, anchor))

            if best_dist <= 1:
                candidates.append((anchor, best_dist))

        if not candidates:
            continue

        candidates.sort(key=lambda item: (item[1], len(item[0].split()), len(item[0]), item[0]))
        best_target, best_score = candidates[0]

        same_score_targets = [target for target, score in candidates if score == best_score]
        if len(same_score_targets) == 1 and best_target in merged:
            merged[best_target].extend(merged[short_form])
            del merged[short_form]

    return merged


def merge_groups_by_dominant_anchor(groups: dict) -> dict:
    """
    Fusionne une forme courte vers une ancre dominante quand l'ambiguïté est faible.
    """
    normalized_keys = list(groups.keys())
    merged = {key: list(values) for key, values in groups.items()}

    long_forms = [key for key in normalized_keys if len(key.split()) >= 2]
    short_forms = [key for key in normalized_keys if len(key.split()) == 1]

    for short_form in short_forms:
        if short_form not in merged:
            continue

        candidates = []
        for long_form in long_forms:
            if long_form not in merged:
                continue
            words = long_form.split()
            if short_form == words[0] or short_form == words[-1]:
                candidates.append(long_form)

        if len(candidates) <= 1:
            continue

        ranked = sorted(
            candidates,
            key=lambda candidate: len(merged[candidate]),
            reverse=True,
        )
        top = ranked[0]
        top_count = len(merged[top])
        second_count = len(merged[ranked[1]])

        if top_count >= 3 and top_count >= (2 * second_count):
            merged[top].extend(merged[short_form])
            del merged[short_form]

    return merged


def resolve_aliases(mentions: list[dict], use_known_aliases: bool = False) -> dict:
    """
    Résolution d'alias en plusieurs étapes.
    """
    groups = build_initial_groups(mentions)
    if use_known_aliases:
        groups = apply_known_alias_targets(groups)
    groups = merge_groups_by_last_name(groups)
    groups = merge_groups_by_first_name(groups)
    groups = merge_groups_by_initial_prefix(groups)
    groups = merge_groups_by_similarity(groups)
    if use_known_aliases:
        groups = apply_known_alias_targets(groups)

    resolved_mentions = []
    characters = []

    character_count = 1

    for normalized_key, mention_group in groups.items():
        character_id = f"char_{character_count:04d}"

        alias_texts = sorted({mention["text"] for mention in mention_group})
        canonical_name = choose_canonical_name(alias_texts, normalized_key=normalized_key)
        mention_ids = [mention["mention_id"] for mention in mention_group]

        characters.append(
            {
                "character_id": character_id,
                "canonical_name": canonical_name,
                "aliases": alias_texts,
                "mention_ids": mention_ids,
            }
        )

        for mention in mention_group:
            resolved_mentions.append(
                {
                    "mention_id": mention["mention_id"],
                    "text": mention["text"],
                    "start_token": mention["start_token"],
                    "end_token": mention["end_token"],
                    "character_id": character_id,
                    "canonical_name": canonical_name,
                }
            )

        character_count += 1

    return {
        "resolved_mentions": resolved_mentions,
        "characters": characters,
    }

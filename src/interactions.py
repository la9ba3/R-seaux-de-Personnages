from __future__ import annotations

from utils import sort_pair


def are_mentions_close(m1: dict, m2: dict, window_size: int = 25) -> bool:
    """
    Verifie si deux mentions sont a une distance <= window_size.
    """
    distance = abs(m1["start_token"] - m2["start_token"])
    return distance <= window_size


def _count_mentions_by_character(resolved_mentions: list[dict]) -> dict[str, int]:
    counts = {}
    for mention in resolved_mentions:
        character_id = mention["character_id"]
        counts[character_id] = counts.get(character_id, 0) + 1
    return counts


def _build_cooccurrences(
    sorted_mentions: list[dict],
    window_size: int,
) -> dict[tuple[str, str], int]:
    cooccurrences = {}

    for i in range(len(sorted_mentions)):
        m1 = sorted_mentions[i]
        for j in range(i + 1, len(sorted_mentions)):
            m2 = sorted_mentions[j]

            if m2["start_token"] - m1["start_token"] > window_size:
                break

            char_1 = m1["character_id"]
            char_2 = m2["character_id"]
            if char_1 == char_2:
                continue

            if are_mentions_close(m1, m2, window_size):
                pair = sort_pair(char_1, char_2)
                cooccurrences[pair] = cooccurrences.get(pair, 0) + 1

    return cooccurrences


def _filter_interactions(
    cooccurrences: dict[tuple[str, str], int],
    character_counts: dict[str, int],
    min_edge_weight: int,
    min_mentions_for_weight1: int,
) -> list[dict]:
    interactions = []

    for (source, target), weight in cooccurrences.items():
        source_count = character_counts.get(source, 0)
        target_count = character_counts.get(target, 0)

        keep_edge = False
        if weight >= min_edge_weight:
            keep_edge = True
        elif (
            min_edge_weight == 2
            and weight == 1
            and source_count >= min_mentions_for_weight1
            and target_count >= min_mentions_for_weight1
        ):
            # Regle stricte historique.
            keep_edge = True

        if not keep_edge:
            continue

        interactions.append(
            {
                "source": source,
                "target": target,
                "weight": weight,
            }
        )

    interactions.sort(key=lambda edge: (edge["source"], edge["target"]))
    return interactions


def extract_interactions_from_mentions(
    resolved_mentions: list[dict],
    window_size: int = 25,
    min_edge_weight: int = 2,
    min_mentions_for_weight1: int = 2,
) -> list[dict]:
    """
    Construit les interactions ponderees entre personnages a partir des mentions resolues.

    Mode strict (historique):
    - min_edge_weight=2 : garde les aretes de poids >= 2
    - plus une exception sur poids 1 si chaque personnage a >= min_mentions_for_weight1

    Mode permissif (demo/test):
    - min_edge_weight=1 : garde toutes les cooccurrences detectees.

    Fallbacks:
    - si aucune arete n'est conservee sur un chapitre riche en mentions,
      on elargit la fenetre de cooccurrence
    - en dernier recours, on garde la meilleure arete robuste (poids max)
    """
    if len(resolved_mentions) < 2:
        return []

    sorted_mentions = sorted(resolved_mentions, key=lambda mention: mention["start_token"])
    character_counts = _count_mentions_by_character(sorted_mentions)

    cooccurrences = _build_cooccurrences(sorted_mentions, window_size)
    interactions = _filter_interactions(
        cooccurrences,
        character_counts,
        min_edge_weight=min_edge_weight,
        min_mentions_for_weight1=min_mentions_for_weight1,
    )

    if not interactions and len(resolved_mentions) >= 20:
        expanded_window = max(window_size + 10, int(window_size * 1.6))
        if expanded_window > window_size:
            expanded_cooccurrences = _build_cooccurrences(sorted_mentions, expanded_window)
            expanded_interactions = _filter_interactions(
                expanded_cooccurrences,
                character_counts,
                min_edge_weight=min_edge_weight,
                min_mentions_for_weight1=min_mentions_for_weight1,
            )
            if expanded_interactions:
                return expanded_interactions
            cooccurrences = expanded_cooccurrences

    if not interactions and cooccurrences:
        robust_edges = [
            ((source, target), weight)
            for (source, target), weight in cooccurrences.items()
            if character_counts.get(source, 0) >= 2 and character_counts.get(target, 0) >= 2
        ]
        if robust_edges:
            robust_edges.sort(
                key=lambda item: (
                    -item[1],
                    -(character_counts[item[0][0]] + character_counts[item[0][1]]),
                    item[0][0],
                    item[0][1],
                )
            )
            (source, target), weight = robust_edges[0]
            return [{"source": source, "target": target, "weight": weight}]

    return interactions

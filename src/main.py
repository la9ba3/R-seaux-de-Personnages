from config import get_default_config, validate_config
from preprocessing import preprocess_document
from ner import (
    load_ner_model,
    extract_person_mentions,
    extract_rule_based_person_mentions,
    build_enriched_person_mentions,
    filter_person_mentions,
    align_mentions_to_tokens,
)
from alias_resolution import resolve_aliases
from interactions import extract_interactions_from_mentions
from polarity import enrich_interactions_with_polarity, load_polarity_lexicon
from graph_builder import build_graph
from export import (
    graph_to_graphml_string,
    export_graphml,
    build_submission_row,
    export_submission_csv,
)


def filter_weak_characters(
    characters: list[dict],
    resolved_mentions: list[dict],
    mention_source_by_id: dict[str, str] | None = None,
    keep_singleton_sources: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Supprime les personnages faibles:
    - une seule mention
    - un seul alias
    - alias a un seul mot

    Exception configurable:
    - on peut garder certains singletons selon leur source de mention
      (ex: rule_list, rule_salvage).
    """
    kept_characters = []
    kept_ids = set()
    mention_source_by_id = mention_source_by_id or {}
    keep_singleton_sources = keep_singleton_sources or set()

    for character in characters:
        aliases = character["aliases"]
        mention_ids = character["mention_ids"]

        single_alias = len(aliases) == 1
        single_mention = len(mention_ids) == 1
        one_word_alias = len(aliases[0].split()) == 1 if aliases else False

        should_drop = single_alias and single_mention and one_word_alias

        if should_drop and mention_ids:
            source = mention_source_by_id.get(mention_ids[0], "")
            if source in keep_singleton_sources:
                should_drop = False

        if not should_drop:
            kept_characters.append(character)
            kept_ids.add(character["character_id"])

    kept_resolved_mentions = [
        mention for mention in resolved_mentions if mention["character_id"] in kept_ids
    ]

    return kept_characters, kept_resolved_mentions


def run_pipeline(input_path: str, config: dict, preloaded_model=None) -> dict:
    """
    Execute le pipeline complet sur un document.
    Retourne tous les objets utiles pour le debug et l'export.
    """
    validate_config(config)

    document = preprocess_document(input_path)
    model = preloaded_model if preloaded_model is not None else load_ner_model(config["ner_model"])

    spacy_mentions = extract_person_mentions(document["clean_text"], model)
    rule_mentions = extract_rule_based_person_mentions(document["clean_text"])

    raw_mentions = build_enriched_person_mentions(
        document["clean_text"],
        spacy_mentions,
        rule_mentions,
    )

    mentions = filter_person_mentions(raw_mentions)
    aligned_mentions = align_mentions_to_tokens(mentions, document["tokens"])
    mention_source_by_id = {
        mention["mention_id"]: mention.get("source", "unknown")
        for mention in aligned_mentions
    }

    alias_result = resolve_aliases(aligned_mentions)
    resolved_mentions = alias_result["resolved_mentions"]
    characters = alias_result["characters"]

    characters, resolved_mentions = filter_weak_characters(
        characters,
        resolved_mentions,
        mention_source_by_id=mention_source_by_id,
        keep_singleton_sources=set(config.get("keep_singleton_sources", [])),
    )

    interactions = extract_interactions_from_mentions(
        resolved_mentions,
        window_size=config["cooccurrence_window"],
        min_edge_weight=config.get("interaction_min_weight", 2),
    )

    if config.get("polarity_enabled", True):
        polarity_lexicon = load_polarity_lexicon(config["polarity_lexicon_path"])
        interactions = enrich_interactions_with_polarity(
            interactions,
            resolved_mentions,
            document["tokens"],
            polarity_lexicon,
            window_size=config["cooccurrence_window"],
            context_window=config.get("polarity_context_window", 8),
        )

    graph = build_graph(characters, interactions)

    return {
        "doc_id": document["doc_id"],
        "document": document,
        "raw_mentions": raw_mentions,
        "mentions": mentions,
        "aligned_mentions": aligned_mentions,
        "resolved_mentions": resolved_mentions,
        "characters": characters,
        "interactions": interactions,
        "graph": graph,
    }


def main() -> None:
    """
    Exemple d'execution sur un chapitre.
    """
    config = get_default_config()

    input_path = "data/raw/les_cavernes_d_acier/chapter_1.txt.preprocessed"
    result = run_pipeline(input_path, config)

    graphml_content = graph_to_graphml_string(result["graph"])

    graphml_path = f"data/processed/{result['doc_id']}.graphml"
    export_graphml(result["graph"], graphml_path)

    submission_row = build_submission_row(result["doc_id"], graphml_content)
    csv_path = "data/submissions/test_submission.csv"
    export_submission_csv([submission_row], csv_path)

    print("Pipeline termine.")
    print("Document :", result["doc_id"])
    print("Mentions extraites :", len(result["mentions"]))
    print("Mentions alignees :", len(result["aligned_mentions"]))
    print("Personnages :", len(result["characters"]))
    print("Interactions :", len(result["interactions"]))
    print("Noeuds du graphe :", result["graph"].number_of_nodes())
    print("Aretes du graphe :", result["graph"].number_of_edges())
    print("GraphML :", graphml_path)
    print("CSV :", csv_path)
    print("Mentions brutes :", len(result["raw_mentions"]))
    print("Mentions filtrees :", len(result["mentions"]))


if __name__ == "__main__":
    main()

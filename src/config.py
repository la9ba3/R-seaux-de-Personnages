from pathlib import Path
import os


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_default_config() -> dict:
    """
    Retourne la configuration par defaut du projet.
    """
    project_root = Path(__file__).resolve().parent.parent

    config = {
        "project_root": project_root,
        "data_raw_dir": project_root / "data" / "raw",
        "data_interim_dir": project_root / "data" / "interim",
        "data_processed_dir": project_root / "data" / "processed",
        "data_submissions_dir": project_root / "data" / "submissions",
        "outputs_figures_dir": project_root / "outputs" / "figures",
        "outputs_reports_dir": project_root / "outputs" / "reports",

        # Donnees
        "books": [
            "les_cavernes_d_acier",
            "prelude_a_fondation",
        ],
        "chapter_file_extension": ".txt.preprocessed",

        # NER
        #"ner_model": "fr_core_news_lg",
        "ner_model": os.getenv("NER_MODEL", "fr_core_news_lg"),
        "strict_ner_filters": _env_bool("STRICT_NER_FILTERS", False),
        "known_aliases_enabled": _env_bool("KNOWN_ALIASES_ENABLED", False),
        "export_all_aliases": _env_bool("EXPORT_ALL_ALIASES", False),
        # Sources autorisees a survivre au filtre singleton.
        "keep_singleton_sources": [
            "rule_title",
            "rule_role",
            "rule_list",
            "rule_salvage",
        ],

        # Interactions
        "cooccurrence_window": 25,
        # 1 = garder toutes les cooccurrences; 2 = regle stricte historique.
        "interaction_min_weight": 1,

        # Polarite des relations
        "polarity_enabled": _env_bool("POLARITY_ENABLED", True),
        "polarity_lexicon_path": project_root / "data" / "polarity" / "dictionnaire_polarite_fr.txt",
        "polarity_context_window": 8,

        # Export
        "submission_filename": "submission.csv",
    }

    return config


def validate_config(config: dict) -> None:
    """
    Verifie que la configuration contient les cles minimales requises.
    Leve une ValueError si la configuration est invalide.
    """
    required_keys = [
        "project_root",
        "data_raw_dir",
        "data_interim_dir",
        "data_processed_dir",
        "data_submissions_dir",
        "outputs_figures_dir",
        "outputs_reports_dir",
        "books",
        "chapter_file_extension",
        "ner_model",
        "strict_ner_filters",
        "known_aliases_enabled",
        "export_all_aliases",
        "keep_singleton_sources",
        "cooccurrence_window",
        "interaction_min_weight",
        "polarity_enabled",
        "polarity_lexicon_path",
        "polarity_context_window",
        "submission_filename",
    ]

    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Configuration invalide. Cles manquantes : {missing_keys}")

    if not isinstance(config["books"], list) or not config["books"]:
        raise ValueError("La cle 'books' doit etre une liste non vide.")

    if not isinstance(config["cooccurrence_window"], int) or config["cooccurrence_window"] <= 0:
        raise ValueError("La cle 'cooccurrence_window' doit etre un entier strictement positif.")

    if not isinstance(config["interaction_min_weight"], int) or config["interaction_min_weight"] <= 0:
        raise ValueError("La cle 'interaction_min_weight' doit etre un entier strictement positif.")

    if not isinstance(config["polarity_enabled"], bool):
        raise ValueError("La cle 'polarity_enabled' doit etre un booleen.")

    if not isinstance(config["polarity_context_window"], int) or config["polarity_context_window"] < 0:
        raise ValueError("La cle 'polarity_context_window' doit etre un entier positif ou nul.")

    if not isinstance(config["keep_singleton_sources"], list):
        raise ValueError("La cle 'keep_singleton_sources' doit etre une liste.")

    for key in ("strict_ner_filters", "known_aliases_enabled", "export_all_aliases"):
        if not isinstance(config[key], bool):
            raise ValueError(f"La cle '{key}' doit etre un booleen.")

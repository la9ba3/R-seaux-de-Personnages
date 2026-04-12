from pathlib import Path
import re


def read_text(path: str) -> str:
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def tokenize_text(text: str) -> list[dict]:
    raw_tokens = text.split()
    return [{"text": token, "index": i} for i, token in enumerate(raw_tokens)]


def build_doc_id(path: str) -> str:
    """
    Convertit un fichier chapitre en ID Kaggle.

    Exemples :
    - data/raw/les_cavernes_d_acier/chapter_1.txt.preprocessed -> lca0
    - data/raw/les_cavernes_d_acier/chapter_18.txt.preprocessed -> lca17
    - data/raw/prelude_a_fondation/chapter_1.txt.preprocessed -> paf0
    - data/raw/prelude_a_fondation/chapter_19.txt.preprocessed -> paf18
    """
    file_path = Path(path)
    book_name = file_path.parent.name
    file_name = file_path.name

    match = re.match(r"chapter_(\d+)\.txt\.preprocessed$", file_name)
    if not match:
        raise ValueError(f"Nom de fichier de chapitre invalide : {file_name}")

    chapter_number_in_file = int(match.group(1))
    chapter_index = chapter_number_in_file - 1  # Kaggle commence à 0

    if book_name == "prelude_a_fondation":
        book_code = "paf"
    elif book_name == "les_cavernes_d_acier":
        book_code = "lca"
    else:
        raise ValueError(f"Livre inconnu pour la soumission Kaggle : {book_name}")

    return f"{book_code}{chapter_index}"


def preprocess_document(path: str) -> dict:
    raw_text = read_text(path)
    cleaned_text = clean_text(raw_text)
    tokens = tokenize_text(cleaned_text)
    doc_id = build_doc_id(path)

    document = {
        "doc_id": doc_id,
        "raw_text": raw_text,
        "clean_text": cleaned_text,
        "tokens": tokens,
    }

    return document
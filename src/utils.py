from pathlib import Path


def ensure_dir(path: str) -> None:
    """
    Crée un dossier s'il n'existe pas.
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def sort_pair(a: str, b: str) -> tuple[str, str]:
    """
    Retourne une paire triée pour éviter les doublons
    (A, B) / (B, A).
    """
    return tuple(sorted([a, b]))
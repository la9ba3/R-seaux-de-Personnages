from pathlib import Path

# Dossier racine du projet = dossier où se trouve ce script
ROOT = Path(__file__).resolve().parent

# Dossiers à créer
directories = [
    "data/raw",
    "data/interim",
    "data/processed",
    "data/submissions",
    "notebooks",
    "outputs/figures",
    "outputs/reports",
    "src",
    "scripts",
    "tests",
]

# Fichiers à créer
files = {
    "README.md": "# Character Network Project\n",
    "requirements.txt": "",
    ".gitignore": """# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.venv/
venv/

# Jupyter
.ipynb_checkpoints/

# Outputs
outputs/
data/interim/
data/processed/
data/submissions/

# OS
.DS_Store
Thumbs.db
""",
    "src/main.py": "",
    "src/config.py": "",
    "src/preprocessing.py": "",
    "src/ner.py": "",
    "src/alias_resolution.py": "",
    "src/interactions.py": "",
    "src/graph_builder.py": "",
    "src/export.py": "",
    "src/utils.py": "",
    "tests/test_alias_resolution.py": "",
    "tests/test_interactions.py": "",
    "tests/test_export.py": "",
}

def create_directories():
    for directory in directories:
        path = ROOT / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"[DIR]  {path}")

def create_files():
    for relative_path, content in files.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            path.write_text(content, encoding="utf-8")
            print(f"[FILE] {path}")
        else:
            print(f"[SKIP] {path} existe déjà")

def main():
    print(f"Initialisation du projet dans : {ROOT}")
    create_directories()
    create_files()
    print("Terminé.")

if __name__ == "__main__":
    main()
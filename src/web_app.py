from __future__ import annotations

import argparse
import base64
from collections import Counter
from html import escape
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import re
from urllib.parse import parse_qs

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from alias_resolution import resolve_aliases
from config import get_default_config
from graph_builder import build_graph
from interactions import extract_interactions_from_mentions
from ner import (
    align_mentions_to_tokens,
    deduplicate_mentions,
    extract_person_mentions,
    extract_rule_based_person_mentions,
    filter_person_mentions,
    load_ner_model,
)
from preprocessing import clean_text, tokenize_text


MAX_TEXT_LENGTH = 120_000
_MODEL = None
_CONFIG = get_default_config()
UI_TITLE_ONLY_WORDS = {
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
UI_ALLOWED_LOWER_TOKENS = {
    "de",
    "du",
    "des",
    "d",
    "d'",
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
UI_NAME_PATTERN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+"
UI_NAME_RE = re.compile(UI_NAME_PATTERN)
UI_ENUMERATION_RE = re.compile(
    rf"\b{UI_NAME_PATTERN}(?:\s*,\s*{UI_NAME_PATTERN})+\s*(?:,\s*)?(?:et|ou)\s+{UI_NAME_PATTERN}\b"
)


def _normalize_name_token(token: str) -> str:
    cleaned = token.strip(" \t\n\r.,;:!?()[]{}\"'")
    cleaned = cleaned.replace("’", "'")
    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'\-]", "", cleaned)
    return cleaned


def is_plausible_character_name(name: str) -> bool:
    parts = [_normalize_name_token(part) for part in name.split()]
    parts = [part for part in parts if part]
    if not parts:
        return False

    normalized_parts = [part.lower() for part in parts]
    if len(normalized_parts) == 1 and normalized_parts[0].rstrip(".") in UI_TITLE_ONLY_WORDS:
        return False

    for part, normalized in zip(parts, normalized_parts):
        if part[0].islower() and normalized not in UI_ALLOWED_LOWER_TOKENS:
            return False

    return True


def filter_ui_noise_characters(
    characters: list[dict],
    resolved_mentions: list[dict],
) -> tuple[list[dict], list[dict]]:
    kept_characters = []
    kept_ids = set()

    for character in characters:
        if not is_plausible_character_name(character["canonical_name"]):
            continue
        kept_characters.append(character)
        kept_ids.add(character["character_id"])

    kept_resolved_mentions = [
        mention for mention in resolved_mentions if mention["character_id"] in kept_ids
    ]
    return kept_characters, kept_resolved_mentions


def filter_ui_noise_mentions(mentions: list[dict]) -> list[dict]:
    return [mention for mention in mentions if is_plausible_character_name(mention["text"])]


def build_anchor_words(spacy_mentions: list[dict]) -> set[str]:
    anchor_words: set[str] = set()
    for mention in spacy_mentions:
        for match in UI_NAME_RE.finditer(mention["text"]):
            anchor_words.add(match.group(0).lower())
    return anchor_words


def extract_salvaged_name_mentions(spacy_mentions: list[dict]) -> list[dict]:
    mentions = []
    mention_count = 1

    for mention in spacy_mentions:
        mention_text = mention["text"]
        if is_plausible_character_name(mention_text):
            continue

        for match in UI_NAME_RE.finditer(mention_text):
            item_text = match.group(0)
            start_char = mention["start_char"] + match.start()
            end_char = mention["start_char"] + match.end()

            mentions.append(
                {
                    "mention_id": f"m_rule_salvage_{mention_count:04d}",
                    "text": item_text,
                    "start_char": start_char,
                    "end_char": end_char,
                    "label": "PER",
                    "source": "rule_salvage",
                }
            )
            mention_count += 1

    return mentions


def extract_list_based_person_mentions(
    text: str,
    anchor_words: set[str],
) -> list[dict]:
    mentions = []
    mention_count = 1

    for list_match in UI_ENUMERATION_RE.finditer(text):
        list_text = list_match.group(0)
        items = []

        for item_match in UI_NAME_RE.finditer(list_text):
            item_text = item_match.group(0)
            global_start = list_match.start() + item_match.start()
            global_end = list_match.start() + item_match.end()
            items.append((item_text, global_start, global_end))

        if len(items) < 3:
            continue

        if not any(item_text.lower() in anchor_words for item_text, _, _ in items):
            continue

        for item_text, start_char, end_char in items:
            mentions.append(
                {
                    "mention_id": f"m_rule_list_{mention_count:04d}",
                    "text": item_text,
                    "start_char": start_char,
                    "end_char": end_char,
                    "label": "PER",
                    "source": "rule_list",
                }
            )
            mention_count += 1

    return mentions


def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = load_ner_model(_CONFIG["ner_model"])
    return _MODEL


def analyze_text(text: str) -> dict:
    model = get_model()
    cleaned_text = clean_text(text)
    tokens = tokenize_text(cleaned_text)

    spacy_mentions = extract_person_mentions(cleaned_text, model)
    rule_mentions = extract_rule_based_person_mentions(cleaned_text)
    salvaged_mentions = extract_salvaged_name_mentions(spacy_mentions)
    anchor_words = build_anchor_words(spacy_mentions)
    list_mentions = extract_list_based_person_mentions(cleaned_text, anchor_words)
    raw_mentions = deduplicate_mentions(
        spacy_mentions + rule_mentions + salvaged_mentions + list_mentions
    )

    mentions = filter_person_mentions(raw_mentions)
    mentions = filter_ui_noise_mentions(mentions)
    aligned_mentions = align_mentions_to_tokens(mentions, tokens)

    alias_result = resolve_aliases(aligned_mentions)
    resolved_mentions = alias_result["resolved_mentions"]
    characters = alias_result["characters"]

    # Interface mode: keep one-mention names (useful for exploratory text input),
    # but remove obvious noise such as title-only nodes or lowercase verb fragments.
    characters, resolved_mentions = filter_ui_noise_characters(characters, resolved_mentions)
    interactions = extract_interactions_from_mentions(
        resolved_mentions,
        window_size=_CONFIG["cooccurrence_window"],
        min_edge_weight=_CONFIG.get("interaction_min_weight", 2),
    )

    graph = build_graph(characters, interactions)
    mention_counts = Counter(mention["character_id"] for mention in resolved_mentions)

    return {
        "raw_mentions": raw_mentions,
        "mentions": mentions,
        "resolved_mentions": resolved_mentions,
        "characters": characters,
        "interactions": interactions,
        "graph": graph,
        "mention_counts": mention_counts,
    }


def graph_to_base64_png(graph: nx.Graph) -> str | None:
    if graph.number_of_nodes() == 0:
        return None

    figure, axis = plt.subplots(figsize=(9, 6))
    position = nx.spring_layout(graph, seed=42, k=1.25)

    degrees = dict(graph.degree())
    node_sizes = [500 + 220 * degrees[node] for node in graph.nodes()]
    edge_widths = [1.0 + 0.6 * data.get("weight", 1) for _, _, data in graph.edges(data=True)]
    labels = {node: data.get("label", node) for node, data in graph.nodes(data=True)}

    nx.draw_networkx_nodes(
        graph,
        position,
        node_size=node_sizes,
        alpha=0.9,
        node_color="#4C78A8",
        ax=axis,
    )
    nx.draw_networkx_edges(
        graph,
        position,
        width=edge_widths,
        alpha=0.55,
        edge_color="#666666",
        ax=axis,
    )
    nx.draw_networkx_labels(
        graph,
        position,
        labels=labels,
        font_size=8,
        ax=axis,
    )

    axis.set_axis_off()
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(figure)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_character_rows(characters: list[dict], mention_counts: Counter) -> str:
    if not characters:
        return "<p>Aucun personnage detecte.</p>"

    sorted_characters = sorted(
        characters,
        key=lambda character: (
            -mention_counts.get(character["character_id"], 0),
            character["canonical_name"],
        ),
    )

    rows = []
    for character in sorted_characters[:25]:
        count = mention_counts.get(character["character_id"], 0)
        aliases = ", ".join(character["aliases"][:5])
        if len(character["aliases"]) > 5:
            aliases += ", ..."
        rows.append(
            (
                "<tr>"
                f"<td>{escape(character['canonical_name'])}</td>"
                f"<td>{count}</td>"
                f"<td>{escape(aliases)}</td>"
                "</tr>"
            )
        )

    return (
        "<table>"
        "<thead><tr><th>Nom canonique</th><th>Mentions</th><th>Alias</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build_results_html(analysis: dict) -> str:
    graph = analysis["graph"]
    graph_image = graph_to_base64_png(graph)
    character_rows = build_character_rows(analysis["characters"], analysis["mention_counts"])

    graph_block = (
        f"<img alt='Graphe des personnages' src='data:image/png;base64,{graph_image}' />"
        if graph_image
        else "<p>Le graphe est vide pour ce texte.</p>"
    )

    return (
        "<section class='results'>"
        "<h2>Resultats</h2>"
        "<div class='stats'>"
        f"<p>Mentions brutes : {len(analysis['raw_mentions'])}</p>"
        f"<p>Mentions filtrees : {len(analysis['mentions'])}</p>"
        f"<p>Personnages : {len(analysis['characters'])}</p>"
        f"<p>Interactions : {len(analysis['interactions'])}</p>"
        f"<p>Noeuds : {graph.number_of_nodes()}</p>"
        f"<p>Aretes : {graph.number_of_edges()}</p>"
        "</div>"
        "<h3>Graphe</h3>"
        f"{graph_block}"
        "<h3>Personnages detectes</h3>"
        f"{character_rows}"
        "</section>"
    )


def validate_input_text(input_text: str) -> str | None:
    if not input_text.strip():
        return "Veuillez saisir un texte non vide."
    if len(input_text) > MAX_TEXT_LENGTH:
        return f"Texte trop long (max {MAX_TEXT_LENGTH} caracteres)."
    return None


def run_analysis_for_input(input_text: str) -> tuple[int, dict]:
    validation_error = validate_input_text(input_text)
    if validation_error is not None:
        return 400, {
            "ok": False,
            "message": validation_error,
            "results_html": "",
        }

    try:
        analysis = analyze_text(input_text)
    except Exception as error:  # pragma: no cover
        return 500, {
            "ok": False,
            "message": f"Erreur pendant l'analyse : {error}",
            "results_html": "",
        }

    return 200, {
        "ok": True,
        "message": "Analyse terminee.",
        "results_html": build_results_html(analysis),
    }


def render_page(
    input_text: str = "",
    message: str = "",
    results_html: str = "",
) -> str:
    escaped_text = escape(input_text)
    escaped_message = f"<p class='message'>{escape(message)}</p>" if message else "<p class='message'></p>"

    return (
        "<!doctype html>"
        "<html lang='fr'>"
        "<head>"
        "<meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width, initial-scale=1' />"
        "<title>Graphe de personnages</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;max-width:980px;margin:24px auto;padding:0 12px;}"
        "h1,h2,h3{margin-bottom:8px;}"
        "textarea{width:100%;min-height:220px;padding:10px;font-family:monospace;}"
        "button{padding:9px 14px;cursor:pointer;}"
        ".message{background:#f3f5f7;padding:8px 10px;border-left:3px solid #6b7785;min-height:18px;}"
        ".stats{display:flex;flex-wrap:wrap;gap:14px;margin:6px 0 12px;}"
        ".stats p{margin:0;background:#f8f9fa;padding:6px 8px;border:1px solid #e4e6e8;}"
        "img{max-width:100%;height:auto;border:1px solid #ddd;padding:6px;background:#fff;}"
        "table{width:100%;border-collapse:collapse;margin-top:8px;}"
        "th,td{border:1px solid #ddd;padding:6px;text-align:left;vertical-align:top;}"
        "th{background:#f5f5f5;}"
        ".controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px;}"
        "</style>"
        "</head>"
        "<body>"
        "<h1>Extraction de graphe de personnages</h1>"
        "<p>Colle un texte puis lance l'analyse pour obtenir le graphe des personnages.</p>"
        f"{escaped_message}"
        "<form id='analyze-form' method='post'>"
        "<label for='input_text'><strong>Texte d'entree</strong></label>"
        f"<textarea id='input_text' name='input_text' placeholder='Colle un chapitre ici...'>{escaped_text}</textarea>"
        "<div class='controls'>"
        "<button id='analyze-button' type='submit'>Analyser le texte</button>"
        "<label><input id='auto-analyze' type='checkbox' /> Analyse auto (0.8s)</label>"
        "</div>"
        "</form>"
        f"<div id='results-container'>{results_html}</div>"
        "<script>"
        "(function(){"
        "const form=document.getElementById('analyze-form');"
        "const input=document.getElementById('input_text');"
        "const button=document.getElementById('analyze-button');"
        "const auto=document.getElementById('auto-analyze');"
        "const msg=document.querySelector('.message');"
        "const results=document.getElementById('results-container');"
        "let timer=null;"
        "let requestId=0;"
        "function setMessage(text){msg.textContent=text || '';}"
        "async function runAnalysis(){"
        "const text=input.value;"
        "const myId=++requestId;"
        "button.disabled=true;"
        "setMessage('Analyse en cours...');"
        "try{"
        "const body=new URLSearchParams();"
        "body.set('input_text', text);"
        "const response=await fetch('/analyze',{"
        "method:'POST',"
        "headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},"
        "body:body.toString()"
        "});"
        "const data=await response.json();"
        "if(myId!==requestId){return;}"
        "if(!response.ok || !data.ok){"
        "setMessage(data.message || 'Erreur.');"
        "return;"
        "}"
        "results.innerHTML=data.results_html || '';"
        "setMessage(data.message || 'Analyse terminee.');"
        "}catch(error){"
        "if(myId!==requestId){return;}"
        "setMessage('Erreur reseau.');"
        "}finally{"
        "if(myId===requestId){button.disabled=false;}"
        "}"
        "}"
        "form.addEventListener('submit',function(event){"
        "event.preventDefault();"
        "runAnalysis();"
        "});"
        "input.addEventListener('input',function(){"
        "if(!auto.checked){return;}"
        "if(timer!==null){clearTimeout(timer);}"
        "timer=setTimeout(runAnalysis,800);"
        "});"
        "})();"
        "</script>"
        "</body>"
        "</html>"
    )


class CharacterGraphHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        content = render_page(message="Pret.")
        self.respond_html(content)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8", errors="replace")
        form_data = parse_qs(body)
        input_text = form_data.get("input_text", [""])[0]

        status_code, payload = run_analysis_for_input(input_text)
        request_path = self.path.split("?", maxsplit=1)[0]

        if request_path == "/analyze":
            self.respond_json(payload, status_code=status_code)
            return

        content = render_page(
            input_text=input_text,
            message=payload["message"],
            results_html=payload["results_html"],
        )
        self.respond_html(content)

    def respond_html(self, content: str, status_code: int = 200):
        payload = content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def respond_json(self, payload_obj: dict, status_code: int = 200):
        payload = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args):  # noqa: A003
        return


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), CharacterGraphHandler)
    print(f"Serveur demarre sur http://{host}:{port}")
    print("Ctrl+C pour arreter.")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interface web de graphe de personnages")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'ecoute")
    parser.add_argument("--port", type=int, default=8000, help="Port HTTP")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run_server(host=arguments.host, port=arguments.port)

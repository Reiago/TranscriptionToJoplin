#!/usr/bin/env python3
"""Cree une note dans Joplin via l'API locale du Web Clipper Service."""
import argparse
import json
import os
import sys

if os.name == "nt" and not sys.flags.utf8_mode:
    # Sans le mode UTF-8, Windows decode argv avec la codepage console et
    # corrompt les caracteres accentues (ex: --title avec des accents).
    import subprocess

    result = subprocess.run([sys.executable, "-X", "utf8", __file__] + sys.argv[1:])
    sys.exit(result.returncode)

import requests
from dotenv import load_dotenv


def get_base_url() -> str:
    port = os.environ.get("JOPLIN_PORT", "41184")
    return f"http://localhost:{port}"


def get_token() -> str:
    token = os.environ.get("JOPLIN_TOKEN")
    if not token:
        raise RuntimeError(
            "JOPLIN_TOKEN manquant. Copie .env.example vers .env et renseigne le token "
            "(Joplin Desktop > Options > Web Clipper)."
        )
    return token


def check_connection() -> str:
    base_url = get_base_url()
    resp = requests.get(f"{base_url}/ping", timeout=5)
    resp.raise_for_status()
    return resp.text


def get_or_create_notebook_id(base_url: str, token: str, name: str) -> str:
    page = 1
    while True:
        resp = requests.get(
            f"{base_url}/folders", params={"token": token, "page": page}, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        for folder in data.get("items", []):
            if folder["title"].lower() == name.lower():
                return folder["id"]
        if not data.get("has_more"):
            break
        page += 1

    resp = requests.post(
        f"{base_url}/folders", params={"token": token}, json={"title": name}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_note(title: str, body: str, notebook: str | None = None) -> dict:
    token = get_token()
    base_url = get_base_url()

    payload = {"title": title, "body": body}

    notebook = notebook or os.environ.get("JOPLIN_NOTEBOOK")
    if notebook:
        payload["parent_id"] = get_or_create_notebook_id(base_url, token, notebook)

    resp = requests.post(f"{base_url}/notes", params={"token": token}, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Cree une note dans Joplin via l'API Web Clipper.")
    parser.add_argument("--check", action="store_true", help="Verifie juste la connexion a Joplin")
    parser.add_argument("--title", help="Titre de la note")
    parser.add_argument("--body-file", help="Fichier contenant le corps (markdown) de la note")
    parser.add_argument("--body", help="Corps de la note directement en argument")
    parser.add_argument("--notebook", help="Nom du carnet Joplin cible (sinon JOPLIN_NOTEBOOK ou carnet par defaut)")
    args = parser.parse_args()

    if args.check:
        try:
            result = check_connection()
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            sys.exit(1)
        print(json.dumps({"status": "ok", "response": result}))
        return

    if not args.title or not (args.body_file or args.body):
        parser.error("--title et (--body-file ou --body) sont requis (sauf avec --check)")

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    else:
        body = args.body

    try:
        note = create_note(args.title, body, args.notebook)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"id": note.get("id"), "title": note.get("title")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

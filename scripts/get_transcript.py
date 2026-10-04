#!/usr/bin/env python3
"""Recupere le titre, la date de publication, la description et la transcription (sous-titres) d'une video YouTube."""
import argparse
import json
import sys

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def get_video_info(url: str):
    ydl_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    chapters = [
        {"start": int(c.get("start_time") or 0), "title": c.get("title", "")}
        for c in info.get("chapters") or []
    ]
    upload_date = info.get("upload_date") or ""  # format YYYYMMDD
    if len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": upload_date,
        "description": info.get("description") or "",
        "chapters": chapters,
    }


def get_transcript(url: str, langs):
    info = get_video_info(url)
    video_id = info["id"]
    if not video_id:
        raise RuntimeError("Impossible de recuperer les informations de la video.")

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
    except TranscriptsDisabled as exc:
        raise RuntimeError("Les sous-titres sont desactives pour cette video.") from exc
    except NoTranscriptFound as exc:
        raise RuntimeError(
            "Aucun sous-titre disponible pour cette video (ni manuel, ni automatique)."
        ) from exc
    except CouldNotRetrieveTranscript as exc:
        raise RuntimeError(f"Impossible de recuperer la transcription: {exc}") from exc

    transcript = " ".join(
        snippet.text.strip() for snippet in fetched.snippets if snippet.text.strip()
    )

    if not transcript:
        raise RuntimeError("La transcription recuperee est vide.")

    return {
        "id": video_id,
        "title": info["title"],
        "url": url,
        "channel": info["channel"],
        "upload_date": info["upload_date"],
        "description": info["description"],
        "chapters": info["chapters"],
        "subtitle_source": f"{fetched.language_code}{'(auto)' if fetched.is_generated else ''}",
        "transcript": transcript,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Recupere le titre, la description et la transcription d'une video YouTube (JSON sur stdout)."
    )
    parser.add_argument("url", help="URL de la video YouTube")
    parser.add_argument(
        "--langs",
        default="fr,en",
        help="Langues preferees pour les sous-titres, separees par des virgules (defaut: fr,en)",
    )
    args = parser.parse_args()
    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]

    try:
        result = get_transcript(args.url, langs)
    except Exception as exc:  # noqa: BLE001 - on veut renvoyer toute erreur a l'appelant
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

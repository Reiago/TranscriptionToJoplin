#!/usr/bin/env python3
"""Recupere le titre et la transcription (sous-titres) d'une video YouTube."""
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
    return info.get("id"), info.get("title")


def get_transcript(url: str, langs):
    video_id, title = get_video_info(url)
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
        "title": title,
        "url": url,
        "subtitle_source": f"{fetched.language_code}{'(auto)' if fetched.is_generated else ''}",
        "transcript": transcript,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Recupere le titre et la transcription d'une video YouTube (JSON sur stdout)."
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

#!/usr/bin/env python3
"""Recupere le titre et la transcription (sous-titres) d'une video YouTube."""
import argparse
import glob
import json
import os
import re
import sys
import tempfile

import yt_dlp

TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
TAG_RE = re.compile(r"<[^>]+>")


def vtt_to_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    text_lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if TIMESTAMP_RE.match(line):
            continue
        if line.isdigit():
            continue
        line = TAG_RE.sub("", line).strip()
        if line and (not text_lines or text_lines[-1] != line):
            text_lines.append(line)
    return " ".join(text_lines)


def pick_subtitle_file(vtt_files, video_id, langs):
    for lang in langs:
        for f in vtt_files:
            basename = os.path.basename(f)
            if basename.startswith(f"{video_id}.{lang}.") or basename == f"{video_id}.{lang}.vtt":
                return f
    return vtt_files[0]


def get_transcript(url: str, langs):
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt",
            "subtitleslangs": langs,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logtostderr": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        video_id = info.get("id")
        title = info.get("title")

        vtt_files = glob.glob(os.path.join(tmpdir, f"{video_id}*.vtt"))
        if not vtt_files:
            raise RuntimeError(
                "Aucun sous-titre disponible pour cette video (ni manuel, ni automatique)."
            )

        chosen = pick_subtitle_file(vtt_files, video_id, langs)
        transcript = vtt_to_text(chosen)

        if not transcript:
            raise RuntimeError("La transcription recuperee est vide.")

        return {
            "id": video_id,
            "title": title,
            "url": url,
            "subtitle_source": os.path.basename(chosen),
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

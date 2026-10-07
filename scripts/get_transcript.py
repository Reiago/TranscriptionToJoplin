#!/usr/bin/env python3
"""Recupere le titre, la date de publication, la description et la transcription d'une video YouTube.

Utilise les sous-titres YouTube ; a defaut, transcrit l'audio avec faster-whisper.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

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
        "live_status": info.get("live_status") or "",
    }


def fetch_subtitles(video_id: str, langs):
    """Retourne (texte, source) depuis les sous-titres YouTube."""
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
    source = f"{fetched.language_code}{'(auto)' if fetched.is_generated else ''}"
    return transcript, source


def add_cuda_dll_dirs():
    """Rend visibles les DLL CUDA 12 des paquets pip nvidia-* (cuBLAS, cuDNN) pour ctranslate2."""
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def run_whisper(audio_file: Path, model_name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, info = model.transcribe(str(audio_file), vad_filter=True)
    # segments est un generateur : la transcription (et les erreurs CUDA) arrive ici
    transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
    return transcript, info.language


def transcribe_audio(url: str, model_name: str):
    """Telecharge la piste audio et la transcrit avec faster-whisper. Retourne (texte, source)."""
    with tempfile.TemporaryDirectory() as tmp:
        print("Telechargement de l'audio...", file=sys.stderr)
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(tmp) / "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        audio_file = next(Path(tmp).glob("audio.*"))

        print(f"Transcription avec Whisper ({model_name})...", file=sys.stderr)
        add_cuda_dll_dirs()
        try:
            transcript, language = run_whisper(audio_file, model_name, "cuda", "float16")
        except Exception as exc:  # noqa: BLE001 - pas de GPU/CUDA utilisable
            print(f"GPU indisponible ({exc}), transcription sur CPU.", file=sys.stderr)
            transcript, language = run_whisper(audio_file, model_name, "cpu", "int8")
    return transcript, f"{language}(whisper:{model_name})"


def get_transcript(url: str, langs, whisper_model: str | None):
    info = get_video_info(url)
    video_id = info["id"]
    if not video_id:
        raise RuntimeError("Impossible de recuperer les informations de la video.")

    try:
        transcript, source = fetch_subtitles(video_id, langs)
    except RuntimeError as exc:
        if not whisper_model:
            raise
        if info["live_status"] in ("is_live", "is_upcoming"):
            raise RuntimeError(
                f"{exc} La video est un direct en cours ou a venir : "
                "transcription audio impossible avant la fin de la diffusion."
            ) from exc
        print(f"{exc} Repli sur la transcription audio.", file=sys.stderr)
        transcript, source = transcribe_audio(url, whisper_model)

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
        "subtitle_source": source,
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
    parser.add_argument(
        "--whisper-model",
        default="large-v3-turbo",
        help="Modele faster-whisper utilise si la video n'a pas de sous-titres (defaut: large-v3-turbo)",
    )
    parser.add_argument(
        "--no-whisper",
        action="store_true",
        help="Ne pas transcrire l'audio quand les sous-titres sont absents",
    )
    args = parser.parse_args()
    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]

    try:
        result = get_transcript(args.url, langs, None if args.no_whisper else args.whisper_model)
    except Exception as exc:  # noqa: BLE001 - on veut renvoyer toute erreur a l'appelant
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

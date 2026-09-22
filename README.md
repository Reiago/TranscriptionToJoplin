# TranscriptionToJoplin

Transcrit une video YouTube, en genere un resume, et l'envoie dans Joplin sous
forme de note — via un skill Claude Code (`youtube-to-joplin`) qui orchestre
deux scripts Python et l'API locale du Joplin Web Clipper.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration de Joplin

1. Ouvrir Joplin Desktop.
2. Options (ou Preferences) > Web Clipper.
3. Activer le "Web Clipper Service".
4. Copier le token affiche.
5. Copier `.env.example` vers `.env` et renseigner `JOPLIN_TOKEN` (et
   eventuellement `JOPLIN_NOTEBOOK` pour cibler un carnet par defaut).

Joplin Desktop doit rester ouvert pour que l'API locale (`localhost:41184`) soit
disponible.

## Utilisation

Dans une session Claude Code, donner simplement un lien YouTube et demander un
resume a envoyer dans Joplin : le skill `youtube-to-joplin` s'occupe du reste.

En manuel :

```bash
# 1. Recuperer titre + transcription
python scripts/get_transcript.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2. Verifier la connexion Joplin
python scripts/send_to_joplin.py --check

# 3. Creer la note (corps au format markdown)
python scripts/send_to_joplin.py --title "Mon titre" --body-file note.md
```

## Format de note genere

```
# <Titre de la video>
<URL YouTube>

<Contenu du resume>
```

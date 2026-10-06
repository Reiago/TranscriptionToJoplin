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
# 1. Recuperer titre, description (liens) + transcription
python scripts/get_transcript.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2. Verifier la connexion Joplin
python scripts/send_to_joplin.py --check

# 3. Creer la note (corps au format markdown)
python scripts/send_to_joplin.py --title "Mon titre" --body-file note.md
```

## Nettoyer une note importee depuis un mail

Les mails HTML exportes depuis Thunderbird (extension "Joplin Export", format
HTML) arrivent dans Joplin sous forme de tableaux HTML de mise en page, presque
illisibles. `clean_email_note.py` les convertit en markdown : texte, titres,
listes et images conserves, liens de tracking remplaces par leur vraie
destination, pixels espions, icones et pied de desabonnement supprimes.

```bash
# Apercu du resultat, sans modifier la note
python scripts/clean_email_note.py --search 'title:"Ollama now supports*"' --dry-run

# Nettoyage (le corps d'origine est sauvegarde dans backups/)
python scripts/clean_email_note.py --id <NOTE_ID>
```

Options : `--all` pour traiter toutes les notes trouvees par `--search`,
`--keep-footer` pour garder le paragraphe de desabonnement, `--file` pour
convertir un fichier local sans passer par Joplin.

Pour eviter le probleme a la source : dans Thunderbird, options de l'extension
Joplin Export > Format : **Plaintext** (texte brut, sans images ; l'extension
repasse en HTML si le mail n'a pas de version texte).

## Format de note genere

```
# <Titre de la video>
<URL YouTube>

<Contenu du resume>
```

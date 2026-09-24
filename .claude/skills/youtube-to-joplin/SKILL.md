---
name: youtube-to-joplin
description: Transcrit une vidéo YouTube et envoie un résumé/synthèse formaté dans Joplin. Utiliser quand l'utilisateur donne un lien YouTube et demande un résumé à enregistrer dans Joplin.
---

# YouTube -> Résumé -> Joplin

Objectif : à partir d'un lien YouTube, récupérer la transcription, en écrire un
résumé/synthèse, et créer une note dans Joplin avec ce format de corps :

```
# <Titre de la vidéo>
<URL YouTube>

<Contenu du résumé>
```

## Étapes

1. **Vérifier la config Joplin**
   - S'assurer qu'un fichier `.env` existe à la racine (sinon le créer à partir de
     `.env.example` et demander à l'utilisateur son `JOPLIN_TOKEN`, visible dans
     Joplin Desktop > Options > Web Clipper, après avoir activé le service).
   - Tester la connexion : `python scripts/send_to_joplin.py --check`
   - Si ça échoue, dire à l'utilisateur d'ouvrir Joplin Desktop et d'activer le
     « Web Clipper Service » (Options > Web Clipper > Activer), puis réessayer.

2. **Récupérer la transcription**
   ```
   python scripts/get_transcript.py "<URL_YOUTUBE>"
   ```
   Retourne un JSON `{id, title, url, subtitle_source, transcript}` sur stdout.
   En cas d'erreur (pas de sous-titres disponibles), le signaler à l'utilisateur
   plutôt que d'inventer un contenu.

3. **Rédiger le résumé**
   À partir du champ `transcript`, écrire une synthèse claire et structurée en
   français (sauf demande contraire) : points clés, structure/logique de la
   vidéo, conclusions éventuelles. Ne pas paraphraser phrase par phrase ; dégager
   l'essentiel. Adapter la longueur à celle de la vidéo.

   **Orthographe : écrire en français correct avec tous les accents et signes
   diacritiques (é, è, ê, à, ç, ô, î, ù…).** Ne jamais les supprimer, même si la
   transcription source en est dépourvue. Les scripts gèrent l'UTF-8.

4. **Construire le corps de la note**
   ```
   # <title>
   <url>

   <résumé>
   ```
   Écrire ce contenu dans un fichier temporaire (scratchpad), encodé en UTF-8.

5. **Créer la note dans Joplin**
   ```
   python scripts/send_to_joplin.py --title "<title>" --body-file <fichier_temp>
   ```
   Par défaut la note est créée dans le carnet `YT-Transcript` (via
   `JOPLIN_NOTEBOOK` dans `.env`), qui est créé automatiquement s'il n'existe
   pas encore. Ajouter `--notebook "<nom>"` si l'utilisateur précise un autre
   carnet cible.

6. Confirmer à l'utilisateur que la note a été créée (titre + carnet).

## Notes

- Les scripts n'appellent aucune IA : la rédaction du résumé (étape 3) est faite
  par Claude directement, pas par un script externe.
- Dépendances Python : voir `requirements.txt` (`pip install -r requirements.txt`).

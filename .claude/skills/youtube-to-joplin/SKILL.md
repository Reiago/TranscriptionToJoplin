---
name: youtube-to-joplin
description: Transcrit une video YouTube et envoie un resume/synthese formate dans Joplin. Utiliser quand l'utilisateur donne un lien YouTube et demande un resume a enregistrer dans Joplin.
---

# YouTube -> Resume -> Joplin

Objectif : a partir d'un lien YouTube, recuperer la transcription, en ecrire un
resume/synthese, et creer une note dans Joplin avec ce format de corps :

```
# <Titre de la video>
<URL YouTube>

<Contenu du resume>
```

## Etapes

1. **Verifier la config Joplin**
   - S'assurer qu'un fichier `.env` existe a la racine (sinon le creer a partir de
     `.env.example` et demander a l'utilisateur son `JOPLIN_TOKEN`, visible dans
     Joplin Desktop > Options > Web Clipper, apres avoir active le service).
   - Tester la connexion : `python scripts/send_to_joplin.py --check`
   - Si ca echoue, dire a l'utilisateur d'ouvrir Joplin Desktop et d'activer le
     "Web Clipper Service" (Options > Web Clipper > Activer), puis reessayer.

2. **Recuperer la transcription**
   ```
   python scripts/get_transcript.py "<URL_YOUTUBE>"
   ```
   Retourne un JSON `{id, title, url, subtitle_source, transcript}` sur stdout.
   En cas d'erreur (pas de sous-titres disponibles), le signaler a l'utilisateur
   plutot que d'inventer un contenu.

3. **Rediger le resume**
   A partir du champ `transcript`, ecrire une synthese claire et structuree en
   francais (sauf demande contraire) : points cles, structure/logique de la
   video, conclusions eventuelles. Ne pas paraphraser phrase par phrase ; degager
   l'essentiel. Adapter la longueur a celle de la video.

4. **Construire le corps de la note**
   ```
   # <title>
   <url>

   <resume>
   ```
   Ecrire ce contenu dans un fichier temporaire (scratchpad).

5. **Creer la note dans Joplin**
   ```
   python scripts/send_to_joplin.py --title "<title>" --body-file <fichier_temp>
   ```
   Par defaut la note est creee dans le carnet `YT-Transcript` (via
   `JOPLIN_NOTEBOOK` dans `.env`), qui est cree automatiquement s'il n'existe
   pas encore. Ajouter `--notebook "<nom>"` si l'utilisateur precise un autre
   carnet cible.

6. Confirmer a l'utilisateur que la note a ete creee (titre + carnet).

## Notes

- Les scripts n'appellent aucune IA : la redaction du resume (etape 3) est faite
  par Claude directement, pas par un script externe.
- Dependances Python : voir `requirements.txt` (`pip install -r requirements.txt`).

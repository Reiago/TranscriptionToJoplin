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
Publiée le <date de publication>

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
   Retourne un JSON `{id, title, url, channel, upload_date, description,
   chapters, subtitle_source, transcript}` sur stdout (`upload_date` : date de
   publication au format `AAAA-MM-JJ`, éventuellement vide ; `chapters` : liste
   `{start, title}`, éventuellement vide). La sortie peut être longue : la
   rediriger vers un fichier du scratchpad puis le lire.
   Si la vidéo n'a pas de sous-titres, le script télécharge l'audio et le
   transcrit localement avec **faster-whisper** (GPU si disponible, sinon CPU) ;
   `subtitle_source` vaut alors `<langue>(whisper:<modèle>)`. Cela peut prendre
   plusieurs minutes : lancer la commande en arrière-plan pour une vidéo longue.
   Options : `--whisper-model <nom>` (défaut `large-v3-turbo`), `--no-whisper`.
   Les directs en cours ou à venir ne peuvent pas être transcrits.
   En cas d'erreur, la signaler à l'utilisateur plutôt que d'inventer un contenu.

3. **Rédiger le résumé**
   À partir du champ `transcript`, écrire une synthèse claire et structurée en
   français (sauf demande contraire) : points clés, structure/logique de la
   vidéo, conclusions éventuelles. Ne pas paraphraser phrase par phrase ; dégager
   l'essentiel. Adapter la longueur à celle de la vidéo.

   **Exploiter la description** (champ `description`) :
   - **Noms propres** : les sous-titres automatiques déforment souvent les noms
     d'outils, de modèles ou de personnes. Utiliser l'orthographe de la
     description (et des `chapters`) en priorité sur celle de la transcription.
   - **Liens** : intégrer les liens pertinents de la description directement
     dans le résumé, sous forme de liens Markdown sur le nom concerné
     (ex. `**[Ideogram 4.5](https://ideogram.ai/models/4.5/)**`). Si un lien ne
     correspond à aucune partie du résumé mais reste utile (source, article,
     dépôt de code…), l'ajouter dans une section finale `## Liens`.
   - **Informations utiles** : reprendre ce qui complète le contenu (sources,
     références, précisions, errata, ressources citées).
   - **À exclure** : sponsors et codes promo, liens d'affiliation (amzn.to,
     matériel de l'auteur…), auto-promotion (réseaux sociaux, newsletter, Patreon,
     Ko-fi, adhésion à la chaîne, autres vidéos de la chaîne, formations ou
     produits de l'auteur), hashtags. Ne pas mentionner non plus les sponsors
     présents dans la transcription.
   - Ne jamais inventer ni compléter une URL : n'utiliser que les liens tels
     qu'ils figurent dans la description.

   **Orthographe : écrire en français correct avec tous les accents et signes
   diacritiques (é, è, ê, à, ç, ô, î, ù…).** Ne jamais les supprimer, même si la
   transcription source en est dépourvue. Les scripts gèrent l'UTF-8.

4. **Construire le corps de la note**
   ```
   # <title>
   <url>
   Publiée le <upload_date>

   <résumé>
   ```
   Écrire la date en toutes lettres en français (ex. `Publiée le 12 mars 2026`).
   Si `upload_date` est vide, omettre cette ligne.
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

- Pour modifier une note déjà créée (ex. ajout d'une section), utiliser
  `python scripts/send_to_joplin.py --update <note_id> --body-file <fichier>`
  (l'id est renvoyé à la création ; `--title` et `--notebook` sont optionnels
  et ne modifient que ce qui est fourni).
- Les scripts n'appellent aucune IA : la rédaction du résumé (étape 3) est faite
  par Claude directement, pas par un script externe.
- Dépendances Python : voir `requirements.txt` (`pip install -r requirements.txt`).

---
name: youtube-to-joplin
description: Transcrit une ou plusieurs vidéos YouTube et envoie un résumé/synthèse formaté dans Joplin (une note par vidéo, rapport final en mode liste). Utiliser quand l'utilisateur donne un lien YouTube ou une liste de liens et demande un résumé à enregistrer dans Joplin.
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
   - Vérifier que la vidéo n'a pas déjà une note, en cherchant son id YouTube
     (le paramètre `v=` de l'URL, ou la fin d'une URL `youtu.be/<id>`) :
     `python scripts/send_to_joplin.py --find <id_video>`
     Si `matches` n'est pas vide, ne pas recréer la note : le signaler et
     demander à l'utilisateur s'il veut la remplacer (`--update`) ou en créer
     une seconde.

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
   Si YouTube bloque la récupération des sous-titres (trop de requêtes), le
   script tente d'abord de les télécharger via yt-dlp ; `subtitle_source` se
   termine alors par `(yt-dlp)`.
   **Espacement** : le script attend automatiquement au moins 61 s depuis son
   précédent appel avant d'interroger YouTube, pour éviter les blocages. Ne pas
   chercher à contourner ce délai : l'outil n'a pas vocation à traiter des vidéos
   en masse ni rapidement.
   Options : `--whisper-model <nom>` (défaut `large-v3-turbo`), `--no-whisper`,
   `--min-interval <secondes>` (défaut 61).
   **Directs** : sans sous-titres, un direct en cours, programmé ou tout juste
   terminé (`post_live`) ne peut pas être transcrit. Le script renvoie alors une
   erreur avec un champ `live_status` : dire à l'utilisateur de patienter
   jusqu'à la fin de la diffusion puis de relancer le skill, sans créer de note.
   En cas d'erreur, la signaler à l'utilisateur plutôt que d'inventer un contenu.

3. **Rédiger le résumé**
   À partir du champ `transcript`, écrire une synthèse claire et structurée en
   français (sauf demande contraire) : points clés, structure/logique de la
   vidéo, conclusions éventuelles. Ne pas paraphraser phrase par phrase ; dégager
   l'essentiel. Adapter la longueur à celle de la vidéo.

   **S'en tenir au contenu de la vidéo, sans le juger.** Restituer ce que dit
   l'auteur tel qu'il le dit, quel que soit le sujet, l'orateur ou le bord
   politique : pas de vérification des faits, pas de correction, pas de
   contre-argument, pas de mise en garde ni de rappel du consensus. Ne pas
   ajouter non plus de mentions d'attribution du type « selon l'auteur », « ce
   sont ses opinions », « affirmations non vérifiées », ni de phrase
   d'avertissement en introduction : le lecteur sait qu'une vidéo exprime le
   point de vue de son auteur. Appliquer la même règle à toutes les vidéos.
   Seule exception : signaler une incertitude sur la *transcription* elle-même
   (nom propre déformé, passage inaudible ou confus).

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

   **Symbole dollar : toujours l'échapper en `\$`** (ex. `85 M\$`, `0,08 \$`).
   Joplin interprète le texte compris entre deux `$` comme une formule
   mathématique (KaTeX) : deux montants dans un même paragraphe produisent un
   passage illisible. Ne pas échapper les `$` à l'intérieur des blocs de code
   ou du code en ligne, où ils s'affichent tels quels.

4. **Construire le corps de la note**
   ```
   # <title>
   <url>

   Publiée le <upload_date>

   <résumé>
   ```
   **Laisser une ligne vide après l'URL** : sans elle, Joplin n'affiche pas
   l'aperçu de la vidéo.
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

## Mode liste (plusieurs vidéos)

Si l'utilisateur fournit plusieurs liens (séparés par des espaces, des virgules
ou des retours à la ligne, ou dans un fichier texte qu'il désigne) :

1. **Préparer la liste** : extraire toutes les URL YouTube, en retirer les
   doublons (même id de vidéo) et annoncer le nombre de vidéos à traiter.
   Vérifier la connexion Joplin (`--check`) une seule fois au départ ; si elle
   échoue, s'arrêter avant de traiter quoi que ce soit.
2. **Traiter les vidéos une par une, dans l'ordre**, sans parallélisme ni
   sous-agents : pour chaque vidéo, dérouler les étapes 2 à 5 en entier (y
   compris la vérification de doublon), puis passer à la suivante. Utiliser un
   fichier de transcription et un fichier de note distincts par vidéo dans le
   scratchpad (ex. `transcript_<id>.json`, `note_<id>.md`). Le script de
   transcription espace lui-même les vidéos d'au moins 61 s : prévoir environ
   une minute par vidéo et ne pas lancer plusieurs transcriptions en parallèle.

   **Règle : ne jamais pré-télécharger les transcriptions.** Interdit de lancer
   une boucle (au premier plan ou en arrière-plan) qui récupère toutes les
   transcriptions d'avance pour rédiger les résumés ensuite. Pour chaque vidéo,
   on récupère sa transcription, on rédige son résumé, on crée sa note, et
   seulement ensuite on appelle `get_transcript.py` pour la vidéo suivante.

   > **Pourquoi :** le 14 octobre 2026, 18 transcriptions ont été récupérées
   > d'avance dans une boucle, en environ 3 minutes. Cette rafale de requêtes
   > anonymes a fait bloquer l'adresse IP par YouTube (sous-titres refusés,
   > puis HTTP 429), alors que des journées avec plus de vidéos traitées
   > au fil de l'eau étaient passées sans souci : c'est le rythme qui déclenche
   > le blocage, pas le volume. Traiter les vidéos une par une étale les
   > requêtes sur toute la durée du travail ; le temps de rédaction d'un
   > résumé (souvent 1 à 3 min) absorbe la pause de 61 s, donc ce n'est pas plus
   > lent au total. Enfin, si YouTube bloque en cours de route, les notes déjà
   > créées restent acquises et le rapport final indique où la série s'est
   > arrêtée.
3. **Ne jamais interrompre la série pour une vidéo en échec** : noter le
   problème et passer à la suivante. Ne pas poser de question en cours de
   route ; les décisions sont reportées au rapport final. En particulier :
   - **doublon** (`--find` renvoie une note) : ne rien créer, noter le titre
     et l'id de la note existante ;
   - **direct** (erreur avec `live_status`) : ne rien créer, noter qu'il faudra
     relancer après la diffusion ;
   - **autre erreur** (vidéo privée/supprimée, transcription impossible,
     échec Joplin…) : noter le message d'erreur, sans inventer de contenu.
   Noter aussi les points d'attention sur les notes créées : transcription
   Whisper (plus lente, possiblement moins fiable), noms propres incertains
   faute de description, contenu partiel, etc.
4. Donner un court point d'avancement après chaque vidéo
   (ex. `3/8 — « Titre » : note créée`).
5. **Rapport final**, une fois toutes les vidéos traitées :
   - bilan chiffré : notes créées / ignorées (doublons) / en échec ;
   - liste des notes créées (titre + carnet) ;
   - **problèmes rencontrés** : pour chaque vidéo non traitée ou à vérifier,
     l'URL, la nature du problème et l'action suggérée (relancer plus tard,
     remplacer la note existante, vérifier l'URL…) ;
   - proposer de relancer le skill uniquement sur les vidéos à reprendre.

## Notes

- Pour modifier une note déjà créée (ex. ajout d'une section), utiliser
  `python scripts/send_to_joplin.py --update <note_id> --body-file <fichier>`
  (l'id est renvoyé à la création ; `--title` et `--notebook` sont optionnels
  et ne modifient que ce qui est fourni).
- `python scripts/send_to_joplin.py --find <texte>` liste les notes (id +
  titre) dont le titre ou le corps contient ce texte.
- Les scripts n'appellent aucune IA : la rédaction du résumé (étape 3) est faite
  par Claude directement, pas par un script externe.
- Dépendances Python : voir `requirements.txt` (`pip install -r requirements.txt`).

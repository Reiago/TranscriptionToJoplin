---
name: clean-email-note
description: Rend lisible une note Joplin importée depuis un mail HTML (extension Thunderbird « Joplin Export ») en la convertissant en Markdown propre. Utiliser quand l'utilisateur signale une note Joplin illisible à cause du HTML d'un mail, ou demande de nettoyer une note issue d'un mail/newsletter.
---

# Nettoyer une note Joplin importée depuis un mail

Les mails HTML exportés depuis Thunderbird arrivent dans Joplin sous forme de
tableaux HTML de mise en page, presque illisibles. Le script
`scripts/clean_email_note.py` les convertit en Markdown : texte, titres, listes
et images conservés ; liens de tracking remplacés par leur vraie destination ;
pixels espions, icônes, avatars et pied de désabonnement supprimés.

## Étapes

1. **Vérifier la connexion Joplin** : `python scripts/send_to_joplin.py --check`
   (si ça échoue, demander d'ouvrir Joplin Desktop et d'activer le « Web Clipper
   Service »).

2. **Identifier la note**
   - Les notes importées par l'extension ont un titre de la forme
     `<Objet du mail> from <Expéditeur> <adresse>`.
   - Chercher avec une requête ciblée sur le titre, par exemple
     `--search 'title:"Comfy Agent: The First*"'`.
   - Si plusieurs notes correspondent, le script refuse et liste les candidates
     (sur stderr) : choisir la bonne et relancer avec `--id <NOTE_ID>`, ou
     demander à l'utilisateur en cas de doute.
   - **Ne pas utiliser `--all` sur une recherche large** : les pages enregistrées
     par le Web Clipper contiennent le même type de HTML et seraient réécrites.
     `--all` ne sert que si l'utilisateur demande explicitement plusieurs mails
     précis.

3. **Prévisualiser**
   ```
   python scripts/clean_email_note.py --id <NOTE_ID> --dry-run > <fichier_scratchpad>
   ```
   Le Markdown obtenu va sur stdout, le rapport JSON (`avant`/`apres` en
   caractères) sur stderr. Relire le résultat : le texte principal du mail doit
   être présent. Si du contenu utile manque, ne pas appliquer et le signaler.

4. **Appliquer**
   ```
   python scripts/clean_email_note.py --id <NOTE_ID>
   ```
   Le corps d'origine est sauvegardé automatiquement dans `backups/` (chemin
   indiqué dans le champ `sauvegarde` du JSON). Une note sans HTML renvoie
   `"status": "rien a nettoyer"` et n'est pas modifiée.

5. **Finitions éventuelles** (optionnel, si l'utilisateur veut une note plus
   soignée) : le script laisse parfois du bruit propre à l'expéditeur (boutons
   « Like / Comment / Share », « Read in app », liens Substack
   `substack.com/redirect/<uuid>` non décodables). Les retirer à la main en
   récupérant le corps, en l'éditant dans le scratchpad, puis
   `python scripts/send_to_joplin.py --update <NOTE_ID> --body-file <fichier>`.
   Ne jamais inventer une URL de destination pour un lien non décodé.

6. Confirmer à l'utilisateur : titre de la note, taille avant/après, chemin de
   la sauvegarde.

## Notes

- Options : `--keep-footer` conserve le paragraphe de désabonnement ; `--file
  <chemin>` convertit un fichier local sans passer par Joplin.
- Pour éviter le problème à la source : dans Thunderbird, options de
  l'extension Joplin Export > **Format : Plaintext** (texte brut, sans images ;
  l'extension repasse en HTML si le mail n'a pas de version texte).

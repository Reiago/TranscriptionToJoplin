#!/usr/bin/env python3
"""Nettoie une note Joplin importee depuis un mail HTML (extension Thunderbird
"Joplin Export") : convertit le HTML de mise en page en markdown lisible,
decode les liens de tracking et supprime les pixels espions."""
import argparse
import base64
import html
import json
import os
import re
import sys

if os.name == "nt" and not sys.flags.utf8_mode:
    # Sans le mode UTF-8, Windows decode argv avec la codepage console et
    # corrompt les caracteres accentues (ex: --search avec des accents).
    import subprocess

    result = subprocess.run([sys.executable, "-X", "utf8", __file__] + sys.argv[1:])
    sys.exit(result.returncode)

from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv

from send_to_joplin import get_base_url, get_token

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"

# Balises HTML reconnues ; tout le reste (ex: "<hello@ollama.com>" dans le
# markdown de Joplin) est conserve tel quel.
KNOWN_TAGS = {
    "a", "abbr", "address", "article", "b", "big", "blockquote", "body", "br", "center",
    "code", "col", "colgroup", "dd", "del", "div", "dl", "dt", "em", "font", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hr", "html", "i", "img", "ins",
    "kbd", "li", "link", "main", "mark", "meta", "ol", "p", "pre", "s", "section", "small",
    "span", "strike", "strong", "style", "sub", "sup", "table", "tbody", "td", "tfoot",
    "th", "thead", "time", "title", "tr", "tt", "u", "ul", "wbr", "script", "noscript", "figure",
    "figcaption", "picture", "source", "nav", "label", "o:p",
}
VOID_TAGS = {"br", "col", "hr", "img", "link", "meta", "source", "wbr"}
BLOCK_TAGS = {
    "address", "article", "blockquote", "body", "center", "dd", "div", "dl", "dt", "figure",
    "figcaption", "footer", "header", "html", "main", "nav", "p", "section", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr",
}
SKIP_TAGS = {"head", "noscript", "script", "style", "title"}
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|mso-hide\s*:\s*all|opacity\s*:\s*0(?![.\d])",
    re.I,
)
INVISIBLE_CHARS = re.compile("[\u00ad\u034f\u200b-\u200f\u2060\ufeff]")
UNSUBSCRIBE = re.compile(
    r"unsubscribe|d[ée]sabonn|d[ée]sinscri|opt[-_ ]?out|manage[-_ ]?(your[-_ ])?(preferences|subscription)",
    re.I,
)
RESOURCE_IMG = re.compile(r"!\[[^\]\n]*\]\(:/([0-9a-f]{32})\)")
# Une ressource image plus petite que ca est un pixel de suivi.
PIXEL_MAX_BYTES = 200
# Une image HTML affichee a cette taille ou moins est un pixel, une icone ou un avatar.
ICON_MAX_PX = 48


def unwrap_url(url: str) -> str:
    """Remplace un lien de redirection/tracking par l'URL de destination."""
    for _ in range(3):
        parts = urlsplit(url)
        # Ex: https://c.vialoops.com/CL0/https:%2F%2Follama.com%2Fdownload/1/...
        match = re.search(r"/(https?(?::|%3A)(?:%2F){2}[^/]+)", parts.path, re.I)
        if match:
            url = unquote(match.group(1))
            continue
        # Ex: ...?url=https%3A%2F%2F... (Outlook safelinks, Google, etc.)
        for _key, value in parse_qsl(parts.query):
            if re.match(r"https?://", value) and not value.startswith(f"{parts.scheme}://{parts.netloc}"):
                url = value
                break
        else:
            # Ex: https://substack.com/redirect/2/<base64 {"e": "https://..."}>.<signature>
            target = next(filter(None, map(decode_b64_url, parts.path.split("/"))), None)
            if not target:
                break
            url = target
    parts = urlsplit(url)
    if parts.query:
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith(("utm_", "mc_")) and k.lower() not in {"ref_src", "_hsenc", "_hsmi"}]
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url


def decode_b64_url(segment: str) -> str | None:
    """Decode un segment base64url contenant un JSON avec une URL (redirections Substack)."""
    payload = segment.split(".")[0]
    if len(payload) < 20 or not re.fullmatch(r"[A-Za-z0-9_-]+", payload):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str) and re.match(r"https?://", value):
                return value
    return None


def is_decoration(attrs: dict) -> bool:
    """Pixel de suivi, icone (j'aime, partage...) ou avatar : sans interet dans une note."""
    style = attrs.get("style") or ""
    for key in ("width", "height"):
        value = (attrs.get(key) or "").strip().removesuffix("px")
        match = re.search(rf"(?<![-\w]){key}\s*:\s*(\d+)px", style, re.I)
        if value.isdigit() and int(value) <= ICON_MAX_PX or match and int(match.group(1)) <= ICON_MAX_PX:
            return True
    return bool(HIDDEN_STYLE.search(style))


class MailToMarkdown(HTMLParser):
    """Convertit le HTML d'un mail en markdown. Le texte hors balises HTML
    (deja du markdown, produit par Joplin) est recopie sans modification."""

    def __init__(self, html_only: bool = False):
        super().__init__(convert_charrefs=False)
        self.html_only = html_only
        self.out: list[str] = []
        self.stack: list[tuple[str, int | None, dict]] = []  # (tag, index de debut, infos)
        self.skip_depth = 0
        self.pre_depth = 0
        self.list_stack: list[list] = []  # ["ul"|"ol", compteur]

    # -- outils -------------------------------------------------------------
    @property
    def in_html(self) -> bool:
        return self.html_only or bool(self.stack)

    def emit(self, text: str) -> None:
        if not self.skip_depth:
            self.out.append(text)

    def block(self) -> None:
        self.emit("\n\n")

    def collected(self, start: int) -> str:
        text = "".join(self.out[start:])
        del self.out[start:]
        return text

    # -- parseur ------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag not in KNOWN_TAGS:
            self.handle_unknown(self.get_starttag_text())
            return
        attrs = {k: v or "" for k, v in attrs}
        if tag in VOID_TAGS:
            self.handle_void(tag, attrs)
            return

        hidden = tag in SKIP_TAGS or bool(HIDDEN_STYLE.search(attrs.get("style", "")))
        if hidden:
            self.skip_depth += 1
        info = {"hidden": hidden, "attrs": attrs}
        if tag in BLOCK_TAGS:
            self.block()
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.block()
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
            self.block()
        elif tag == "li":
            # L'indentation des sous-listes est ajoutee a la fermeture du <li> parent.
            if self.list_stack and self.list_stack[-1][0] == "ol":
                self.list_stack[-1][1] += 1
                bullet = f"{self.list_stack[-1][1]}. "
            else:
                bullet = "- "
            self.emit("\n" + bullet)
        elif tag == "pre":
            self.pre_depth += 1
            self.block()
        self.stack.append((tag, len(self.out), info))

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS or tag not in KNOWN_TAGS:
            self.handle_starttag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_void(self, tag, attrs):
        if tag == "br":
            self.emit("\n")
        elif tag == "hr":
            self.emit("\n\n---\n\n")
        elif tag == "img" and not is_decoration(attrs):
            src = attrs.get("src", "").strip()
            if src and not src.startswith("data:"):
                alt = " ".join(attrs.get("alt", "").split()).replace("]", "")
                self.emit(f"![{alt}]({src})")

    def handle_endtag(self, tag):
        if tag not in KNOWN_TAGS or tag in VOID_TAGS:
            if tag not in KNOWN_TAGS:
                self.handle_unknown(f"</{tag}>")
            return
        if not any(t == tag for t, _, _ in self.stack):
            return  # balise fermante orpheline
        while self.stack:
            open_tag, start, info = self.stack.pop()
            self.close_element(open_tag, start, info)
            if open_tag == tag:
                break

    def close_element(self, tag, start, info):
        if info["hidden"]:
            self.skip_depth -= 1
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = " ".join(self.collected(start).split())
            if text:
                self.emit("#" * int(tag[1]) + " " + text.replace("**", ""))
            self.block()
        elif tag == "a":
            text = " ".join(self.collected(start).split())
            href = info["attrs"].get("href", "").strip()
            if not text:
                return
            if not href or href.startswith("#") or ("](" in text and not text.startswith("![")):
                self.emit(text)
            else:
                self.emit(f"[{text}]({unwrap_url(html.unescape(href))})")
        elif tag in ("b", "strong", "em", "i"):
            text = self.collected(start)
            marker = "**" if tag in ("b", "strong") else "*"
            if text.strip() and "\n" not in text.strip() and marker not in text:
                lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", text, re.S).groups()
                self.emit(f"{lead}{marker}{core}{marker}{trail}")
            else:
                self.emit(text)
        elif tag == "code" and not self.pre_depth:
            text = self.collected(start)
            if text.strip():
                self.emit(f"`{text.strip()}`")
        elif tag == "pre":
            self.pre_depth -= 1
            text = self.collected(start).strip("\n")
            text = re.sub(r"^`|`$", "", text) if text.count("`") == 2 else text
            if text.strip():
                self.emit(f"\n\n```\n{text}\n```\n\n")
        elif tag == "li":
            # Les <p>/<div> internes ne doivent pas separer la puce de son texte.
            lines = re.sub(r"\n[ \t]*(?:\n[ \t]*)+", "\n", self.collected(start).strip()).split("\n")
            self.emit("\n  ".join(line.rstrip() for line in lines if line.strip()))
        elif tag == "blockquote":
            text = self.collected(start).strip()
            if text:
                self.emit("\n\n" + "\n".join("> " + line for line in text.splitlines()) + "\n\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self.block()
        elif tag in BLOCK_TAGS:
            self.block()

    def handle_data(self, data):
        if not self.in_html:
            self.emit(data)
        elif self.pre_depth:
            self.emit(data)
        else:
            self.emit(re.sub(r"\s+", " ", data))

    def handle_entityref(self, name):
        self.handle_ref(f"&{name};")

    def handle_charref(self, name):
        self.handle_ref(f"&#{name};")

    def handle_ref(self, ref):
        if self.in_html:
            self.handle_data(html.unescape(ref))
        else:
            self.emit(ref)

    def handle_unknown(self, raw):
        self.handle_data(raw if not self.in_html else html.unescape(raw))

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def convert(self, body: str) -> str:
        self.feed(body)
        self.finish()
        return "".join(self.out)

    def finish(self):
        super().close()
        while self.stack:
            tag, start, info = self.stack.pop()
            self.close_element(tag, start, info)


def tidy(markdown: str, keep_footer: bool = False) -> str:
    text = INVISIBLE_CHARS.sub("", markdown).replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+(?=[^ \t\-*>\d])", "\n", text)
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", text)]
    result = []
    for b in blocks:
        if not b.strip():
            continue
        if not keep_footer and UNSUBSCRIBE.search(b) and len(b) < 1200:
            continue
        if result and b == result[-1]:
            continue  # bloc duplique (version mobile/desktop d'un meme contenu)
        result.append(b)
    text = "\n\n".join(result)
    # Des blocs vides entre deux <li> laissent des lignes vides entre les puces.
    list_gap = re.compile(r"(?m)^([ ]*(?:-|\d+\.) .*)\n\n(?=[ ]*(?:-|\d+\.) )")
    while list_gap.search(text):
        text = list_gap.sub(r"\1\n", text)
    return text.strip() + "\n"


def clean_body(body: str, html_only: bool = False, keep_footer: bool = False, is_pixel_resource=None) -> str:
    markdown = MailToMarkdown(html_only=html_only).convert(body)
    if is_pixel_resource:
        markdown = RESOURCE_IMG.sub(lambda m: "" if is_pixel_resource(m.group(1)) else m.group(0), markdown)
    return tidy(markdown, keep_footer=keep_footer)


# -- API Joplin --------------------------------------------------------------
def api_get(path: str, **params) -> dict:
    resp = requests.get(f"{get_base_url()}{path}", params={"token": get_token(), **params}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def is_pixel_resource(resource_id: str) -> bool:
    try:
        res = api_get(f"/resources/{resource_id}", fields="mime,size")
    except requests.HTTPError:
        return False
    return res.get("mime", "").startswith("image/") and int(res.get("size") or 0) <= PIXEL_MAX_BYTES


def find_notes(query: str) -> list[dict]:
    notes, page = [], 1
    while True:
        data = api_get("/search", query=query, fields="id,title", page=page)
        notes += data.get("items", [])
        if not data.get("has_more"):
            return notes
        page += 1


def clean_note(note_id: str, dry_run: bool, keep_footer: bool) -> dict:
    note = api_get(f"/notes/{note_id}", fields="id,title,body,markup_language")
    html_only = note.get("markup_language") == 2
    body = note["body"]
    if not html_only and not re.search(r"<(table|div|td|span|p)\b", body, re.I):
        return {"id": note_id, "title": note["title"], "status": "rien a nettoyer"}

    cleaned = clean_body(body, html_only, keep_footer, is_pixel_resource)
    if dry_run:
        print(cleaned)
        return {"id": note_id, "title": note["title"], "status": "dry-run",
                "avant": len(body), "apres": len(cleaned)}

    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"{note_id}-{datetime.now():%Y%m%d-%H%M%S}.{'html' if html_only else 'md'}"
    backup.write_text(body, encoding="utf-8")

    payload = {"body": cleaned}
    if html_only:
        payload["markup_language"] = 1
    resp = requests.put(f"{get_base_url()}/notes/{note_id}", params={"token": get_token()},
                        json=payload, timeout=15)
    resp.raise_for_status()
    return {"id": note_id, "title": note["title"], "status": "nettoyee",
            "avant": len(body), "apres": len(cleaned), "sauvegarde": str(backup)}


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Rend lisible une note Joplin importee depuis un mail HTML "
        "(conversion en markdown, liens de tracking decodes, pixels espions retires)."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--id", help="ID de la note a nettoyer")
    target.add_argument("--search", help="Recherche Joplin (ex: \"Ollama\" ou 'title:\"Comfy*\"')")
    target.add_argument("--file", help="Convertit un fichier local et affiche le resultat (sans Joplin)")
    parser.add_argument("--all", action="store_true", help="Avec --search : nettoie toutes les notes trouvees")
    parser.add_argument("--dry-run", action="store_true", help="Affiche le resultat sans modifier la note")
    parser.add_argument("--keep-footer", action="store_true",
                        help="Conserve les paragraphes de desabonnement en pied de mail")
    args = parser.parse_args()

    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
        html_only = bool(re.match(r"\s*(<!doctype|<html)", body, re.I))
        print(clean_body(body, html_only, args.keep_footer), end="")
        return

    try:
        if args.id:
            ids = [args.id]
        else:
            notes = find_notes(args.search)
            if not notes:
                parser.error(f"aucune note ne correspond a : {args.search}")
            if len(notes) > 1 and not args.all:
                print(json.dumps({"error": "plusieurs notes correspondent ; preciser la recherche, "
                                  "utiliser --id ou ajouter --all", "notes": notes},
                                 ensure_ascii=False, indent=2), file=sys.stderr)
                sys.exit(2)
            ids = [n["id"] for n in notes]
        for note_id in ids:
            report = clean_note(note_id, args.dry_run, args.keep_footer)
            print(json.dumps(report, ensure_ascii=False), file=sys.stderr if args.dry_run else sys.stdout)
    except requests.RequestException as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

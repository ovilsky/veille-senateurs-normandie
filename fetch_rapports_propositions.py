#!/usr/bin/env python3
"""
Récupère les rapports et propositions de loi des sénateurs normands suivis
(voir senateurs_config.py) depuis senat.fr, écrit un fichier JSON.

Source (vérifiée le 08/09/2026) :
  - Rapports : /rapports-senateur/{slug}.html (session en cours),
    /rapports-senateur/{slug}{annee_debut_session}.html (sessions passées).
    Deux sous-catégories sur chaque page : "Rapports d'information" et
    "Rapports législatifs". Chaque entrée a une commission, un titre, un
    type+numéro (très variable : "Rapport d'information numéro 813",
    "Avis numéro 335", "Rapport général Tome III Annexe 10 Volume 2"...),
    parfois un lien vers une synthèse ("L'Essentiel"), et une date.
  - Propositions de loi/résolution : /propositions-de-loi/{slug}.html
    (session en cours), /propositions-de-loi/{slug}{annee}.html (passées).
    Deux sous-catégories : dont le sénateur est AUTEUR, et dont il est
    COSIGNATAIRE — distinction importante à conserver (comme pour le
    projet députés, auteur ≠ cosignataire).

IMPORTANT sur les dates : contrairement aux questions écrites (format
JJ/MM/AAAA), les propositions de loi affichent des dates en toutes lettres
("1er juillet 2026", "6 mai 2026") — le script les convertit en JJ/MM/AAAA
pour rester cohérent avec le reste des données.

Comme pour les questions écrites, ce module n'a pas pu être testé contre
le vrai site depuis le bac à sable de conception (accès réseau restreint) :
seule la structure des pages a été vérifiée via des outils de recherche/
consultation web. Fixtures + tests hors-ligne fournis pour validation
avant le premier run réel.
"""

import json
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from senateurs_config import SENATEURS

HEADERS = {
    "User-Agent": "VeilleSenateursNormandie/1.0 (usage redaction locale ; contact: redaction@example.fr)"
}
BASE = "https://www.senat.fr"
REQUEST_DELAY = 1.0

# Sessions à parcourir : None = session en cours (pas de suffixe dans l'URL),
# 2024 = session précédente (2024-2025). Ajuster pour un historique plus
# profond (chaque session ajoutée = 2 x 17 sénateurs x 2 catégories de pages
# supplémentaires à récupérer).
SESSION_SUFFIXES = [None, 2024]

MONTHS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12,
}


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"  # cf. bug d'encodage rencontré sur les questions écrites
    return BeautifulSoup(resp.text, "html.parser")


def parse_french_date(text):
    """Convertit "1er juillet 2026" ou "6 mai 2026" en "01/07/2026" / "06/05/2026"."""
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéûôA-ZÉÛÔ]+)\s+(\d{4})", text)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = MONTHS_FR.get(month_name.lower())
    if not month:
        return None
    return f"{int(day):02d}/{int(month):02d}/{year}"


def find_date_ddmmyyyy(text):
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    return m.group(0) if m else None


def absolute_url(href):
    if href.startswith("http"):
        return href
    return BASE + href


# ---------- Propositions de loi ----------

PROPOSITION_LINK_RE = re.compile(r"/dossier-legislatif/(ppl|ppr)[\w-]*\.html$")


def parse_propositions_page(soup, senateur, seen_urls):
    """
    Repère chaque proposition via son lien (fiable), puis détermine le
    rôle (auteur/cosignataire) et la date à partir du texte aplati de la
    page plutôt que de balises précises (h2/li...) : on ne sait pas quelle
    structure HTML exacte utilise senat.fr, donc on évite d'en dépendre.

    Principe : la page contient toujours la phrase "... est l'auteur"
    avant la liste des propositions dont il est auteur, et "...est
    cosignataire" avant celles dont il est cosignataire. On repère la
    position de cette deuxième phrase dans le texte, et tout lien situé
    après cette position est un "cosignataire", tout lien avant est un
    "auteur".
    """
    results = []
    full_text = re.sub(r"\s+", " ", soup.get_text(" "))

    cosign_match = re.search(r"est\s+cosignataire", full_text, re.I)
    cosign_pos = cosign_match.start() if cosign_match else None

    cursor = 0
    for link in soup.find_all("a", href=PROPOSITION_LINK_RE):
        href = link["href"]
        url = absolute_url(href)
        if url in seen_urls:
            continue

        titre = link.get_text(" ", strip=True)
        if not titre:
            continue

        pos = full_text.find(titre, cursor)
        if pos == -1:
            pos = full_text.find(titre)  # repli : recherche depuis le début
        role = "cosignataire" if (cosign_pos is not None and pos != -1 and pos > cosign_pos) else "auteur"

        after = full_text[pos + len(titre): pos + len(titre) + 60] if pos != -1 else ""
        date_depot = parse_french_date(after)

        if pos != -1:
            cursor = pos + len(titre)

        seen_urls.add(url)
        results.append({
            "type": "proposition_de_loi",
            "titre": titre,
            "role": role,
            "senateur_slug": senateur["slug"],
            "senateur_nom": senateur["nom"],
            "senateur_dept": senateur["dept"],
            "date_depot": date_depot,
            "url": url,
        })

    return results


def fetch_propositions(senateur):
    all_results = []
    seen_urls = set()
    for suffix in SESSION_SUFFIXES:
        slug = senateur["slug"]
        url = f"{BASE}/propositions-de-loi/{slug}{suffix if suffix else ''}.html"
        try:
            soup = get(url)
        except requests.RequestException as e:
            print(f"    Erreur propositions {senateur['nom']} ({url}) : {e}", file=sys.stderr)
            continue
        time.sleep(REQUEST_DELAY)
        all_results.extend(parse_propositions_page(soup, senateur, seen_urls))
    return all_results


# ---------- Rapports ----------

# Liens vers un document de rapport (pas vers sa synthèse, reconnaissable
# au suffixe -syn.pdf).
RAPPORT_LINK_RE = re.compile(r"/(rap|notice-rapport)/[\w./-]+\.(html|pdf)$")
SYNTHESE_SUFFIX_RE = re.compile(r"-syn\.pdf$")

SECTION_INFO_RE = re.compile(r"rapports?\s+d.information", re.I)
SECTION_LEGISLATIF_RE = re.compile(r"rapports?\s+l[ée]gislatifs?", re.I)
# Le texte étant aplati (plus de retours à la ligne pour délimiter), on
# borne la capture à 90 caractères et on s'arrête dès qu'on croise un mot
# commençant par une majuscule précédé d'un espace (le titre qui suit
# commence toujours par une majuscule) — sinon [^\n]* engloutirait le
# titre entier faute de retour à la ligne pour l'arrêter.
COMMISSION_RE = re.compile(
    r"de la (?:[Cc]ommission|[Dd][ée]l[ée]gation)\b.{0,90}?(?=\s+[A-ZÀ-ÜÉÈÊËÎÏ]|$)"
)


def parse_rapports_page(soup, senateur, seen_urls):
    """
    Repère chaque rapport via son lien type+numéro (fiable, et jamais un
    lien de synthèse -syn.pdf), puis retrouve commission/titre/catégorie/
    date à partir du texte aplati de la page autour de ce lien — même
    principe que parse_propositions_page : on ne suppose aucune balise
    HTML précise.
    """
    results = []
    full_text = re.sub(r"\s+", " ", soup.get_text(" "))

    # On repère TOUTES les occurrences des titres de section (le texte
    # d'introduction de la page contient souvent une phrase du type "la
    # liste des rapports d'information et des rapports législatifs", qui
    # matcherait aussi les deux motifs si on ne prenait que la première
    # occurrence — d'où l'utilisation d'un repère "le plus récent avant
    # ce lien" plutôt qu'une simple position unique).
    section_markers = []
    for m in SECTION_INFO_RE.finditer(full_text):
        section_markers.append((m.start(), "information"))
    for m in SECTION_LEGISLATIF_RE.finditer(full_text):
        section_markers.append((m.start(), "legislatif"))
    section_markers.sort()

    def categorie_for_pos(pos):
        cat = None
        for marker_pos, marker_cat in section_markers:
            if marker_pos < pos:
                cat = marker_cat
            else:
                break
        return cat

    cursor = 0
    for link in soup.find_all("a", href=RAPPORT_LINK_RE):
        href = link["href"]
        if SYNTHESE_SUFFIX_RE.search(href):
            continue
        url = absolute_url(href)
        if url in seen_urls:
            continue

        type_numero = link.get_text(" ", strip=True)
        if not type_numero:
            continue

        pos = full_text.find(type_numero, cursor)
        if pos == -1:
            pos = full_text.find(type_numero)
        if pos == -1:
            continue  # texte du lien introuvable dans le texte aplati : cas limite, on ignore

        categorie = categorie_for_pos(pos)

        before = full_text[max(0, pos - 300):pos]
        after = full_text[pos + len(type_numero): pos + len(type_numero) + 150]

        commission_matches = list(COMMISSION_RE.finditer(before))
        commission = commission_matches[-1].group(0) if commission_matches else None

        # Le titre est le texte entre la commission (si trouvée, sinon le
        # début de la fenêtre) et le lien lui-même.
        titre_zone = before[commission_matches[-1].end():] if commission_matches else before
        titre = re.sub(r"^\s*\d+\.\s*", "", titre_zone).strip(" .")
        if not titre:
            titre = None

        date_publication = find_date_ddmmyyyy(after)

        cursor = pos + len(type_numero)
        seen_urls.add(url)
        results.append({
            "type": "rapport",
            "categorie": categorie,
            "commission": commission,
            "titre": titre,
            "type_numero": type_numero,
            "senateur_slug": senateur["slug"],
            "senateur_nom": senateur["nom"],
            "senateur_dept": senateur["dept"],
            "date_publication": date_publication,
            "url": url,
        })

    return results


def fetch_rapports(senateur):
    all_results = []
    seen_urls = set()
    for suffix in SESSION_SUFFIXES:
        slug = senateur["slug"]
        url = f"{BASE}/rapports-senateur/{slug}{suffix if suffix else ''}.html"
        try:
            soup = get(url)
        except requests.RequestException as e:
            print(f"    Erreur rapports {senateur['nom']} ({url}) : {e}", file=sys.stderr)
            continue
        time.sleep(REQUEST_DELAY)
        all_results.extend(parse_rapports_page(soup, senateur, seen_urls))
    return all_results


# ---------- Orchestration ----------

def main():
    all_propositions = []
    all_rapports = []

    for senateur in SENATEURS:
        print(f"--- {senateur['nom']} ---", file=sys.stderr)
        props = fetch_propositions(senateur)
        raps = fetch_rapports(senateur)
        print(f"    {len(props)} proposition(s), {len(raps)} rapport(s)", file=sys.stderr)
        all_propositions.extend(props)
        all_rapports.extend(raps)

    output = {
        "generated_at": datetime.now().isoformat(),
        "propositions_de_loi": all_propositions,
        "rapports": all_rapports,
    }

    with open("rapports-propositions-senateurs-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(
        f"\n{len(all_propositions)} proposition(s) et {len(all_rapports)} rapport(s) au total.",
        file=sys.stderr,
    )
    print("Écrit dans rapports-propositions-senateurs-data.json", file=sys.stderr)


if __name__ == "__main__":
    main()

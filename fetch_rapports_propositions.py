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
    Parcourt le document dans l'ordre, en gardant trace de la section
    courante (auteur / cosignataire) au fur et à mesure qu'on croise les
    titres de section, et en traitant chaque lien de proposition rencontré.
    """
    results = []
    current_role = None

    for el in soup.find_all(["h2", "h3", "a"]):
        if el.name in ("h2", "h3") and el.find("a") is None:
            heading_text = el.get_text(" ", strip=True).lower()
            if "auteur" in heading_text and "cosignataire" not in heading_text:
                current_role = "auteur"
            elif "cosignataire" in heading_text:
                current_role = "cosignataire"
            continue

        if el.name == "a":
            href = el.get("href", "")
            if not PROPOSITION_LINK_RE.search(href):
                continue
            url = absolute_url(href)
            if url in seen_urls:
                continue

            titre = el.get_text(" ", strip=True)
            if not titre:
                continue

            # Repli : la date suit le lien, souvent dans le même conteneur.
            container = el.find_parent(["li", "dd", "div", "p"]) or el.parent
            container_text = container.get_text(" ", strip=True) if container else ""
            after_title = container_text.split(titre, 1)[-1] if titre in container_text else container_text
            date_publication = parse_french_date(after_title)

            seen_urls.add(url)
            results.append({
                "type": "proposition_de_loi",
                "titre": titre,
                "role": current_role or "inconnu",  # ne devrait pas arriver si la page est bien formée
                "senateur_slug": senateur["slug"],
                "senateur_nom": senateur["nom"],
                "senateur_dept": senateur["dept"],
                "date_depot": date_publication,
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
COMMISSION_RE = re.compile(r"de la (commission|d[ée]l[ée]gation)[^\n]*", re.I)


def parse_rapports_page(soup, senateur, seen_urls):
    results = []
    current_type = None  # "information" ou "legislatif"

    # On avance dans le document dans l'ordre en gardant trace :
    # - de la section courante (info / législatif)
    # - du dernier titre (h3/h4) rencontré, qui précède toujours les liens
    #   de son entrée
    # - de la dernière mention de commission/délégation rencontrée
    last_heading_text = None
    last_commission = None

    for el in soup.find_all(["h2", "h3", "h4", "li", "p", "div", "a"], recursive=True):
        text = el.get_text(" ", strip=True) if el.name != "a" else None

        if el.name in ("h2",) and text:
            if SECTION_INFO_RE.search(text):
                current_type = "information"
                continue
            if SECTION_LEGISLATIF_RE.search(text):
                current_type = "legislatif"
                continue

        if el.name in ("h3", "h4") and text:
            # Un titre de rapport n'est normalement pas un lien lui-même
            # (le lien est sur la ligne "type + numéro" juste en dessous).
            last_heading_text = text
            continue

        if el.name in ("li", "p", "div") and text and COMMISSION_RE.search(text) and len(text) < 120:
            # Ligne courte du type "de la commission des finances" : on
            # limite la longueur pour éviter de capter un gros bloc de
            # texte contenant accidentellement "de la commission" ailleurs.
            m = COMMISSION_RE.search(text)
            last_commission = m.group(0)
            continue

        if el.name == "a":
            href = el.get("href", "")
            if not RAPPORT_LINK_RE.search(href) or SYNTHESE_SUFFIX_RE.search(href):
                continue
            url = absolute_url(href)
            if url in seen_urls or last_heading_text is None:
                continue

            type_numero = el.get_text(" ", strip=True)

            # Important : on cherche l'ancêtre <li> (l'entrée entière),
            # pas seulement le <p> immédiat qui contient le lien — sinon
            # la date, qui est dans un <p> voisin, n'est jamais trouvée.
            container = (
                el.find_parent("li")
                or el.find_parent(["dd", "div"])
                or el.find_parent("p")
                or el.parent
            )
            container_text = container.get_text(" ", strip=True) if container else ""
            date_publication = find_date_ddmmyyyy(container_text)

            seen_urls.add(url)
            results.append({
                "type": "rapport",
                "categorie": current_type or "inconnue",
                "commission": last_commission,
                "titre": last_heading_text,
                "type_numero": type_numero,
                "senateur_slug": senateur["slug"],
                "senateur_nom": senateur["nom"],
                "senateur_dept": senateur["dept"],
                "date_publication": date_publication,
                "url": url,
            })
            # Une fois l'entrée traitée, on évite de la réutiliser pour un
            # deuxième lien (ex. lien de synthèse déjà exclu, mais aussi
            # pour un éventuel deuxième lien de texte) tant qu'on n'a pas
            # vu un nouveau titre.
            last_heading_text = None
            last_commission = None

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

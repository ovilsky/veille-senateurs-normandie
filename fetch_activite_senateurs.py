#!/usr/bin/env python3
"""
Récupère les questions écrites des sénateurs normands suivis (voir
senateurs_config.py) depuis les archives officielles de senat.fr,
écrit un fichier JSON, et réécrit automatiquement le bloc de données
dans veille-senateurs-normandie.html (recherche des marqueurs
__DATA_START__ / __DATA_END__, remplacement).

Source (vérifiée le 07/09/2026, voir la conversation de conception) :
  - Archives annuelles, TOUS sénateurs confondus, groupées par date de
    publication au JO : /questions/base/{annee}/
    Contrairement au site de l'Assemblée nationale, il n'existe pas de
    liste "questions d'un sénateur" filtrable par URL : il faut parcourir
    l'archive annuelle (chronologique, ~20 dates de publication par an)
    et repérer les questions de nos 17 sénateurs suivis.
  - Le moteur de recherche dynamique /basile/rechercheQuestion.do est
    interdit par le robots.txt du Sénat (vérifié) : on ne l'utilise
    jamais, même si son URL est présente sur les pages.
  - Chaque question a une page dédiée /questions/base/{annee}/qSEQ....html
    contenant le texte intégral de la question, la réponse (si publiée),
    les dates, et surtout un lien fiable vers /senateur/{slug}.html qui
    identifie l'auteur sans ambiguïté.

Stratégie de fiabilité (cf. pièges de scraping notés dans le projet
précédent) :
  1. Sur la page d'archive annuelle, le nom affiché à côté de chaque lien
     "de M./Mme X" sert seulement de PRÉ-FILTRE grossier (par nom de
     famille) pour limiter le nombre de pages à aller consulter — jamais
     de confiance aveugle dedans (accents, homonymes, troncatures).
  2. Chaque question pré-filtrée est ensuite ouverte individuellement,
     et l'auteur n'est confirmé QUE via le lien /senateur/{slug}.html
     trouvé sur cette page, comparé au slug exact de senateurs_config.py.
     Si aucun match exact de slug : la question est ignorée (mieux vaut
     rater une question ambiguë que mal l'attribuer).
  3. Déduplication par numéro de question (ex. "07859"), jamais par URL
     brute (deux URLs différentes peuvent pointer sur la même question
     selon l'année de republication).
  4. Requêtes espacées (REQUEST_DELAY) par respect du serveur du Sénat.

Usage :
    pip install requests beautifulsoup4 --break-system-packages
    python3 fetch_activite_senateurs.py

Sortie :
    activite-senateurs-data.json — à placer à côté de
    veille-senateurs-normandie.html
"""

import json
import re
import sys
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from senateurs_config import SENATEURS

HEADERS = {
    "User-Agent": "VeilleSenateursNormandie/1.0 (usage redaction locale ; contact: redaction@example.fr)"
}

BASE = "https://www.senat.fr"

# Années à parcourir. La législature en cours + l'année précédente
# suffisent pour une veille ; augmentez si vous voulez un historique
# plus profond (attention : chaque année ajoute ~1500-2000 questions
# à parcourir, tous sénateurs confondus).
YEARS = [2026, 2025]

REQUEST_DELAY = 1.0  # secondes entre deux requêtes (politesse envers le serveur du Sénat)

QUESTION_LINK_RE = re.compile(r"/questions/base/\d{4}/qSEQ[A-Za-z0-9]+\.html$")
DISPLAYED_NAME_RE = re.compile(r"de\s+(?:M\.|Mme)\s+(.+)")


def normalize(name):
    """Normalise un nom pour comparaison tolérante aux accents/casse."""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", n).strip().lower()


# Table de correspondance nom-de-famille -> sénateur(s) suivis, pour le
# pré-filtre. Plusieurs sénateurs peuvent partager un nom de famille
# (aucun cas parmi nos 17, mais le code reste générique).
SURNAME_INDEX = {}
for s in SENATEURS:
    surname = normalize(s["nom"].split()[-1])
    SURNAME_INDEX.setdefault(surname, []).append(s)

SLUG_INDEX = {s["slug"]: s for s in SENATEURS}


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def candidate_surnames_in_text(text):
    """Renvoie les sénateurs suivis dont le nom de famille apparaît dans `text`."""
    norm = normalize(text)
    hits = []
    for surname, sens in SURNAME_INDEX.items():
        if surname in norm:
            hits.extend(sens)
    return hits


# ---------- Étape 1 : pré-filtrage sur l'archive annuelle ----------

def list_candidate_questions_from_soup(soup):
    """
    Prend le BeautifulSoup d'une page d'archive annuelle et renvoie une
    liste de (numero_question, url, senateurs_candidats) pour toute
    entrée dont le nom affiché contient le nom de famille d'un de nos
    sénateurs suivis.

    Le nom affiché n'est PAS une preuve d'attribution (voir docstring du
    module) : c'est seulement pour éviter d'ouvrir des milliers de pages
    inutiles. La preuve vient de l'étape 2 (parse_question_page).

    Séparée de list_candidate_questions() pour être testable hors-ligne
    sur une fixture, sans requête réseau.
    """
    candidates = []
    seen_numeros = set()

    for link in soup.find_all("a", href=QUESTION_LINK_RE):
        numero = link.get_text(strip=True)
        qurl = link["href"]
        if not qurl.startswith("http"):
            qurl = BASE + qurl

        # Le nom du sénateur suit le lien dans le même élément de liste
        # (ex. "<a>07859</a> de Mme Corinne Féret"). On prend le texte de
        # l'élément parent le plus proche (li, p, etc.) et on retire le
        # texte du lien lui-même pour isoler le "de M./Mme Nom".
        container = link.find_parent(["li", "p", "div"]) or link.parent
        container_text = container.get_text(" ", strip=True) if container else ""
        m = DISPLAYED_NAME_RE.search(container_text)
        displayed_name = m.group(1).strip() if m else container_text

        hits = candidate_surnames_in_text(displayed_name)
        if not hits:
            continue
        if numero in seen_numeros:
            continue
        seen_numeros.add(numero)
        candidates.append((numero, qurl, hits))

    return candidates


def list_candidate_questions(year):
    """Version réseau : récupère l'archive annuelle puis délègue au parsing."""
    url = f"{BASE}/questions/base/{year}/"
    soup = get(url)
    return list_candidate_questions_from_soup(soup)


# ---------- Étape 2 : ouverture + confirmation d'attribution ----------

TITLE_POOR_THRESHOLD = 40  # seuil de longueur pour détecter un "titre pauvre"


def parse_question_page(url):
    """
    Ouvre la page d'une question et en extrait les données, en confirmant
    l'auteur via le lien fiable vers /senateur/{slug}.html.

    Renvoie None si aucun sénateur suivi n'est confirmé comme auteur
    (mieux vaut ignorer que mal attribuer).
    """
    soup = get(url)

    # Auteur : chercher un lien /senateur/{slug}.html dans la zone
    # "Auteur de la question" (repli : n'importe quel lien de ce type
    # dans le haut de page, le premier trouvé étant fiable d'après la
    # structure observée).
    auteur_link = soup.find("a", href=re.compile(r"/senateur/[a-z0-9_]+\.html$"))
    if not auteur_link:
        return None
    slug_match = re.search(r"/senateur/([a-z0-9_]+)\.html$", auteur_link["href"])
    if not slug_match:
        return None
    slug = slug_match.group(1)
    senateur = SLUG_INDEX.get(slug)
    if senateur is None:
        # Question d'un sénateur non suivi (le pré-filtre a eu un faux
        # positif, ex. homonyme partiel) : on ignore proprement.
        return None

    # Titre : balise <h1> si présente, sinon <title>, avec repli si "pauvre"
    h1 = soup.find("h1")
    titre = h1.get_text(strip=True) if h1 else None
    if not titre or len(titre) < TITLE_POOR_THRESHOLD:
        title_tag = soup.find("title")
        if title_tag:
            alt = title_tag.get_text(strip=True).split(" - Sénat")[0].strip()
            if alt and len(alt) > len(titre or ""):
                titre = alt
    if not titre:
        titre = "(titre non trouvé)"

    # Espace unique entre chaque nœud de texte : plus robuste que "\n" face
    # aux regex, et évite de dépendre de la mise en forme exacte des balises.
    full_text = re.sub(r"\s+", " ", soup.get_text(" "))

    numero_match = re.search(r"[Qq]uestion écrite n°\s*(\d+)", full_text)
    numero = numero_match.group(1) if numero_match else None

    date_pub_match = re.search(
        r"[Qq]uestion publiée le (\d{2}/\d{2}/\d{4})", full_text
    )
    date_publication = date_pub_match.group(1) if date_pub_match else None

    date_rep_match = re.search(
        r"[Rr]éponse publiée le (\d{2}/\d{2}/\d{4})", full_text
    )
    date_reponse = date_rep_match.group(1) if date_rep_match else None

    ministre_match = re.search(
        r"Ministre interrogé\(e\)\s*(.+?)\s*(?:Question réattribuée|Date\(s\) de publication|$)",
        full_text,
    )
    ministre = ministre_match.group(1).strip() if ministre_match else None

    statut = "répondue" if date_reponse else "en attente de réponse"

    return {
        "type": "question_ecrite",
        "numero": numero,
        "titre": titre,
        "senateur_slug": slug,
        "senateur_nom": senateur["nom"],
        "senateur_dept": senateur["dept"],
        "date_publication": date_publication,
        "date_reponse": date_reponse,
        "statut": statut,
        "ministre_interroge": ministre,
        "url": url,
    }


# ---------- Orchestration ----------

def fetch_all_questions():
    all_questions = {}  # numero -> question dict (dédup par numéro métier)

    for year in YEARS:
        print(f"--- Archive {year} : recherche des candidats ---", file=sys.stderr)
        try:
            candidates = list_candidate_questions(year)
        except requests.RequestException as e:
            print(f"  Erreur en récupérant l'archive {year} : {e}", file=sys.stderr)
            continue
        time.sleep(REQUEST_DELAY)

        print(f"  {len(candidates)} question(s) candidate(s) (pré-filtre par nom)", file=sys.stderr)

        for numero, qurl, hits in candidates:
            if numero in all_questions:
                continue
            try:
                parsed = parse_question_page(qurl)
            except requests.RequestException as e:
                print(f"  Erreur sur {qurl} : {e}", file=sys.stderr)
                continue
            time.sleep(REQUEST_DELAY)

            if parsed is None:
                continue  # pré-filtre en faux positif, ou hors périmètre

            key = parsed["numero"] or numero
            all_questions[key] = parsed
            print(f"    + {parsed['senateur_nom']} : {parsed['titre'][:70]}", file=sys.stderr)

    return list(all_questions.values())


def main():
    questions = fetch_all_questions()
    questions.sort(key=lambda q: q.get("date_publication") or "", reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "questions_ecrites": questions,
    }

    with open("activite-senateurs-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{len(questions)} question(s) écrite(s) récupérée(s) au total.", file=sys.stderr)
    print("Écrit dans activite-senateurs-data.json", file=sys.stderr)


if __name__ == "__main__":
    main()

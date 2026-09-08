#!/usr/bin/env python3
"""
Récupère les questions écrites des sénateurs normands suivis (voir
senateurs_config.py), depuis l'Open Data officiel du Sénat plutôt que par
scraping HTML.

Source (vérifiée le 08/09/2026) :
  https://data.senat.fr/data/questions/questions-depuis-un-an.csv
  Fichier CSV maintenu par le Sénat lui-même (data.senat.fr), régénéré en
  continu, couvrant les 12 derniers mois glissants de questions écrites et
  orales, tous sénateurs confondus. Colonnes utiles : Nom, Prénom,
  Circonscription (département), Groupe, Date de publication JO,
  Ministère de dépôt, Ministère de réponse, Date de réponse JO, Thème(s),
  URL Question.

  Historique de la démarche : la première version de ce script scrapait
  les pages HTML d'archive de senat.fr (~20 pages d'index + jusqu'à 700+
  pages individuelles de questions à ouvrir une par une pour vérifier
  l'auteur). En creusant l'existence d'une éventuelle API/Open Data, ce
  fichier CSV s'est révélé couvrir exactement les mêmes données de façon
  structurée et fiable — le nouveau script est donc radicalement plus
  simple : un seul fichier à télécharger, plus de pré-filtre/vérification
  en deux temps, plus besoin de cache ni de parallélisation.

Piège rencontré et à anticiper :
  - Le fichier n'est PAS en UTF-8 (probablement ISO-8859-1 / Windows-1252,
    comme souvent sur les exports gouvernementaux anciens). Le script
    essaie plusieurs encodages avant d'abandonner.
  - Les dates du CSV sont au format ISO (AAAA-MM-JJ) : converties en
    JJ/MM/AAAA pour rester cohérentes avec le reste des données du projet.
  - L'attribution à un sénateur suivi se fait par nom de famille (colonne
    "Nom"), avec double vérification par département ("Circonscription")
    pour écarter d'éventuels homonymes : un nom de famille qui matche mais
    dont le département ne correspond à aucun de nos 5 départements
    normands est ignoré plutôt que mal attribué (même principe défensif
    que pour le scraping HTML).

Usage :
    pip install requests --break-system-packages
    python3 fetch_activite_senateurs.py

Sortie :
    activite-senateurs-data.json
"""

import csv
import io
import json
import re
import sys
import unicodedata
from datetime import datetime

import requests

from senateurs_config import SENATEURS

CSV_URL = "https://data.senat.fr/data/questions/questions-depuis-un-an.csv"
OUTPUT_FILE = "activite-senateurs-data.json"

HEADERS = {
    "User-Agent": "VeilleSenateursNormandie/1.0 (usage redaction locale ; contact: redaction@example.fr)"
}

# Encodages à essayer dans l'ordre — cf. piège documenté plus haut.
CANDIDATE_ENCODINGS = ["utf-8", "cp1252", "iso-8859-1"]


def normalize(text):
    """Normalise pour comparaison tolérante aux accents/casse/espaces."""
    n = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", n).strip().lower()


# Index nom de famille normalisé -> liste de sénateurs suivis (gère le cas
# générique où deux sénateurs suivis partageraient un nom de famille,
# même si ça n'arrive pas dans notre liste actuelle de 17).
SURNAME_INDEX = {}
for _s in SENATEURS:
    SURNAME_INDEX.setdefault(normalize(_s["nom_famille"]), []).append(_s)

DEPARTEMENTS_SUIVIS = {normalize(_s["dept"]) for _s in SENATEURS}


def fetch_csv_bytes():
    resp = requests.get(CSV_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content


def decode_csv_bytes(raw_bytes):
    """Essaie plusieurs encodages ; renvoie le texte décodé et l'encodage
    utilisé (pour information/debug)."""
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    # Dernier recours : on force en remplaçant les caractères invalides
    # plutôt que de planter, pour ne pas perdre tout le fichier à cause
    # de quelques caractères mal encodés.
    return raw_bytes.decode("iso-8859-1", errors="replace"), "iso-8859-1 (avec erreurs remplacées)"


def parse_csv_text(text):
    """Renvoie la liste des lignes du CSV sous forme de dicts."""
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def iso_to_ddmmyyyy(date_str):
    """Convertit "2025-06-12" en "12/06/2025". Renvoie None si vide/invalide."""
    if not date_str or not date_str.strip():
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str.strip())
    if not m:
        return None
    year, month, day = m.groups()
    return f"{day}/{month}/{year}"


def match_senateur(row):
    """
    Tente d'attribuer une ligne du CSV à l'un de nos 17 sénateurs suivis.
    Double vérification nom de famille + département, comme pour le
    scraping HTML : mieux vaut ignorer une ligne ambiguë que mal
    l'attribuer.
    """
    nom_csv = normalize(row.get("Nom", ""))
    candidates = SURNAME_INDEX.get(nom_csv)
    if not candidates:
        return None

    dept_csv = normalize(row.get("Circonscription", ""))
    for senateur in candidates:
        if normalize(senateur["dept"]) == dept_csv:
            return senateur

    # Nom de famille suivi trouvé mais département qui ne correspond à
    # aucun de nos sénateurs suivis pour ce nom : probable homonyme
    # (sénateur d'un autre département portant le même nom de famille).
    return None


def build_record(row, senateur):
    date_publication = iso_to_ddmmyyyy(row.get("Date de publication JO"))
    date_reponse = iso_to_ddmmyyyy(row.get("Date de réponse JO"))

    url = (row.get("URL Question") or "").strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    return {
        "type": "question_ecrite",
        "numero": (row.get("Numéro") or "").strip() or None,
        "titre": (row.get("Titre") or "").strip(),
        "senateur_slug": senateur["slug"],
        "senateur_nom": senateur["nom"],
        "senateur_dept": senateur["dept"],
        "date_publication": date_publication,
        "date_reponse": date_reponse,
        "statut": "répondue" if date_reponse else "en attente de réponse",
        "ministre_interroge": (row.get("Ministère de dépôt") or "").strip() or None,
        "ministre_reponse": (row.get("Ministère de réponse") or "").strip() or None,
        "themes": (row.get("Thème(s)") or "").strip() or None,
        "groupe_politique": (row.get("Groupe") or "").strip() or None,
        "url": url,
    }


def fetch_all_questions():
    print(f"Téléchargement de {CSV_URL} ...", file=sys.stderr)
    raw_bytes = fetch_csv_bytes()
    text, encoding_used = decode_csv_bytes(raw_bytes)
    print(f"  {len(raw_bytes)} octets reçus, décodés en {encoding_used}.", file=sys.stderr)

    rows = parse_csv_text(text)
    print(f"  {len(rows)} ligne(s) au total dans le fichier (tous sénateurs confondus).", file=sys.stderr)

    results = {}  # numero -> record, dédup par numéro métier
    unmatched_surname_dept_mismatch = 0

    for row in rows:
        senateur = match_senateur(row)
        if senateur is None:
            nom_csv = normalize(row.get("Nom", ""))
            if nom_csv in SURNAME_INDEX:
                unmatched_surname_dept_mismatch += 1
            continue
        record = build_record(row, senateur)
        key = record["numero"] or record["url"]
        results[key] = record

    print(
        f"  {len(results)} question(s) attribuée(s) à nos 17 sénateurs suivis.",
        file=sys.stderr,
    )
    if unmatched_surname_dept_mismatch:
        print(
            f"  ({unmatched_surname_dept_mismatch} ligne(s) avec un nom de famille "
            "correspondant mais un département différent : probables homonymes, ignorées.)",
            file=sys.stderr,
        )

    return list(results.values())


def main():
    questions = fetch_all_questions()
    questions.sort(key=lambda q: q.get("date_publication") or "", reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": CSV_URL,
        "questions_ecrites": questions,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{len(questions)} question(s) écrite(s) récupérée(s) au total.", file=sys.stderr)
    print(f"Écrit dans {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Récupère les positions de vote des sénateurs normands suivis sur les
scrutins solennels ("sur l'ensemble" d'un texte), avec comparaison à la
position majoritaire de leur groupe politique.

Source : NosParlementaires.fr (https://nosparlementaires.fr/donnees-ouvertes)
  Site citoyen indépendant (pas le Sénat lui-même), qui republie sous
  Licence Ouverte 2.0 (Etalab) des données dérivées de l'Open Data
  officiel du Sénat, régénérées quotidiennement. Trois fichiers utilisés :
    - senateurs.csv    : identité de chaque sénateur (nom, groupe...)
    - scrutins_senat.csv : liste de tous les scrutins publics (titre, date, résultat)
    - votes_senat.csv.gz : position de chaque sénateur à chaque scrutin

Pourquoi cette source plutôt que senat.fr directement : au Sénat, les
votes sont publiés SCRUTIN PAR SCRUTIN (pas de page "votes d'un sénateur"),
et la plupart des votes se font à main levée sans liste nominative. Une
extraction fiable depuis senat.fr demanderait de parcourir ~900 pages de
scrutins un par un. NosParlementaires.fr a déjà fait ce travail de
consolidation ; on ne republie pas leurs données mais on les filtre
localement sur nos 17 sénateurs suivis.

Filtre "votes solennels" (choix fait dans la conversation de conception) :
  On ne garde que les scrutins dont le titre correspond à un vote final
  "sur l'ensemble" d'un texte (projet ou proposition de loi, texte de
  commission mixte paritaire...), pas les votes d'amendements ou de
  motions de procédure — plus lisible, quitte à couvrir moins de scrutins.

IMPORTANT — Cette source n'a pas pu être vérifiée en détail avant le
premier run réel : le fichier votes_senat.csv.gz est trop volumineux et
compressé pour être inspecté par les outils de consultation web utilisés
pendant la conception. Le script affiche donc les noms de colonnes qu'il
trouve réellement au démarrage (`--inspect`), et le matching par nom est
fait défensivement (recherche du nom de colonne le plus probable plutôt
que codé en dur), pour qu'on valide ensemble sur le premier run et
qu'on ajuste si les noms réels diffèrent de ce qui est supposé ici.

Usage :
    pip install requests --break-system-packages
    python3 fetch_positions_vote.py --inspect   # affiche les colonnes réelles, ne rien écrire
    python3 fetch_positions_vote.py              # lance le vrai traitement

Sortie :
    positions-vote-senateurs-data.json
"""

import argparse
import csv
import gzip
import io
import json
import re
import sys
import unicodedata
from datetime import datetime

import requests

from senateurs_config import SENATEURS

BASE = "https://nosparlementaires.fr/opendata"
OUTPUT_FILE = "positions-vote-senateurs-data.json"

HEADERS = {
    "User-Agent": "VeilleSenateursNormandie/1.0 (usage redaction locale ; contact: redaction@example.fr)"
}

# Motifs identifiant un vote "sur l'ensemble" d'un texte (vote solennel
# final), par opposition aux votes d'amendements/motions/articles isolés.
# Ancré en DÉBUT de titre (^) : un vote sur un amendement peut mentionner
# accessoirement "constituant l'ensemble" en décrivant l'article visé
# (ex. "sur l'amendement n°9 ... à l'article unique constituant l'ensemble
# de la proposition de loi..."), ce qui donnerait un faux positif sans cet
# ancrage — le sujet réel du vote est toujours en tête du titre.
# L'apostrophe est traitée comme optionnelle (les titres sources mêlent
# apostrophe simple, typographique, ou absente : "l'ensemble"/"lensemble").
VOTE_SOLENNEL_RE = re.compile(
    r"^sur\s+l.?article\s+\S+\s+constituant\s+l.?ensemble\b|"
    r"^sur\s+l.?ensemble\b|"
    r"^sur\s+le\s+texte\s+élabor[ée]\s+par\s+la\s+commission\s+mixte\s+paritaire\b",
    re.I,
)


def normalize(text):
    n = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", n).strip().lower()


def fetch_text(path):
    resp = requests.get(f"{BASE}/{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_gz_text(path):
    resp = requests.get(f"{BASE}/{path}", headers=HEADERS, timeout=60)
    resp.raise_for_status()
    with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as f:
        return f.read().decode("utf-8")


def read_csv(text):
    return list(csv.DictReader(io.StringIO(text)))


def find_column(fieldnames, *keywords_options):
    """
    Trouve le nom de colonne réel le plus probable parmi fieldnames, en
    cherchant celle qui contient tous les mots-clés d'un des jeux de
    mots-clés fournis (dans l'ordre de préférence). Renvoie None si
    aucune ne correspond — mieux vaut échouer explicitement que deviner
    silencieusement une mauvaise colonne.
    """
    normalized_fields = {f: normalize(f) for f in fieldnames}
    for keywords in keywords_options:
        for field, norm in normalized_fields.items():
            if all(kw in norm for kw in keywords):
                return field
    return None


def inspect():
    print("=== Colonnes réelles des fichiers NosParlementaires.fr ===\n", file=sys.stderr)

    senateurs_text = fetch_text("senateurs.csv")
    senateurs_rows = read_csv(senateurs_text)
    print(f"senateurs.csv : {len(senateurs_rows)} lignes", file=sys.stderr)
    print(f"  colonnes : {senateurs_rows[0].keys() if senateurs_rows else '(vide)'}", file=sys.stderr)
    if senateurs_rows:
        print(f"  exemple  : {senateurs_rows[0]}\n", file=sys.stderr)

    scrutins_text = fetch_text("scrutins_senat.csv")
    scrutins_rows = read_csv(scrutins_text)
    print(f"scrutins_senat.csv : {len(scrutins_rows)} lignes", file=sys.stderr)
    print(f"  colonnes : {scrutins_rows[0].keys() if scrutins_rows else '(vide)'}", file=sys.stderr)
    if scrutins_rows:
        print(f"  exemple  : {scrutins_rows[0]}\n", file=sys.stderr)

    print("Téléchargement de votes_senat.csv.gz (peut prendre quelques secondes)...", file=sys.stderr)
    votes_text = fetch_gz_text("votes_senat.csv.gz")
    votes_rows_iter = csv.DictReader(io.StringIO(votes_text))
    first_rows = []
    for i, row in enumerate(votes_rows_iter):
        first_rows.append(row)
        if i >= 2:
            break
    print(f"votes_senat.csv.gz : colonnes : {first_rows[0].keys() if first_rows else '(vide)'}", file=sys.stderr)
    for row in first_rows:
        print(f"  exemple : {row}", file=sys.stderr)


def build_senateur_id_index(senateurs_rows):
    """
    Associe chaque sénateur suivi (senateurs_config.py) à sa ligne dans
    senateurs.csv de NosParlementaires.fr, par nom+prénom normalisés
    (double vérification par département quand la colonne existe, même
    principe défensif que pour le CSV Open Data du Sénat).
    """
    if not senateurs_rows:
        return {}

    fieldnames = list(senateurs_rows[0].keys())
    col_nom = find_column(fieldnames, ["nom"], ["name"])
    col_prenom = find_column(fieldnames, ["prenom"], ["prénom".translate(str.maketrans("é", "e"))], ["first", "name"])
    col_dept = find_column(fieldnames, ["dept"], ["departement"], ["circonscription"])
    col_id = find_column(fieldnames, ["slug"], ["id"])

    if not (col_nom and col_id):
        print(
            "ATTENTION : colonnes nom/identifiant introuvables dans senateurs.csv — "
            f"colonnes disponibles : {fieldnames}. Lancez --inspect pour diagnostiquer.",
            file=sys.stderr,
        )
        return {}

    print(
        f"Colonnes retenues pour senateurs.csv : nom={col_nom!r}, prenom={col_prenom!r}, "
        f"dept={col_dept!r}, id={col_id!r}",
        file=sys.stderr,
    )

    index = {}  # senateur_config["slug"] -> id NosParlementaires
    for s in SENATEURS:
        target_nom = normalize(s["nom_famille"])
        target_prenom = normalize(s["prenom"])
        candidates = []
        for row in senateurs_rows:
            row_nom = normalize(row.get(col_nom, ""))
            row_prenom = normalize(row.get(col_prenom, "")) if col_prenom else ""
            if target_nom in row_nom or row_nom in target_nom:
                if not col_prenom or target_prenom in row_prenom or row_prenom in target_prenom:
                    candidates.append(row)

        if len(candidates) == 1:
            index[s["slug"]] = candidates[0][col_id]
        elif len(candidates) > 1 and col_dept:
            # Désambiguïsation par département si plusieurs candidats
            dept_matches = [
                c for c in candidates
                if normalize(s["dept"]) in normalize(c.get(col_dept, ""))
            ]
            if len(dept_matches) == 1:
                index[s["slug"]] = dept_matches[0][col_id]
            else:
                print(f"  Ambigu pour {s['nom']} : {len(candidates)} candidat(s), ignoré.", file=sys.stderr)
        elif not candidates:
            print(f"  Introuvable dans senateurs.csv : {s['nom']}", file=sys.stderr)
        else:
            print(f"  Ambigu pour {s['nom']} : {len(candidates)} candidat(s), ignoré.", file=sys.stderr)

    return index


def filter_votes_solennels(scrutins_rows):
    """Renvoie {scrutin_id: scrutin_row} pour les seuls votes solennels."""
    result = {}
    for row in scrutins_rows:
        title = row.get("title", "")
        if VOTE_SOLENNEL_RE.search(title):
            result[row["id"]] = row
    return result


def build_id_to_groupe(senateurs_rows, col_id, col_groupe):
    if not col_groupe:
        return {}
    return {row[col_id]: row.get(col_groupe) for row in senateurs_rows if row.get(col_id)}


def majority_position(counter):
    """Position la plus fréquente d'un Counter {position: nombre}. None si vide."""
    if not counter:
        return None
    return max(counter.items(), key=lambda kv: kv[1])[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inspect", action="store_true",
        help="Affiche les colonnes réelles des fichiers sources sans rien écrire (diagnostic)",
    )
    args = parser.parse_args()

    if args.inspect:
        inspect()
        return

    print("Téléchargement de senateurs.csv ...", file=sys.stderr)
    senateurs_rows = read_csv(fetch_text("senateurs.csv"))

    print("Téléchargement de scrutins_senat.csv ...", file=sys.stderr)
    scrutins_rows = read_csv(fetch_text("scrutins_senat.csv"))
    votes_solennels = filter_votes_solennels(scrutins_rows)
    print(
        f"  {len(scrutins_rows)} scrutin(s) au total, {len(votes_solennels)} vote(s) solennel(s) retenu(s).",
        file=sys.stderr,
    )

    id_index = build_senateur_id_index(senateurs_rows)
    if not id_index:
        print("Aucun sénateur suivi retrouvé dans senateurs.csv — abandon.", file=sys.stderr)
        sys.exit(1)
    reverse_id_index = {v: k for k, v in id_index.items()}  # id NosParlementaires -> slug senat.fr
    slug_to_senateur = {s["slug"]: s for s in SENATEURS}

    senateurs_fieldnames = list(senateurs_rows[0].keys()) if senateurs_rows else []
    col_id_all = find_column(senateurs_fieldnames, ["slug"], ["id"])
    col_groupe = find_column(senateurs_fieldnames, ["groupe"])
    id_to_groupe = build_id_to_groupe(senateurs_rows, col_id_all, col_groupe) if col_id_all else {}
    if not col_groupe:
        print(
            "ATTENTION : colonne groupe introuvable dans senateurs.csv — la comparaison "
            "au vote du groupe sera omise.",
            file=sys.stderr,
        )

    print("Téléchargement et décompression de votes_senat.csv.gz (peut être long) ...", file=sys.stderr)
    votes_text = fetch_gz_text("votes_senat.csv.gz")
    votes_reader = csv.DictReader(io.StringIO(votes_text))

    fieldnames = votes_reader.fieldnames or []
    col_scrutin_id = find_column(fieldnames, ["scrutin", "id"])
    col_senateur_id = find_column(fieldnames, ["senateur", "id"], ["deput", "id"], ["parlementaire", "id"])
    col_position = find_column(fieldnames, ["position"], ["vote"])

    if not (col_scrutin_id and col_senateur_id and col_position):
        print(
            "ATTENTION : colonnes attendues introuvables dans votes_senat.csv.gz — "
            f"colonnes disponibles : {fieldnames}. Lancez --inspect pour diagnostiquer, "
            "puis signalez ceci pour ajuster le script.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Colonnes retenues pour votes_senat.csv.gz : scrutin_id={col_scrutin_id!r}, "
        f"senateur_id={col_senateur_id!r}, position={col_position!r}",
        file=sys.stderr,
    )

    from collections import Counter, defaultdict

    # Comptage des positions par (scrutin_id, groupe), sur TOUS les
    # sénateurs (pas seulement les 17 suivis) : nécessaire pour connaître
    # la position majoritaire d'un groupe, indépendamment de qui on suit.
    group_tally = defaultdict(Counter)  # (scrutin_id, groupe) -> Counter(position)
    our_rows = []  # lignes concernant nos 17 sénateurs, à finaliser après coup

    for row in votes_reader:
        scrutin_id = row.get(col_scrutin_id)
        if scrutin_id not in votes_solennels:
            continue
        senateur_id = row.get(col_senateur_id)
        position = row.get(col_position)
        groupe = id_to_groupe.get(senateur_id)

        if groupe:
            group_tally[(scrutin_id, groupe)][position] += 1

        if senateur_id in reverse_id_index:
            our_rows.append((scrutin_id, senateur_id, position))

    results = []
    for scrutin_id, senateur_id, position in our_rows:
        slug = reverse_id_index[senateur_id]
        senateur = slug_to_senateur[slug]
        scrutin = votes_solennels[scrutin_id]
        groupe = id_to_groupe.get(senateur_id)

        position_groupe = None
        vote_comme_groupe = None
        if groupe:
            tally = dict(group_tally.get((scrutin_id, groupe), {}))
            position_groupe = majority_position(tally)
            if position_groupe is not None and position is not None:
                vote_comme_groupe = (position == position_groupe)

        results.append({
            "type": "position_vote",
            "scrutin_id": scrutin_id,
            "scrutin_titre": scrutin.get("title"),
            "scrutin_date": (scrutin.get("date") or "")[:10] or None,
            "scrutin_url": scrutin.get("url"),
            "senateur_slug": slug,
            "senateur_nom": senateur["nom"],
            "senateur_dept": senateur["dept"],
            "position": position,
            "groupe_politique": groupe,
            "position_majoritaire_groupe": position_groupe,
            "vote_comme_son_groupe": vote_comme_groupe,
        })

    results.sort(key=lambda r: r.get("scrutin_date") or "", reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": "https://nosparlementaires.fr/donnees-ouvertes (données dérivées de l'Open Data du Sénat)",
        "positions_vote": results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{len(results)} position(s) de vote récupérée(s) au total.", file=sys.stderr)
    print(f"Écrit dans {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()

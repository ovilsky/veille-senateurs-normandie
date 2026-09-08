#!/usr/bin/env python3
"""
Teste fetch_activite_senateurs.py (version Open Data CSV) contre une
fixture locale, sans aucun appel réseau.
"""

import fetch_activite_senateurs as fas

FIXTURES = "fixtures"


def load_fixture_text(path):
    with open(f"{FIXTURES}/{path}", encoding="utf-8") as f:
        return f.read()


def test_iso_to_ddmmyyyy():
    assert fas.iso_to_ddmmyyyy("2025-06-12") == "12/06/2025"
    assert fas.iso_to_ddmmyyyy("") is None
    assert fas.iso_to_ddmmyyyy(None) is None
    print("OK : iso_to_ddmmyyyy convertit correctement les dates ISO.\n")


def test_decode_csv_bytes():
    text, enc = fas.decode_csv_bytes("Prénom;Nom\nHervé;Maurey\n".encode("utf-8"))
    assert "Hervé" in text
    assert enc == "utf-8"

    text, enc = fas.decode_csv_bytes("Prénom;Nom\nHervé;Maurey\n".encode("cp1252"))
    assert "Hervé" in text
    print(f"OK : decode_csv_bytes gère UTF-8 et CP1252/Latin-1 (détecté : {enc}).\n")


def test_parse_and_match_and_build():
    text = load_fixture_text("questions_opendata_sample.csv")
    rows = fas.parse_csv_text(text)
    print(f"{len(rows)} ligne(s) dans la fixture CSV.")
    assert len(rows) == 5

    matched = []
    for row in rows:
        senateur = fas.match_senateur(row)
        if senateur:
            matched.append((row, senateur))

    print(f"{len(matched)} ligne(s) attribuée(s) à un sénateur suivi :")
    for row, senateur in matched:
        print(f"  {senateur['nom']} ({senateur['dept']}) : {row['Titre'][:60]}")

    assert len(matched) == 2, f"attendu 2 questions attribuées, trouvé {len(matched)}"

    noms_matches = {senateur["nom"] for _, senateur in matched}
    assert noms_matches == {"Hervé Maurey", "Corinne Féret"}, noms_matches

    print("OK : match_senateur attribue correctement et rejette l'homonyme "
          "Maurey/Var ainsi que les sénateurs hors périmètre.\n")

    row_maurey = next(r for r in rows if r["Numéro"] == "08995")
    senateur_maurey = fas.match_senateur(row_maurey)
    record = fas.build_record(row_maurey, senateur_maurey)

    assert record["numero"] == "08995"
    assert record["titre"] == "Effets des additifs alimentaires sur la santé des consommateurs"
    assert record["senateur_dept"] == "Eure"
    assert record["date_publication"] == "04/06/2026"
    assert record["date_reponse"] is None
    assert record["statut"] == "en attente de réponse"
    assert record["url"].startswith("https://")
    assert record["themes"] == "Questions sociales et santé"

    row_feret = next(r for r in rows if r["Numéro"] == "07859")
    senateur_feret = fas.match_senateur(row_feret)
    record_feret = fas.build_record(row_feret, senateur_feret)
    assert record_feret["statut"] == "répondue"
    assert record_feret["date_reponse"] == "04/06/2026"
    assert record_feret["ministre_interroge"] == "Transition écologique"

    print("OK : build_record construit correctement les enregistrements "
          "(dates, statut, URL en https, thèmes).\n")


if __name__ == "__main__":
    test_iso_to_ddmmyyyy()
    test_decode_csv_bytes()
    test_parse_and_match_and_build()
    print("=== Tous les tests hors-ligne passent ===")

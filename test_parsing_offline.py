#!/usr/bin/env python3
"""
Teste les fonctions de parsing de fetch_activite_senateurs.py contre des
fixtures HTML locales (reproduisant fidèlement la structure réelle
observée sur senat.fr), sans aucun appel réseau.

Usage : python3 test_parsing_offline.py
"""

from bs4 import BeautifulSoup

import fetch_activite_senateurs as fas

FIXTURES = "fixtures"


def load(path):
    with open(f"{FIXTURES}/{path}", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def test_list_candidate_questions():
    soup = load("archive_2026.html")
    candidates = fas.list_candidate_questions_from_soup(soup)

    numeros = {c[0] for c in candidates}
    print(f"Candidats trouvés : {sorted(numeros)}")

    # On attend : Olivier Bitz x2 (07196, 07197), David Margueritte (0955S),
    # Kristina Pluchet (07736), Pascal Allizard (07786), Corinne Féret (07859),
    # Sébastien Fagnen (07864), Catherine Morin-Desailly (07844), Céline Brulin (07818)
    # PAS Nicole Bonnefoy (07181, homonyme sans rapport) ni Monique Lubin (07857, hors périmètre)
    expected_present = {
        "07196", "07197", "0955S", "07736", "07786",
        "07859", "07864", "07844", "07818",
    }
    expected_absent = {"07181", "07857"}

    missing = expected_present - numeros
    unexpected = expected_absent & numeros

    assert not missing, f"ÉCHEC : candidats attendus manquants : {missing}"
    assert not unexpected, f"ÉCHEC : candidats qui n'auraient pas dû apparaître : {unexpected}"
    print("OK : list_candidate_questions_from_soup filtre correctement.\n")


def test_parse_question_page_matched():
    # On monkey-patche get() pour lire la fixture au lieu du réseau
    original_get = fas.get
    fas.get = lambda url: load("question_07859.html")
    try:
        result = fas.parse_question_page("https://www.senat.fr/questions/base/2026/qSEQ260207859.html")
    finally:
        fas.get = original_get

    print("Résultat parse_question_page (Corinne Féret) :")
    for k, v in result.items():
        print(f"  {k}: {v}")

    assert result is not None
    assert result["senateur_slug"] == "feret_corinne14281w"
    assert result["senateur_nom"] == "Corinne Féret"
    assert result["numero"] == "07859"
    assert result["date_publication"] == "26/02/2026"
    assert result["date_reponse"] == "04/06/2026"
    assert result["statut"] == "répondue"
    assert "conchylicole" in result["titre"].lower()
    assert len(result["titre"]) >= fas.TITLE_POOR_THRESHOLD, "titre jugé trop pauvre alors qu'il ne l'est pas"
    print("OK : parse_question_page extrait correctement une question attribuée.\n")


def test_parse_question_page_out_of_scope():
    original_get = fas.get
    fas.get = lambda url: load("question_07857_hors_perimetre.html")
    try:
        result = fas.parse_question_page("https://www.senat.fr/questions/base/2026/qSEQ260207857.html")
    finally:
        fas.get = original_get

    print(f"Résultat parse_question_page (hors périmètre) : {result}")
    assert result is None, "ÉCHEC : une question hors périmètre a été attribuée à tort"
    print("OK : parse_question_page ignore bien un sénateur non suivi.\n")


if __name__ == "__main__":
    test_list_candidate_questions()
    test_parse_question_page_matched()
    test_parse_question_page_out_of_scope()
    print("=== Tous les tests hors-ligne passent ===")

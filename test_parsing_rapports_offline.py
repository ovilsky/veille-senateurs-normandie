#!/usr/bin/env python3
"""
Teste le parsing de fetch_rapports_propositions.py contre des fixtures
locales, sans aucun appel réseau.
"""

from bs4 import BeautifulSoup

import fetch_rapports_propositions as frp

FIXTURES = "fixtures"

MAUREY = {
    "slug": "maurey_herve08009t",
    "nom": "Hervé Maurey",
    "dept": "Eure",
}


def load(path):
    with open(f"{FIXTURES}/{path}", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def test_parse_french_date():
    assert frp.parse_french_date("1er juillet 2026") == "01/07/2026"
    assert frp.parse_french_date("6 mai 2026") == "06/05/2026"
    assert frp.parse_french_date("17 février 2026") == "17/02/2026"
    print("OK : parse_french_date convertit correctement les dates en toutes lettres.\n")


def test_parse_propositions_page():
    soup = load("propositions_maurey.html")
    results = frp.parse_propositions_page(soup, MAUREY, seen_urls=set())

    print(f"{len(results)} proposition(s) trouvée(s) :")
    for r in results:
        print(f"  [{r['role']}] {r['date_depot']} - {r['titre'][:60]}")

    assert len(results) == 5, f"attendu 5 propositions, trouvé {len(results)}"

    auteurs = [r for r in results if r["role"] == "auteur"]
    cosignataires = [r for r in results if r["role"] == "cosignataire"]
    assert len(auteurs) == 3, f"attendu 3 en tant qu'auteur, trouvé {len(auteurs)}"
    assert len(cosignataires) == 2, f"attendu 2 en tant que cosignataire, trouvé {len(cosignataires)}"

    ppl823 = next(r for r in results if "ppl25-823" in r["url"])
    assert ppl823["role"] == "auteur"
    assert ppl823["date_depot"] == "01/07/2026"
    assert "compensation financière" in ppl823["titre"]

    ppr595 = next(r for r in results if "ppr25-595" in r["url"])
    assert ppr595["role"] == "cosignataire"
    assert ppr595["date_depot"] == "05/05/2026"

    print("OK : parse_propositions_page distingue bien auteur / cosignataire et extrait les dates.\n")


def test_parse_rapports_page():
    soup = load("rapports_maurey.html")
    results = frp.parse_rapports_page(soup, MAUREY, seen_urls=set())

    print(f"{len(results)} rapport(s) trouvé(s) :")
    for r in results:
        print(f"  [{r['categorie']}] {r['date_publication']} - {r['type_numero']} - {r['titre'][:50]}")

    assert len(results) == 4, f"attendu 4 rapports, trouvé {len(results)}"

    info = [r for r in results if r["categorie"] == "information"]
    legis = [r for r in results if r["categorie"] == "legislatif"]
    assert len(info) == 2, f"attendu 2 rapports d'information, trouvé {len(info)}"
    assert len(legis) == 2, f"attendu 2 rapports législatifs, trouvé {len(legis)}"

    r813 = next(r for r in results if "r25-813" in r["url"])
    assert r813["categorie"] == "information"
    assert r813["date_publication"] == "30/06/2026"
    assert r813["commission"] and "finances" in r813["commission"]
    assert "Zéro artificialisation nette" in r813["titre"]
    assert r813["type_numero"] == "Rapport d'information numéro 813"

    a335 = next(r for r in results if "a25-335" in r["url"])
    assert a335["categorie"] == "legislatif"
    assert a335["type_numero"] == "Avis numéro 335"
    # Le lien de synthèse (-syn.pdf) ne doit jamais créer d'entrée à part
    syn_urls = [r["url"] for r in results if r["url"].endswith("-syn.pdf")]
    assert not syn_urls, f"des liens de synthèse ont été traités comme des rapports : {syn_urls}"

    print("OK : parse_rapports_page extrait correctement commission/titre/type/date, "
          "et ignore les liens de synthèse.\n")


if __name__ == "__main__":
    test_parse_french_date()
    test_parse_propositions_page()
    test_parse_rapports_page()
    print("=== Tous les tests hors-ligne passent ===")

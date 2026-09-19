#!/usr/bin/env python3
"""
Teste les parties de fetch_positions_vote.py qui ne dépendent pas du
schéma réel (encore non confirmé) de votes_senat.csv.gg : le filtre
"votes solennels" et le matching par nom des sénateurs suivis.
"""

import fetch_positions_vote as fpv

FIXTURES = "fixtures"


def load_csv(path):
    with open(f"{FIXTURES}/{path}", encoding="utf-8") as f:
        return fpv.read_csv(f.read())


def test_vote_solennel_filter():
    rows = load_csv("scrutins_senat_sample.csv")
    votes_solennels = fpv.filter_votes_solennels(rows)

    print(f"{len(votes_solennels)} vote(s) solennel(s) sur {len(rows)} scrutin(s) dans la fixture :")
    for sid, row in votes_solennels.items():
        print(f"  {sid} : {row['title'][:70]}")

    # Attendu solennel : 2023-100 (article unique constituant l'ensemble),
    # 2023-101 (sur l'ensemble), 2023-104 (texte CMP)
    # PAS solennel : 2023-1 (amendement, mentionne "constituant l'ensemble"
    # mais À PROPOS d'un amendement — piège à éviter), 2023-108 (motion),
    # 2023-124 (article isolé, pas "constituant l'ensemble")
    assert set(votes_solennels.keys()) == {"2023-100", "2023-101", "2023-104"}, votes_solennels.keys()
    print("OK : filter_votes_solennels exclut bien l'amendement-piège 2023-1 "
          "et ne garde que les vrais votes finaux.\n")


def test_build_senateur_id_index():
    senateurs_rows = load_csv("senateurs_nosparlementaires_sample.csv")
    index = fpv.build_senateur_id_index(senateurs_rows)

    print(f"Index construit : {index}")

    maurey = next(s for s in fpv.SENATEURS if s["nom"] == "Hervé Maurey")
    feret = next(s for s in fpv.SENATEURS if s["nom"] == "Corinne Féret")

    # Le piège : la fixture contient DEUX lignes "Hervé Maurey" (un
    # homonyme inactif, comme observé en vrai sur senateurs.csv qui
    # contient 1948 lignes historiques). On doit retomber sur le sénateur
    # ACTIF, jamais sur l'ancien homonyme.
    assert index.get(maurey["slug"]) == "herve-maurey", index
    assert index.get(feret["slug"]) == "corinne-feret", index
    print("OK : build_senateur_id_index retrouve correctement Maurey et Féret, "
          "et préfère le sénateur actif face à l'homonyme inactif.\n")


def test_build_scrutins_groupes():
    """
    Vérifie le regroupement par scrutin (nouvelle structure attendue par
    le dashboard : une carte par scrutin, pas une ligne par paire
    sénateur/scrutin) sur des données synthétiques à 2 scrutins x 2
    sénateurs, avec un sénateur qui suit son groupe et un autre non.
    """
    votes_solennels = {
        "S1": {
            "title": "Sur l'ensemble du projet de loi Test",
            "date": "2024-03-01",
            "url": "https://senat.fr/S1",
            "dossier_ref": "PJL-1",
            "votants": "340", "suffrages_exprimes": "330", "pour": "200", "contre": "130",
        },
        "S2": {
            "title": "Sur l'ensemble de la proposition de loi Test 2",
            "date": "2024-01-15",
            "url": "https://senat.fr/S2",
            "dossier_ref": "PPL-2",
            "votants": "300", "suffrages_exprimes": "300", "pour": "100", "contre": "200",
        },
    }
    reverse_id_index = {"id-feret": "feret_corinne14281w", "id-maurey": "maurey_herve08009t"}
    slug_to_senateur = {s["slug"]: s for s in fpv.SENATEURS}
    id_to_groupe = {"id-feret": "Socialiste", "id-maurey": "Union Centriste"}
    from collections import Counter
    group_tally = {
        ("S1", "Socialiste"): Counter({"pour": 5, "contre": 1}),
        ("S1", "Union Centriste"): Counter({"contre": 4, "pour": 1}),
        ("S2", "Socialiste"): Counter({"contre": 3}),
        ("S2", "Union Centriste"): Counter({"pour": 2}),
    }
    our_rows = [
        ("S1", "id-feret", "pour"),       # suit son groupe (majorité "pour")
        ("S1", "id-maurey", "pour"),      # NE suit PAS son groupe (majorité "contre")
        ("S2", "id-feret", "contre"),     # suit son groupe
    ]

    results = fpv.build_scrutins_groupes(
        our_rows, votes_solennels, reverse_id_index, slug_to_senateur,
        id_to_groupe, group_tally,
    )

    print(f"{len(results)} scrutin(s) regroupé(s) :")
    for r in results:
        print(f"  {r['scrutin_id']} ({r['scrutin_date']}) : {len(r['positions'])} position(s)")

    assert len(results) == 2, results
    # Trié par date décroissante : S1 (2024-03-01) avant S2 (2024-01-15)
    assert [r["scrutin_id"] for r in results] == ["S1", "S2"], results

    s1 = results[0]
    assert s1["votants"] == 340 and s1["pour"] == 200 and s1["contre"] == 130
    # abstentions déduites : suffrages_exprimes(330) - pour(200) - contre(130) = 0
    assert s1["abstentions"] == 0, s1["abstentions"]
    assert len(s1["positions"]) == 2

    feret_pos = next(p for p in s1["positions"] if p["senateur_slug"] == "feret_corinne14281w")
    maurey_pos = next(p for p in s1["positions"] if p["senateur_slug"] == "maurey_herve08009t")
    assert feret_pos["vote_comme_son_groupe"] is True, feret_pos
    assert maurey_pos["vote_comme_son_groupe"] is False, maurey_pos

    s2 = results[1]
    assert len(s2["positions"]) == 1
    assert s2["positions"][0]["senateur_slug"] == "feret_corinne14281w"
    assert s2["positions"][0]["vote_comme_son_groupe"] is True

    print("OK : build_scrutins_groupes regroupe correctement par scrutin, calcule les "
          "abstentions déduites, et la comparaison individuelle/groupe reste correcte.\n")


if __name__ == "__main__":
    test_vote_solennel_filter()
    test_build_senateur_id_index()
    test_build_scrutins_groupes()
    print("=== Tous les tests hors-ligne passent (partie non dépendante du schéma votes_senat.csv.gz) ===")

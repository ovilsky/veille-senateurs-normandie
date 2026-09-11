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


if __name__ == "__main__":
    test_vote_solennel_filter()
    test_build_senateur_id_index()
    print("=== Tous les tests hors-ligne passent (partie non dépendante du schéma votes_senat.csv.gz) ===")

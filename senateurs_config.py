#!/usr/bin/env python3
"""
Liste des sénateurs normands suivis par l'outil de veille.

CE FICHIER EST LE SEUL ENDROIT OÙ MODIFIER LA LISTE DES SÉNATEURS SUIVIS.
Il n'est jamais dupliqué ailleurs (ni dans le scraper, ni dans le HTML) :
fetch_activite_senateurs.py importe SENATEURS depuis ce module, et le
bloc de données injecté dans index.html est entièrement régénéré à partir
de ce que ce fichier + le scraper produisent.

Contexte renouvellement 2026 :
  - Élections sénatoriales le 27 septembre 2026 (série 2).
  - Calvados, Eure et Seine-Maritime sont en série 2 : leurs 12 sièges
    seront renouvelés le 27/09/2026. Les sénateurs listés ci-dessous pour
    ces 3 départements sont donc les sortants, à mettre à jour après
    l'élection (nouveaux "slug"/"matricule" à récupérer sur
    https://www.senat.fr/senateurs/senatl.html une fois les résultats
    connus).
  - Manche et Orne sont en série 1 (déjà renouvelée en 2023) : leurs
    sénateurs ne changent pas le 27/09/2026, mandat jusqu'en 2029.

Champs :
  nom       : nom d'affichage
  dept      : nom du département
  dept_code : code INSEE du département (utile pour tri/affichage)
  groupe    : groupe politique au Sénat (au 07/09/2026)
  slug      : identifiant utilisé dans les URLs senat.fr,
              ex. https://www.senat.fr/senateur/{slug}.html
  matricule : identifiant interne du Sénat (utile pour data.senat.fr /
              recoupement), ex. "14281W"
  serie     : 1 ou 2 — quelle série sénatoriale (pour savoir qui est
              renouvelé le 27/09/2026)
  renouvele_2026 : bool, dérivé de `serie == 2`, laissé explicite pour
                   lisibilité
"""

SENATEURS = [
    # --- Calvados (14) — série 2, renouvelé le 27/09/2026 ---
    {
        "nom": "Pascal Allizard",
        "dept": "Calvados",
        "dept_code": "14",
        "groupe": "Les Républicains",
        "slug": "allizard_pascal14133k",
        "matricule": "14133K",
        "serie": 2,
    },
    {
        "nom": "Sonia de La Provôté",
        "dept": "Calvados",
        "dept_code": "14",
        "groupe": "Union Centriste",
        "slug": "de_la_provote_sonia19735d",
        "matricule": "19735D",
        "serie": 2,
    },
    {
        "nom": "Corinne Féret",
        "dept": "Calvados",
        "dept_code": "14",
        "groupe": "Socialiste, Écologiste et Républicain",
        "slug": "feret_corinne14281w",
        "matricule": "14281W",
        "serie": 2,
    },
    # --- Eure (27) — série 2, renouvelé le 27/09/2026 ---
    {
        "nom": "Nicole Duranton",
        "dept": "Eure",
        "dept_code": "27",
        "groupe": "Rassemblement des démocrates, progressistes et indépendants",
        "slug": "duranton_nicole14249w",
        "matricule": "14249W",
        "serie": 2,
    },
    {
        "nom": "Hervé Maurey",
        "dept": "Eure",
        "dept_code": "27",
        "groupe": "Union Centriste",
        "slug": "maurey_herve08009t",
        "matricule": "08009T",
        "serie": 2,
    },
    {
        "nom": "Kristina Pluchet",
        "dept": "Eure",
        "dept_code": "27",
        "groupe": "Les Républicains",
        "slug": "pluchet_kristina20118y",
        "matricule": "20118Y",
        "serie": 2,
    },
    # --- Manche (50) — série 1, PAS renouvelé le 27/09/2026 (mandat jusqu'en 2029) ---
    {
        "nom": "David Margueritte",
        "dept": "Manche",
        "dept_code": "50",
        "groupe": "Les Républicains",
        "slug": "margueritte_david21486b",
        "matricule": "21486B",
        "serie": 1,
    },
    {
        "nom": "Béatrice Gosselin",
        "dept": "Manche",
        "dept_code": "50",
        "groupe": "Les Républicains",
        "slug": "gosselin_beatrice20180f",
        "matricule": "20180F",
        "serie": 1,
    },
    {
        "nom": "Sébastien Fagnen",
        "dept": "Manche",
        "dept_code": "50",
        "groupe": "Socialiste, Écologiste et Républicain",
        "slug": "fagnen_sebastien21062e",
        "matricule": "21062E",
        "serie": 1,
    },
    # --- Orne (61) — série 1, PAS renouvelé le 27/09/2026 (mandat jusqu'en 2029) ---
    {
        "nom": "Olivier Bitz",
        "dept": "Orne",
        "dept_code": "61",
        "groupe": "Rassemblement des démocrates, progressistes et indépendants",
        "slug": "bitz_olivier21043b",
        "matricule": "21043B",
        "serie": 1,
    },
    {
        "nom": "Nathalie Goulet",
        "dept": "Orne",
        "dept_code": "61",
        "groupe": "Union Centriste",
        "slug": "goulet_nathalie07004j",
        "matricule": "07004J",
        "serie": 1,
    },
    # --- Seine-Maritime (76) — série 2, renouvelé le 27/09/2026 ---
    {
        "nom": "Céline Brulin",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Communiste Républicain Citoyen et Écologiste - Kanaky",
        "slug": "brulin_celine19758l",
        "matricule": "19758L",
        "serie": 2,
    },
    {
        "nom": "Agnès Canayer",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Les Républicains",
        "slug": "canayer_agnes14053l",
        "matricule": "14053L",
        "serie": 2,
    },
    {
        "nom": "Patrick Chauvet",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Union Centriste",
        "slug": "chauvet_patrick20144b",
        "matricule": "20144B",
        "serie": 2,
    },
    {
        "nom": "Didier Marie",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Socialiste, Écologiste et Républicain",
        "slug": "marie_didier14001x",
        "matricule": "14001X",
        "serie": 2,
    },
    {
        "nom": "Pascal Martin",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Union Centriste",
        "slug": "martin_pascal19826f",
        "matricule": "19826F",
        "serie": 2,
    },
    {
        "nom": "Catherine Morin-Desailly",
        "dept": "Seine-Maritime",
        "dept_code": "76",
        "groupe": "Union Centriste",
        "slug": "morin_desailly_catherine04070g",
        "matricule": "04070G",
        "serie": 2,
    },
]

for _s in SENATEURS:
    _s["renouvele_2026"] = _s["serie"] == 2

if __name__ == "__main__":
    print(f"{len(SENATEURS)} sénateurs suivis :")
    for s in SENATEURS:
        maj = " (renouvelé le 27/09/2026)" if s["renouvele_2026"] else ""
        print(f"  - {s['nom']} ({s['dept']}, {s['groupe']}){maj}")

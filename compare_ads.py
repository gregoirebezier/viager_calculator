import json
import streamlit as st
import pandas as pd


with open("all_ads.json", "r") as f:
    all_ads = json.load(f)

critères_selection = {
    "bien_type_label": ["maison", "appartement"],  # Types de biens recherchés
    "bien_surf_habitable.Int64": 40,  # Surface habitable minimale en m²
    "prix_achat": 50000,  # Prix maximal
    "bien_nb_piece.Int64": 2,  # Nombre minimal de pièces
    "bien_annee_construction.String": 2000,  # Année de construction minimale
    "bien_dpe.String": "C",  # Classe énergétique
}


def filtrer_annonces(annonces, critères):
    annonces_filtrees = []
    for annonce in annonces:
        surface = annonce.get("bien_surf_habitable", {}).get("Int64", 0)
        nb_pieces = annonce.get("bien_nb_piece", 0).get("Int64", 0)
        annee_construction = int(
            annonce.get("bien_annee_construction", 0).get("String", "0")
        )
        dpe = annonce.get("bien_dpe", {}).get("String", "")
        tete1_age = annonce.get("tete1_age", 0)
        tete2_age = (
            annonce.get("tete2_age", {}).get("Int64", 0)
            if annonce.get("tete2_age", {}).get("Valid", False)
            else 0
        )
        age_min_occupant = min(tete1_age, tete2_age) if tete2_age != 0 else tete1_age

        if (
            annonce["bien_type_label"] in critères["bien_type_label"]
            and surface >= critères["bien_surf_habitable.Int64"]
            and annonce["mandat_bouquet_fai"]["Int64"] <= critères["prix_achat"]
            and nb_pieces >= critères["bien_nb_piece.Int64"]
            and dpe == critères["bien_dpe.String"]
            and annee_construction >= critères["bien_annee_construction.String"]
        ):
            rentabilites = {}
            for age_fin_de_vie in [90, 95, 100]:
                annees = age_fin_de_vie - age_min_occupant
                mois = max(annees * 12, 0)

                cout_total = (
                    annonce["mandat_bouquet_fai"]["Int64"]
                    + (annonce["mandat_rente"]["Int64"] * mois)
                    + (
                        (
                            annonce["bien_taxe_fonciere"]["Int64"]
                            + annonce["bien_ordure_menagere"]["Int64"]
                        )
                        * max(annees, 0)
                    )
                )

                rentabilite = annonce["vlb_displayed"] - cout_total
                rentabilites[f"rentabilite_a_{age_fin_de_vie}_ans"] = rentabilite

            res = {
                **rentabilites,
                "link": "https://www.costes-viager.com"
                + annonce["url_path_alternative"],
                "bien_type_label": annonce["bien_type_label"],
                "bien_surf_habitable": surface,
                "prix_achat": annonce["prix_achat"],
                "mandat_bouquet": annonce["mandat_bouquet_fai"]["Int64"],
                "prix estimation": annonce["vlb_displayed"],
                "decote": annonce["mandat_decote_percent"],
                "ordures_menageres": annonce["bien_ordure_menagere"]["Int64"],
                "taxe_fonciere": annonce["bien_taxe_fonciere"]["Int64"],
                "frais_agence": annonce["mandat_frais_agence"],
                "bien_nb_piece": nb_pieces,
                "bien_annee_construction": annee_construction,
                "vente_type_is_libre": annonce["vente_type_is_libre"],
                "bien_dpe": dpe,
            }
            if res["rentabilite_a_100_ans"] > 0:
                annonces_filtrees.append(res)
    return annonces_filtrees


annonces_filtrees = filtrer_annonces(all_ads, critères_selection)
with open("annonces_filtrees.json", "w") as f:
    json.dump(annonces_filtrees, f, indent=4)

df = pd.read_json("annonces_filtrees.json")
st.title("Annonces filtrées")
st.write(df)

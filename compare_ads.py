import json
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide")

if 'departements_selectionnes' not in st.session_state:
    st.session_state['departements_selectionnes'] = []

def lire_fichier_ndjson(chemin_fichier):
    with open(chemin_fichier, "r") as f:
        for ligne in f:
            yield json.loads(ligne)

@st.cache_resource
def extraire_departements_filtres(annonces_filtrees):
    return sorted({annonce["departement"]+" "+annonce["bien_departement_label"] for annonce in annonces_filtrees})


@st.cache_resource
def charger_annonces():
    return list(lire_fichier_ndjson("json_files/all_ads.json"))


def rendre_liens_cliquables(df, nom_colonne_url):
    df[nom_colonne_url] = df[nom_colonne_url].apply(
        lambda x: f'<a href="{x}" target="_blank">{x}</a>'
    )
    return df

def filtrer_par_departement(annonces_filtrees, departements_selectionnes):
    if not departements_selectionnes:
        return annonces_filtrees
    return [annonce for annonce in annonces_filtrees if annonce["departement"]+" "+annonce["bien_departement_label"] in departements_selectionnes]


all_ads = charger_annonces()
all_ads = [json.loads(x) for x in set(json.dumps(x) for x in all_ads)]


if 'departements_selectionnes' not in st.session_state:
    st.session_state['departements_selectionnes'] = []

# with open("json_files/first_ad.json", "w") as f:
#     json.dump(all_ads[0], f, indent=4)
surface_minimale = st.number_input(
    "Surface habitable minimale (en m²)", min_value=0, value=50
)
prix_maximal = st.number_input("Prix maximal", min_value=0, value=50000)
nombre_pieces_minimal = st.number_input(
    "Nombre minimal de pièces", min_value=0, value=2
)
annee_construction_minimale = st.number_input(
    "Année de construction minimale", min_value=0, value=1950
)
classe_energetique = st.selectbox(
    "Classe énergétique", ["A", "B", "C", "D", "E", "F", "G"], index=3
)

argent_par_mois = st.number_input(
    "Argent disponible par mois (en €)", min_value=0, value=500
)

age_rentabilite = st.number_input("Âge pour évaluer la rentabilité", min_value=75, max_value=100, value=100, step=1)

critères_selection = {
    "bien_surf_habitable.Int64": surface_minimale,
    "prix_achat": prix_maximal,
    "argent_par_mois": argent_par_mois,
    "bien_nb_piece.Int64": nombre_pieces_minimal,
    "bien_annee_construction.String": annee_construction_minimale,
    "bien_dpe.String": classe_energetique,
    "age_rentabilite": age_rentabilite,
}


def classe_energetique_superieure(classe_annonce, classe_critere):
    ordre_classes = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}
    return ordre_classes[classe_annonce] <= ordre_classes[classe_critere]


def filtrer_annonces(annonces, critères, age_rentabilite):
    annonces_filtrees = []
    for annonce in annonces:
        annonce = annonce["results"]["annonces"][0]
        surface = annonce.get("bien_surf_habitable", {}).get("Int64", 0)
        nb_pieces = annonce.get("bien_nb_piece", 0)
        if type(nb_pieces) == dict:
            nb_pieces = nb_pieces.get("Int64", 0)
        annee_construction = annonce.get("bien_annee_construction", 0)
        if type(annee_construction) == dict:
            annee_construction = annee_construction.get("String", 0)
        try:
            annee_construction = int(annee_construction)
        except ValueError:
            annee_construction = 9999
        dpe = annonce.get("bien_dpe", {}).get("String", "")
        if not dpe:
            dpe = ""
        tete1_age = annonce.get("tete1_age", 0)
        tete2_age = (
            annonce.get("tete2_age", {}).get("Int64", 0)
            if annonce.get("tete2_age", {}).get("Valid", False)
            else 0
        )
        age_min_occupant = min(tete1_age, tete2_age) if tete2_age != 0 else tete1_age
        if (
            surface >= critères["bien_surf_habitable.Int64"]
            and annonce["mandat_rente"]["Int64"] <= critères["argent_par_mois"]
            and annonce["mandat_bouquet_fai"]["Int64"] <= critères["prix_achat"]
            and nb_pieces >= critères["bien_nb_piece.Int64"]
            and (
                dpe == ""
                or classe_energetique_superieure(dpe, critères["bien_dpe.String"])
            )
            and annee_construction >= critères["bien_annee_construction.String"]
            ):
            rentabilites = {}
            all_rentabilites = sorted([age_rentabilite, 90, 95, 100])
            for age_fin_de_vie in all_rentabilites:
                annees = age_fin_de_vie - age_min_occupant
                mois = max(annees * 12, 0)

                cout_total = (
                    annonce["mandat_bouquet_fai"]["Int64"]
                    + annonce["mandat_frais_agence"]
                    + (annonce["mandat_rente"]["Int64"] * mois)
                    + (
                        (
                            annonce["bien_taxe_fonciere"]["Int64"]
                        )
                        * max(annees, 0)
                    )
                )

                rentabilite = annonce["vlb_displayed"] - cout_total
                rentabilites[f"rentabilite_a_{age_fin_de_vie}_ans"] = rentabilite

            res = {
                **rentabilites,
                "mandat_bouquet": annonce["mandat_bouquet_fai"]["Int64"],
                "argent_par_mois": annonce["mandat_rente"]["Int64"],
                "taxe_fonciere": annonce["bien_taxe_fonciere"]["Int64"],
                "link": "https://www.costes-viager.com"
                + annonce["url_path_alternative"],
                "bien_type_label": annonce["bien_type_label"],
                "bien_surf_habitable": surface,
                "prix_achat": annonce["prix_achat"],
                "prix estimation": annonce["vlb_displayed"],
                "decote": annonce["mandat_decote_percent"],
                "ordures_menageres": annonce["bien_ordure_menagere"]["Int64"],
                "frais_agence": annonce["mandat_frais_agence"],
                "bien_nb_piece": nb_pieces,
                "bien_annee_construction": annee_construction,
                "bien_dpe": dpe,
                "departement": annonce["bien_departement_code"],
                "bien_departement_label": annonce["bien_departement_label"],
            }
            renta = "rentabilite_a_" + str(age_rentabilite) + "_ans"
            if (
                res[renta] > 0
                and not annonce["vendu"]
                and annonce["vente_status"] != "vente en cours"
            ):
                annonces_filtrees.append(res)
    return annonces_filtrees


annonces_filtrees = filtrer_annonces(all_ads, critères_selection, age_rentabilite)

departements_filtres = extraire_departements_filtres(annonces_filtrees)

departements_selectionnes = st.multiselect(
    "Sélectionnez le(s) département(s)",
    options=departements_filtres,
    default=st.session_state['departements_selectionnes']
)

if st.button('Appliquer les filtres'):
    st.session_state['departements_selectionnes'] = departements_selectionnes
    annonces_filtrees = filtrer_par_departement(annonces_filtrees, departements_selectionnes)
else:
    annonces_filtrees = filtrer_par_departement(annonces_filtrees, st.session_state['departements_selectionnes'])

css_style = """
<style>
.table-container {
  overflow-x: auto;
}
</style>
"""


with open("json_files/annonces_filtrees.json", "w") as f:
    json.dump(annonces_filtrees, f, indent=4)

df = pd.read_json("json_files/annonces_filtrees.json")

st.title("Annonces filtrées (uniquement rentables sur " + str(age_rentabilite) + " ans)")
st.write(f"Nombre total d'annonces : {len(all_ads)}")
st.write(f"Nombre d'annonces après filtrage : {len(annonces_filtrees)}")
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(minWidth=100, resizable=True)
gb.configure_column("bien_surf_habitable", minWidth=150)
gb.configure_column("prix_achat", minWidth=150)
gb.configure_column("mandat_bouquet", minWidth=120)
gb.configure_column("prix estimation", minWidth=130)
gb.configure_column("link", hide=True)

gb.configure_selection("single")
gridOptions = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=gridOptions,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    fit_columns_on_grid_load=False,
    height=600,
    allow_unsafe_jscode=True,
)

selected = grid_response["selected_rows"]
if selected:
    selected_row = selected[0]
    link = selected_row["link"]
    st.markdown(f"[Cliquez ici pour ouvrir l'annonce]({link})", unsafe_allow_html=True)

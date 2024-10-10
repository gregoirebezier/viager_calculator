import json
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def configurer_page():
    """Configure la mise en page de la page Streamlit."""
    st.set_page_config(layout="wide")


def initialiser_session_state():
    """Initialise les variables de session si elles ne sont pas déjà définies."""
    if "departements_selectionnes" not in st.session_state:
        st.session_state["departements_selectionnes"] = []


def lire_fichier_ndjson(chemin_fichier):
    """Lit un fichier NDJSON ligne par ligne et retourne un générateur JSON."""
    try:
        with open(chemin_fichier, "r") as fichier:
            for ligne in fichier:
                yield json.loads(ligne)
    except FileNotFoundError:
        st.error(f"Fichier {chemin_fichier} non trouvé.")
        return []


@st.cache_resource
def charger_annonces(chemin_fichier="json_files/all_ads.json"):
    """Charge les annonces depuis un fichier NDJSON."""
    return list(lire_fichier_ndjson(chemin_fichier))


@st.cache_resource
def extraire_departements_filtres(annonces_filtrees):
    """Extrait et trie les départements à partir des annonces filtrées."""
    departements = set()
    for annonce in annonces_filtrees:
        departement = annonce.get("departement")
        bien_departement_label = annonce.get("bien_departement_label")
        if departement and bien_departement_label:
            departements.add(f"{departement} {bien_departement_label}")
    return sorted(departements)


def rendre_liens_cliquables(df, nom_colonne_url):
    """Transforme une colonne de liens en liens cliquables dans un DataFrame."""
    if nom_colonne_url in df.columns:
        df[nom_colonne_url] = df[nom_colonne_url].apply(
            lambda x: f'<a href="{x}" target="_blank">{x}</a>' if pd.notnull(x) else x
        )
    return df


def filtrer_par_departement(annonces_filtrees, departements_selectionnes):
    """Filtre les annonces par département sélectionné."""
    if not departements_selectionnes:
        return annonces_filtrees
    return [
        annonce
        for annonce in annonces_filtrees
        if f"{annonce.get('departement')} {annonce.get('bien_departement_label')}"
        in departements_selectionnes
    ]


def configurer_critères():
    """Configure les critères de filtrage à partir des inputs utilisateur."""
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
    age_rentabilite = st.number_input(
        "Âge pour évaluer la rentabilité",
        min_value=75,
        max_value=130,
        value=100,
        step=1,
    )

    critères_selection = {
        "bien_surf_habitable.Int64": surface_minimale,
        "prix_achat": prix_maximal,
        "argent_par_mois": argent_par_mois,
        "bien_nb_piece.Int64": nombre_pieces_minimal,
        "bien_annee_construction.String": annee_construction_minimale,
        "bien_dpe.String": classe_energetique,
        "age_rentabilite": age_rentabilite,
    }
    return critères_selection


def classe_energetique_superieure(classe_annonce, classe_critere):
    """Vérifie si la classe énergétique de l'annonce est égale ou supérieure au critère."""
    ordre_classes = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}
    return ordre_classes.get(classe_annonce, 6) <= ordre_classes.get(classe_critere, 6)


def get_value(data, key, default=None):
    """
    Récupère la valeur dans un dictionnaire de données potentiellement imbriqué avec des types complexes.
    Si la valeur est un dictionnaire, essaie de récupérer la valeur avec les clés appropriées (comme "Int64", "String", etc.).
    """
    if isinstance(data, dict):
        if "Valid" in data and not data["Valid"]:
            return default
        if key in data:
            return data.get(key, default)
    return data if data is not None else default


def filtrer_annonces(annonces, critères):
    annonces_filtrees = []
    ids_rencontres = set()

    for annonce_data in annonces:
        try:
            annonce = annonce_data["results"]["annonces"][0]
            annonce_id = annonce.get("id", None)
            if annonce_id in ids_rencontres:
                continue

            surface = get_value(annonce.get("bien_surf_habitable"), "Int64", 0)
            nb_pieces = get_value(annonce.get("bien_nb_piece"), "Int64", 0)
            annee_construction = get_value(
                annonce.get("bien_annee_construction"), "String", "9999"
            )
            annee_construction = (
                int(annee_construction) if annee_construction.isdigit() else 9999
            )
            dpe = get_value(annonce.get("bien_dpe"), "String", "")
            tete1_age = annonce.get("tete1_age", 0)
            tete2_age = get_value(annonce.get("tete2_age"), "Int64", 0)
            age_min_occupant = (
                min(tete1_age, tete2_age) if tete2_age != 0 else tete1_age
            )

            if (
                surface >= critères["bien_surf_habitable.Int64"]
                and get_value(annonce.get("mandat_rente"), "Int64", 0)
                <= critères["argent_par_mois"]
                and get_value(annonce.get("mandat_bouquet_fai"), "Int64", 0)
                <= critères["prix_achat"]
                and nb_pieces >= critères["bien_nb_piece.Int64"]
                and (
                    not dpe
                    or classe_energetique_superieure(dpe, critères["bien_dpe.String"])
                )
                and annee_construction >= critères["bien_annee_construction.String"]
            ):
                rentabilites = calculer_rentabilite(
                    annonce, age_min_occupant, critères["age_rentabilite"]
                )

                frais_agence = get_value(annonce.get("mandat_frais_agence"), "Int64", 0)

                res = {
                    **rentabilites,
                    "mandat_bouquet": get_value(
                        annonce.get("mandat_bouquet_fai"), "Int64", 0
                    ),
                    "argent_par_mois": get_value(
                        annonce.get("mandat_rente"), "Int64", 0
                    ),
                    "taxe_fonciere": get_value(
                        annonce.get("bien_taxe_fonciere"), "Int64", 0
                    ),
                    "link": "https://www.costes-viager.com"
                    + annonce.get("url_path_alternative", ""),
                    "bien_type_label": annonce.get("bien_type_label", ""),
                    "bien_surf_habitable": surface,
                    "prix_achat": annonce.get("prix_achat", 0),
                    "prix estimation": annonce.get("vlb_displayed", 0),
                    "decote": annonce.get("mandat_decote_percent", 0),
                    "ordures_menageres": get_value(
                        annonce.get("bien_ordure_menagere"), "Int64", 0
                    ),
                    "frais_agence": frais_agence,
                    "bien_nb_piece": nb_pieces,
                    "bien_annee_construction": annee_construction,
                    "bien_dpe": dpe,
                    "departement": annonce.get("bien_departement_code", ""),
                    "bien_departement_label": annonce.get("bien_departement_label", ""),
                }

                renta = f"rentabilite_a_{critères['age_rentabilite']}_ans"
                if (
                    res[renta] > 0
                    and not annonce.get("vendu", False)
                    and annonce.get("vente_status") != "vente en cours"
                ):
                    annonces_filtrees.append(res)
                    ids_rencontres.add(annonce_id)
        except (KeyError, ValueError, AttributeError) as e:
            st.warning(f"Erreur lors du traitement d'une annonce : {e}")

    return annonces_filtrees


def calculer_rentabilite(annonce, age_min_occupant, age_rentabilite):
    """Calcule la rentabilité d'une annonce en fonction de l'âge de rentabilité."""
    rentabilites = {}
    ages_de_vie = sorted([age_rentabilite, 90, 95, 100])

    bouquet_fai = annonce.get("mandat_bouquet_fai", {}).get("Int64", 0)
    prix_achat = annonce.get("prix_achat", 0)
    rente_mensuelle = annonce.get("mandat_rente", {}).get("Int64", 0)
    taxe_fonciere_annuelle = annonce.get("bien_taxe_fonciere", {}).get("Int64", 0)
    valeur_libre = annonce.get("vlb_displayed", 0)

    for age in ages_de_vie:
        annees = age - age_min_occupant
        mois = max(annees * 12, 0)

        cout_total = (
            bouquet_fai
            + prix_achat * 0.08  # frais de notaire
            + rente_mensuelle * mois
            + taxe_fonciere_annuelle * annees
        )
        rentabilite = valeur_libre - cout_total
        rentabilites[f"rentabilite_a_{age}_ans"] = rentabilite

    return rentabilites


def afficher_annonces_filtrees(annonces_filtrees, age_rentabilite):
    """Affiche les annonces filtrées avec un tableau interactif."""
    if not annonces_filtrees:
        st.warning("Aucune annonce trouvée avec les critères actuels.")
        return

    df = pd.DataFrame(annonces_filtrees)

    if "link" in df.columns:
        df = rendre_liens_cliquables(df, "link")

    st.title(f"Annonces filtrées (rentabilité sur {age_rentabilite} ans)")
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

    selected = grid_response.get("selected_rows", None)

    if selected is not None and len(selected) > 0:
        if isinstance(selected, pd.DataFrame):
            selected_row = selected.iloc[0]
        else:
            selected_row = selected[0]

        link = selected_row.get("link", "")
        if link:
            st.markdown(f"{link}", unsafe_allow_html=True)
        else:
            st.write("No link available for this row.")
    else:
        st.write("No rows selected.")


def main():
    """Fonction principale exécutant l'application."""
    configurer_page()
    initialiser_session_state()

    all_ads = charger_annonces()
    critères = configurer_critères()
    annonces_filtrees = filtrer_annonces(all_ads, critères)

    departements_filtres = extraire_departements_filtres(annonces_filtrees)
    departements_selectionnes = st.multiselect(
        "Sélectionnez le(s) département(s)",
        options=departements_filtres,
        default=st.session_state["departements_selectionnes"],
    )

    if st.button("Appliquer les filtres"):
        st.session_state["departements_selectionnes"] = departements_selectionnes
    annonces_filtrees = filtrer_par_departement(
        annonces_filtrees, st.session_state["departements_selectionnes"]
    )

    afficher_annonces_filtrees(annonces_filtrees, critères["age_rentabilite"])


if __name__ == "__main__":
    main()

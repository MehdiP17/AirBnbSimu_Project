from pathlib import Path
import json
import pandas as pd
import shapely

# fonctions de vérification écrites dans checks.py, lancées ici (import avec un point : src/ est un package)
from . import checks
from .checks import RAW_S3_DIR, list_files, choose_files, check_selection, check_tables

#########################################################################################################
# ---------------------DEFINITION DES CONSTANTES POUR LA TRANSFORMATION------------------------------------------
#########################################################################################################

## --------- CONSTANTES : DOSSIERS EN LOCAL (pour les exports) ---------
# racine du projet 
ROOT = Path(__file__).resolve().parent.parent
# dossier des exports pour verifier à la main en local
EXPORTS_DIR = ROOT / "data" / "exports"

## --------- CONSTANTES : TABLES LOYERS & QUARTIERS ---------
# Paris = 80 quartiers, 4 par arrondissement : quartiers 1-4 -> 1er, 5-8 -> 2e, etc.
NEIGHBORHOODS_PER_ARR = 4

# Valeur de la colonne meuble_txt pour un logement meublé
MEUBLE_TEXT = "meublé"

## --------- CONSTANTES : Table quartiers ---------
## les colonnes de la table quartiers
QUARTIERS_COLUMNS = ["id_quartier", "nom_quartier", "arrondissement", "code_grand_quartier",
                         "latitude", "longitude", "geo_shape"]

## --------- CONSTANTES : Table loyers ---------
## colonnes du rents brut à mettre dans la table loyer
LOYERS_RAW_COLUMNS = ["annee", 
                     "id_quartier", "piece", "epoque", "meuble_txt", 
                     "ref", "max", "min"]

## colonnes renommées pour la table loyers
LOYERS_RENAME = {"piece": "nb_pieces", 
                "ref": "rent_ref", 
                "max": "rent_max", 
                "min": "rent_min"
                }
## colonnes : gardées
LOYERS_COLUMNS = ["annee", 
                 "id_quartier", "nb_pieces", "epoque", "meuble", 
                 "rent_ref", "rent_max", "rent_min"]

## --------- CONSTANTES : TABLE ARRONDISSEMENTS ---------
## Correspondance numéro d'arrondissement --> neighbourhood_cleansed d'Inside Airbnb listings
ARR_NAMES = {
    1: "Louvre", 2: "Bourse", 3: "Temple", 4: "Hôtel-de-Ville", 5: "Panthéon",
    6: "Luxembourg", 7: "Palais-Bourbon", 8: "Élysée", 9: "Opéra", 10: "Entrepôt",
    11: "Popincourt", 12: "Reuilly", 13: "Gobelins", 14: "Observatoire", 15: "Vaugirard",
    16: "Passy", 17: "Batignolles-Monceau", 18: "Buttes-Montmartre", 19: "Buttes-Chaumont",
    20: "Ménilmontant",
}
## Sens inverse (nom -> numéro) pour remplir la colonne arrondissement des listings
ARR_MAP = {nom: numero for numero, nom in ARR_NAMES.items()}

## --------- CONSTANTES : TABLE LISTINGS & LISTING_SNAPSHOTS ---------

## -------- CONSTANTES : Filtrage des listings airbnb --------
### Colonnes à garder des fichiers listings brut dont on a besoin pour la transfo
COLONNES_LISTINGS = [
    "id", "last_scraped", "neighbourhood_cleansed", "latitude", "longitude",
    "room_type", "accommodates", "bedrooms", "bathrooms", "bathrooms_text", "amenities",
    "price", "price_quote_checkin_date", "price_quote_checkout_date", "price_quote_raw",
    "minimum_nights", "number_of_reviews_ltm", "license",
]

### Filtre sur les valeurs des données du listings bruts
### Filtre logement entier
ROOM_TYPE_ENTIRE = "Entire home/apt"
### Filtre hors hotel / bail mobilité
TEXTE_HOTEL = "Exempt - hotel-type listing"
TEXTE_BAIL_MOBILITE = 'Available with a mobility lease only ("bail mobilité")'
## 28 nuits et plus = location bail mobilite, on l'écarte
MAX_NIGHTS = 28
### Filtres securite pour des outliers de prix / accomodate
PRICE_MIN = 20
PRICE_MAX = 1000
MAX_ACCOMMODATES = 16

## -------- CONSTANTES :  Table listings --------
## Colonnes renommées à la fin du nettoyage des listings
LISTINGS_RENAME = {
    "id": "listing_id",
}
## Table listings : une ligne par annonce (infos de description de l'annonce hors prix, on garde le plus recent)
LISTINGS_COLUMNS = [
    "listing_id", "arrondissement", "room_type", "accommodates", "bedrooms", "bathrooms",
    "pieces", "latitude", "longitude", "n_amenities",
]

## -------- CONSTANTES :  Table listings_snapshots --------
## Table listing_snapshots : une ligne par annonce et par relevé (evolution du prix dans le temps pour une meme annonce)
SNAPSHOTS_COLUMNS = [
    "listing_id", "snapshot_date", "releve", "price", "avec_taxes",
    "checkin_month", "days_before_checkin", "test_nights", "minimum_nights", "number_of_reviews_ltm",
]
#########################################################################################################
# -------------------------DEFINITION DES FONCTIONS POUR LE TRANSFORM-------------------------------------
#########################################################################################################

# --------- 1. VERIFIER TOUS LES FICHIERS POUR LE TRANSFORM ---------

## Utilise les fonctions du checks.py pour la verificartion pre-transformation
def get_files():
    """
    Récupère les noms des fichiers à transformer grâce aux fonctions de checks.py.
    Renvoie {"listings": {extract: file}, "reviews": file, "rents": file}.
    """
    # lister tous les fichiers bruts puis garder ceux qui nous intéressent
    all_files = list_files()
    files = choose_files(all_files)

    # vérifier qu'il ne manque rien (bloque la pipeline si un fichier obligatoire manque)
    check_selection(files)

    return files

# --------- 2. TRANSFORMATION ET CREATION TABLE LOYERS & QUARTIERS ---------

## --------- Lire : fichier rents brut ---------
## MODIF POST S3: modifier read_parquet par read_csv

def read_rents(file):
    """Lit le fichier des loyers (parquet) depuis raw_s3 --> dataframe"""
    rents = pd.read_parquet(RAW_S3_DIR / file)
    print(f"rents raw: {file} -> {rents.shape}")
    return rents

## --------- Creation : table quartiers ---------
def transform_quartiers(rents_df):
    """Construit la table quartiers (80 lignes) à partir du fichier brut rents"""
    # une seule ligne par quartier
    quartiers = rents_df.drop_duplicates(subset="id_quartier").copy()

    # 4 quartiers par arrondissement : quartiers 1-4 -> 1er, 5-8 -> 2e, etc.
    quartiers["arrondissement"] = (quartiers["id_quartier"] - 1) // NEIGHBORHOODS_PER_ARR + 1

    # centre du quartier (binaire WKB) -> longitude et latitude
    centers = shapely.from_wkb(quartiers["geo_point_2d"])
    quartiers["longitude"] = shapely.get_x(centers)
    quartiers["latitude"] = shapely.get_y(centers)

    # contour du quartier (binaire WKB) -> texte GeoJSON, lisible par les librairies de cartes
    shapes = shapely.from_wkb(quartiers["geo_shape"])
    quartiers["geo_shape"] = shapely.to_geojson(shapes)

    # garder les colonnes utiles, triées par quartier
    quartiers = quartiers[QUARTIERS_COLUMNS]
    quartiers = quartiers.sort_values("id_quartier").reset_index(drop=True)

    print(f"table quartiers : {quartiers.shape} \n")
    return quartiers

## --------- Creation : table loyers ---------
def transform_loyers(rents_df):
    """Construit la table loyers : toutes les années, meublé et non meublé (17 920 lignes)."""
    loyers = rents_df[LOYERS_RAW_COLUMNS].copy()

    # annee : str --> passer en int
    loyers["annee"] = loyers["annee"].astype(int)
    # meuble_txt : str -> passer en true/false
    loyers["meuble"] = loyers["meuble_txt"] == MEUBLE_TEXT

    # renommer les colonnes de la table loyers
    loyers = loyers.rename(columns=LOYERS_RENAME)
    # garder les colonnes utiles et les trier
    loyers = loyers[LOYERS_COLUMNS]
    loyers = loyers.sort_values(["annee", "id_quartier", "nb_pieces", "epoque", "meuble"]).reset_index(drop=True)

    print(f"table loyers : {loyers.shape} \n")
    return loyers

# --------- 2. TRANSFORMATION ET CREATION TABLE ARRONDISSEMENTS ---------
## --------- Creation : table arrondissements ---------
def transform_arrondissements(neighborhoods):
    """Construit la table arrondissements (20 lignes : numero, nom) à partir de la table quartiers."""
    # les numéros viennent de la table quartiers, pour que la FK quartiers.arrondissement existe toujours
    numbers = sorted(neighborhoods["arrondissement"].unique())
    arrondissements = pd.DataFrame({"numero": numbers})

    # numéro -> nom
    arrondissements["nom"] = arrondissements["numero"].map(ARR_NAMES)

    print(f"table arrondissements : {arrondissements.shape} \n")
    return arrondissements

# --------- 2. TRANSFORMATION ET CREATION TABLE LISTINGS & LISTINGS_SNAPSHOTS ---------
## --------- Lire et concat : fichier listings brut ---------
def read_listings(files):
    """
    Lit tous les relevés listings sélectionnés 
    et les empile dans un seul dataframe
    """
    releves = []
    for releve, file in files.items():
        df = pd.read_csv(RAW_S3_DIR / file, usecols=COLONNES_LISTINGS, low_memory=False)
        # on ajoute une colonne releve pour garder de quel fichier vient la ligne (ex. "2026-09")
        df["releve"] = releve
        releves.append(df)
    return pd.concat(releves, ignore_index=True)

## --------- Conversion : convertir dans les bons types ---------
def convert_types(df):
    """
    Prix en nombre (on enlève $ et ,), 
    dates en vraies dates, 
    minimum_nights en entier.
    """
    df = df.copy()

    # prix : texte "$1,250.00" -> nombre 1250.0 (en euros malgré le $)
    df["price"] = pd.to_numeric(
        df["price"].str.replace("$", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce",
    )

    # dates : texte -> date
    df["snapshot_date"] = pd.to_datetime(df["last_scraped"])
    df["price_quote_checkin_date"] = pd.to_datetime(df["price_quote_checkin_date"])
    df["price_quote_checkout_date"] = pd.to_datetime(df["price_quote_checkout_date"])

    # Int64 (avec I majuscule) accepte les vides, contrairement à int
    df["minimum_nights"] = df["minimum_nights"].astype("Int64")
    return df

## --------- Remplissage : remplir valeurs manquantes de bedrooms ---------
def fill_bedrooms(df):
    """
    bedrooms vide : on reprend la valeur la plus récente de la même annonce dans un autre relevé.
    À lancer AVANT les filtres, pour profiter de toutes les lignes.
    """
    df = df.copy()

    # pour chaque id : la dernière valeur de bedrooms connue
    filled = df.dropna(subset=["bedrooms"])
    last_bedrooms = filled.sort_values("snapshot_date").groupby("id")["bedrooms"].last()

    # on ne remplit que les vides
    df["bedrooms"] = df["bedrooms"].fillna(df["id"].map(last_bedrooms))
    return df

## --------- Remplissage : remplir valeurs manquantes manquantes de bathrooms ---------
def fill_bathrooms(df):
    """bathrooms vide : 
    on le remplit depuis bathrooms_text ("1.5 baths", "Half-bath" = 0.5, "No bathroom" = 0).
    """
    df = df.copy()

    # on remplace les cas sans chiffre par un chiffre
    text = df["bathrooms_text"].str.lower().str.replace("half-bath", "0.5").str.replace("no bathroom", "0")

    # on extrait le premier nombre du texte (ex. "1.5 baths" -> 1.5)
    number = pd.to_numeric(text.str.extract(r"(\d+\.?\d*)")[0])
    df["bathrooms"] = df["bathrooms"].fillna(number)
    return df

## --------- Creation de colonnes : days_before_checkin & test_nights ---------
def add_test_stay(df):
    """
    Pour récupérer un prix, Inside Airbnb fait comme un client : 
    sur Airbnb : un devis pour un séjour: avec une date d'arrivée (price_quote_checkin_date) 
    et une date de départ (price_quote_checkout_date). 
    Ce séjour simulé, c'est le séjour test.

    On calcule alors :
        days_before_checkin : combien de jours à l'avance le devis a été demandé
        test_nights : combien de nuits dure le séjour test
    """
    df = df.copy()
    df["days_before_checkin"] = (df["price_quote_checkin_date"] - df["snapshot_date"]).dt.days
    df["test_nights"] = (df["price_quote_checkout_date"] - df["price_quote_checkin_date"]).dt.days
    return df

## --------- Creation de colonnes : arr., checkin_month, pieces, taxes ---------
def add_columns(df):
    """
    Nouvelles colonnes : 
    arrondissement, 
    mois d'arrivée, 
    pièces, 
    taxes.
    """
    df = df.copy()

    # nom du quartier Airbnb -> numéro d'arrondissement
    df["arrondissement"] = df["neighbourhood_cleansed"].map(ARR_MAP)
    df["checkin_month"] = df["price_quote_checkin_date"].dt.month

    # pièces = chambres + 1 (le séjour), 4 = 4 et plus (comme dans la table loyers)
    df["pieces"] = (df["bedrooms"] + 1).clip(upper=4)

    # prix avec taxes : 1 si le devis indique des taxes, sinon 0
    df["avec_taxes"] = df["price_quote_raw"].map(lambda t: json.loads(t)["quote"]["taxes"] is not None).astype(int)
    return df

## --------- Creation de colonnes : count des amenities ---------
def count_amenities(df):
    """Nombre d'équipements : texte JSON -> liste, puis on compte les éléments."""
    df = df.copy()

    # amenities : texte '["Wifi", "Kitchen", ...]' -> liste Python
    amenity_lists = df["amenities"].map(json.loads)
    df["n_amenities"] = amenity_lists.map(len)
    return df

## --------- Filtres : des listings brut  ---------
def filter_listings(df):
    """
    Les 10 filtres : 
        logement entier, 
        annonce active, 
        courte durée, 
        prix et séjour test valides.
    """
    # 1. logement entier seulement
    df = df[df["room_type"] == ROOM_TYPE_ENTIRE]
    # 2. au moins 3 commentaires sur les 12 derniers mois (annonce active)
    df = df[df["number_of_reviews_ltm"] >= 3]
    # 3. courte durée seulement
    df = df[df["minimum_nights"] < MAX_NIGHTS]
    # 4 et 5. pas d'hôtel, pas de bail mobilité seul
    df = df[df["license"] != TEXTE_HOTEL]
    df = df[df["license"] != TEXTE_BAIL_MOBILITE]
    # 6 et 7. prix rempli et réaliste
    df = df[df["price"].notna()]
    df = df[df["price"].between(PRICE_MIN, PRICE_MAX)]
    # 8. pas plus de 16 voyageurs
    df = df[df["accommodates"] <= MAX_ACCOMMODATES]
    # 9 et 10. séjour test dans le futur et pas trop long
    df = df[df["days_before_checkin"] >= 0]
    df = df[df["test_nights"] <= MAX_NIGHTS]
    return df.copy()

## --------- CREATION TABLE LISTINGS : REGROUPE LES ETAPES ---------
def transform_listings(df):
    """Nettoie les listings en enchaînant les étapes, et affiche le nombre de lignes après chacune."""
    print(f"listings bruts : {df.shape}")

    df = convert_types(df)
    # bedrooms AVANT les filtres (besoin de toutes les lignes des 3 relevés)
    df = fill_bedrooms(df)
    df = add_test_stay(df)

    df = filter_listings(df)
    print(f"après les 10 filtres : {df.shape}")

    df = fill_bathrooms(df)
    df = add_columns(df)
    df = count_amenities(df)

    # noms finaux des colonnes (id -> listing_id, etc.)
    df = df.rename(columns=LISTINGS_RENAME)
    print(f"listings nettoyés : {df.shape}")

    return df


## --------- CREATION TABLE LISTING_SNAPSHOTS ---------
def build_listing_snapshots(clean_listings):
    """Table de faits : une ligne par annonce et par relevé (prix, séjour test, activité)."""
    snapshots = clean_listings[SNAPSHOTS_COLUMNS]
    snapshots = snapshots.sort_values(["listing_id", "snapshot_date"]).reset_index(drop=True)

    print(f"table listing_snapshots : {snapshots.shape} \n")
    return snapshots


## --------- CREATION TABLE LISTINGS ---------
def build_listings(clean_listings):
    """Table dimension : une ligne par annonce, avec les valeurs du relevé le plus récent."""
    # trier par date puis garder la dernière ligne de chaque annonce = relevé le plus récent
    listings = clean_listings.sort_values("snapshot_date")
    listings = listings.drop_duplicates(subset="listing_id", keep="last")

    listings = listings[LISTINGS_COLUMNS]
    listings = listings.sort_values("listing_id").reset_index(drop=True)

    print(f"table listings : {listings.shape} \n")
    return listings



# --------- EXPORT DES TABLES ---------
def export_tables(tables):
    """Écrit chaque table en CSV dans data/exports/ pour les vérifier à la main"""
    # créer le dossier s'il n'existe pas encore
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # une table -> un fichier CSV (les anciens fichiers sont écrasés)
    for name, table in tables.items():
        path = EXPORTS_DIR / f"{name}.csv"
        table.to_csv(path, index=False)
        print(f"export : {name} {table.shape} -> {path.relative_to(ROOT)}")

# --------- PIPELINE QUI RASSEMBLE TRANSFO ET CREATION TABLES ---------
# Lancée par etl.py. Ne reçoit rien, renvoie le dict des tables vérifiées.
def transform_all():
    """Sélectionne, lit, contrôle et transforme les fichiers bruts. Renvoie {"nom_table": DataFrame}."""

    # 1. Verifier la présence de tous les fichiers pour le transform
    print("\n--------- VERIFICATION PRESENCE FICHIERS À TRANSFORMER ---------\n")
    files = get_files()

    # 2. Recap des fichiers retenus et du nombre de warnings
    print("\n--------- RECAP FICHIERS À TRANSFORMER ---------\n")
    print(f"listings : {len(files['listings'])} relevé(s) --> {list(files['listings'])}")
    print(f"reviews  : {files['reviews']}")
    print(f"rents    : {files['rents']}")
    print(f"warnings : {checks.WARNING_COUNT}")

    # 3. Lecture du fichier des loyers
    print("\n--------- RECAP RENTS ---------\n")
    rents_raw = read_rents(files["rents"])

    # 4. Lecture et nettoyage des relevés listings
    # (leur contenu est déjà vérifié avant la mise en S3 : pas de contrôle du brut ici)
    print("\n--------- RECAP LISTINGS ---------\n")
    listings_raw = read_listings(files["listings"])
    clean_listings = transform_listings(listings_raw)

    # TODO : lire les reviews ici

    # 5. Construction des tables
    print("\n---------- Table crées ---------\n")
    quartiers = transform_quartiers(rents_raw)
    loyers = transform_loyers(rents_raw)
    arrondissements = transform_arrondissements(quartiers)
    listing_snapshots = build_listing_snapshots(clean_listings)
    listings = build_listings(clean_listings)
    tables = {
        "arrondissements": arrondissements,
        "quartiers": quartiers,
        "loyers": loyers,
        "listings": listings,
        "listing_snapshots": listing_snapshots,
    }

    # 5. Contrôle des tables propres (point 2)
    check_tables(tables)

    return tables


# --------- TEST ---------
# Pour tester seul, depuis la racine du repo : python -m src.transform
if __name__ == "__main__":
    # Export des tables en CSV dans data/exports/ pour les vérifier
    export_tables(transform_all())
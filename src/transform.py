from pathlib import Path
import pandas as pd
import shapely

# fonctions de vérification écrites dans checks.py, lancées ici (import avec un point : src/ est un package)
from . import checks
from .checks import RAW_S3_DIR, list_files, choose_files, check_selection, check_tables

# --------- CONSTANTES ---------

## --------- CONSTANTES : DOSSIERS (pour les exports) ---------
# racine du projet 
ROOT = Path(__file__).resolve().parent.parent
# dossier des exports pour verifier à la main en local
EXPORTS_DIR = ROOT / "data" / "exports"

## --------- CONSTANTES : RENTS ---------
# Paris = 80 quartiers, 4 par arrondissement : quartiers 1-4 -> 1er, 5-8 -> 2e, etc.
NEIGHBORHOODS_PER_ARR = 4

# Valeur de la colonne meuble_txt pour un logement meublé
MEUBLE_TEXT = "meublé"

# Table quartiers
## les colonnes de la table quartiers
QUARTIERS_COLUMNS = ["id_quartier", "nom_quartier", "arrondissement", "code_grand_quartier",
                         "latitude", "longitude", "geo_shape"]

# Table loyers
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


# --------- 1. FONCTION VERIFIER LES FICHIERS POUR LE TRANSFORM ---------
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

# --------- 2. TRANSFORMATION RENTS (RAW) ---------
## --------- FONCTION LIRE FICHIER : RENTS ---------
## MODIF POST S3: modifier read_parquet par read_csv

def read_rents(file):
    """Lit le fichier des loyers (parquet) depuis raw_s3 --> dataframe"""
    rents = pd.read_parquet(RAW_S3_DIR / file)
    print(f"rents raw: {file} -> {rents.shape}")
    return rents

## --------- FONCTION: CREATION TABLE QUARTIERS ---------
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
    print(quartiers.info)
    return quartiers

## --------- FONCTION TABLE LOYERS ---------
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
    print(loyers.head(3))
    return loyers

# --------- FONCTION EXPORT DES TABLES ---------
def export_tables(tables):
    """Écrit chaque table en CSV dans data/exports/ pour les vérifier à la main"""
    # créer le dossier s'il n'existe pas encore
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # une table -> un fichier CSV (les anciens fichiers sont écrasés)
    for name, table in tables.items():
        path = EXPORTS_DIR / f"{name}.csv"
        table.to_csv(path, index=False)
        print(f"export : {name} {table.shape} -> {path.relative_to(ROOT)}")

# --------- PIPELINE ---------
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

    # TODO : lire les listings et les reviews ici
    # (leur contenu est déjà vérifié avant la mise en S3 : pas de contrôle du brut ici)

    # 4. Construction des tables
    print("\n---------- Table crées ---------\n")
    quartiers = transform_quartiers(rents_raw)
    loyers = transform_loyers(rents_raw)
    tables = {
        "quartiers": quartiers,
        "loyers": loyers,
    }

    # 5. Contrôle des tables propres (point 2)
    check_tables(tables)

    return tables


# --------- TEST ---------
# Pour tester seul, depuis la racine du repo : python -m src.transform
if __name__ == "__main__":
    # Export des tables en CSV dans data/exports/ pour les vérifier
    export_tables(transform_all())
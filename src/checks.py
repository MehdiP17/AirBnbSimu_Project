# checks.py : les fonctions de contrôle du pipeline.
# Elles sont ÉCRITES ici, mais LANCÉES dans transform.py et load.py.


import re                   
from pathlib import Path     
import pandas as pd          


# --------- CONSTANTES POUR LE CHECK ---------
## MODIF POST S3: modifier les directories pour récuperer les fichiers dans S3 pas en local

ROOT = Path(__file__).resolve().parent.parent     # racine du projet (ce fichier est dans src/)
RAW_S3_DIR = ROOT / "data" / "raw_s3"             # directory en local

# On ne garde que les fichiers des années en cours: CURRENT_YEAR
# Et pour les listings : les fichiers trimestriels : REQUIRED_MONTHS : 03 mars, 06 juin, 09 septembre, 12 decembre
CURRENT_YEAR = str(pd.Timestamp.today().year)   
REQUIRED_MONTHS = ["03", "06", "09", "12"]                

# La structure de nommage des differents types de fichiers attendus: 
## --------- MODIF POST S3: .parquet à modifier en .csv 
LISTINGS_PATTERN = r"inside-airbnb/paris/listings_(\d{4})-(\d{2})-\d{2}\.csv"   # listings
REVIEWS_PATTERN = r"inside-airbnb/paris/reviews_\d{4}-\d{2}-\d{2}\.csv"         # reviews_AAAA-MM-JJ.csv
RENT_PATTERN = r"encadrement-loyers/paris/encadrement_loyers.*\.parquet"     # encadrement_loyers

# compteur des WARNING pre-transform
WARNING_COUNT = 0                                 


# --------- FONCTION AFFICHAGE DES LOGS ---------
# Message d'affichage : uniquement pour afficher les messages et compter les warnings lors des checks pre et post transformation.

# on affiche et on continue
def log_ok(message):
    print(f"Check OK: {message}")             

# un warning ajoute +1 au compteur, affiche, continue les checks
def log_warning(message):
    global WARNING_COUNT                      
    WARNING_COUNT += 1                        
    print(f"WARNING {message}")            

# un error bloque la pipeline 
## ex: il n'y a ni de fichier loyer ni de fichier reviews
def log_error(message):
    raise ValueError(message)                 


# --------- FONCTION SELECTION DES FICHIERS POUR TRANSFORMATION ---------
## MODIF POST S3: peut etre il faudra changer des choses sur les chemins ou nommage de fichier à verifier

## --------- FONCTION LISTER LES FICHIERS DE S3 ---------
def list_files(directory=RAW_S3_DIR):
    """
    Liste tous les fichiers dans le bucket S3, triés par nom
    ex. "inside-airbnb/paris/listings_2026-03-21.csv".
    """
    files = []                                                         
    for path in Path(directory).rglob("*"):                           # tout le contenu du dossier et de ses sous-dossiers
        if path.is_file() and not path.name.startswith("."):      # ne prendre que les fichiers, pas les fichiers cachés (.)
            files.append(path.relative_to(directory).as_posix())       # ajouter le nom du chemin à partir de raw_s3 dans la liste files
    return sorted(files)                                               

## --------- FONCTION SELECTIONNER LES FICHIERS POUR TRANSFORM ---------
def select_files(files):
    """
    Choisit les fichiers qui correspondent à la nomenclature pour chaque type : LISTINGS_PATTERN, REVIEWS_PATTERN, RENTS_PATTERN

    Pour la selection on garde uniquement les fichiers: 
    listings: année en cours & mois : 03, 06, 09, 12
    reviews: le plus récent
    rents: les plus récent

    Renvoie {"listings": {extract: file}, "reviews": file ou None, "rents": file ou None}.
    """
    # les fichiers qui seront selectionnées pour le transform
    selected_files = {
        "listings": {}, 
        "reviews": None, 
        "rents": None
        }        
    
    for file in sorted(files):    
        # est-ce que la nomenclature du fichier est un listing
        match = re.fullmatch(LISTINGS_PATTERN, file)     
        # if listing de l'année en cours et un des REQUIRED_MONTHS alors on l'ajoute au dict des selected_files["listings"]                 
        if match:                                                        
            year = match.group(1)
            month = match.group(2)                
            if year == CURRENT_YEAR and month in REQUIRED_MONTHS:        
                selected_files["listings"][f"{year}-{month}"] = file            
            else:                                                        
                print(f"ignoré : {file} (pas un relevé trimestriel de {CURRENT_YEAR})")
        # est-ce que la nomenclature du fichier est un reviews
        elif re.fullmatch(REVIEWS_PATTERN, file):                         
            selected_files["reviews"] = file 
        # est-ce que la nomenclature du fichier est un rents                                               
        elif re.fullmatch(RENT_PATTERN, file):                          
            selected_files["rents"] = file
        # si ne correspond à aucun on signale
        else:                                                            
            print(f"ignoré : {file} (nom non reconnu)")
    
    # on affiche ce qui a été choisi
    for extract, file in selected_files["listings"].items():                     
        print(f"listings choisi : {file} -> relevé du {extract}")
    print(f"reviews choisi : {selected_files['reviews']}")
    print(f"rents choisi : {selected_files['rents']}")
    return selected_files

## --------- FONCTION LISTER LES FICHIERS DE S3 ---------
def selection_check(files):
    """
    Fonction pour vérifier que tous les fichiers nécessaires sont là pour le transform:
        listings: warning s'il manque un fichier trimestriel, error s'il n'y a aucun fichier
        reviews: error s'il n'y a pas de fichier
        rents: error s'il n'y a pas de fichier
    """
    # Verifier quels fichiers listings on a, afficher un warning si un fichier trimestriel manque
    for month in REQUIRED_MONTHS:                                           
        extract = f"{CURRENT_YEAR}-{month}"                              
        if extract in files["listings"]:
            log_ok(f"sélection : relevé {extract} trouvé")
        else:
            log_warning(f"sélection : relevé {extract} introuvable, à vérifier")
    # aucun relevé du tout: error
    if not files["listings"]:                                         
        log_error("sélection : aucun relevé listings trouvé")
    # Verifier qu'il y a un fichier reviews et un rents
    for source in ["reviews", "rents"]:                                 
        if files[source] is None:
            log_error(f"sélection : fichier {source} introuvable")
        else:
            log_ok(f"sélection : {source} trouvé ({files[source]})")


# Pour tester

if __name__ == "__main__": # seulement si on lance : python src/checks.py
    fichiers = select_files(list_files())
    selection_check(fichiers)

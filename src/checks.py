# checks.py : les fonctions de contrôle du pipeline.
# Elles sont ÉCRITES ici, mais LANCÉES dans transform.py et load.py (et summary() dans etl.py).
# Ce fichier ne se lance jamais seul.


import re                   
import pandas as pd          


# --------- CONSTANTES POUR LE CHECK ---------  

# On ne garde que les fichiers des années en cours: CURRENT_YEAR
# Et pour les listings : les fichiers trimestriels : REQUIRED_MONTHS : 03 mars, 06 juin, 09 septembre, 12 decembre
CURRENT_YEAR = str(pd.Timestamp.today().year)   
REQUIRED_MONTHS = ["03", "06", "09", "12"]                

# La structure de nommage des differents types de fichiers attendus: 
LISTINGS_PATTERN = r"inside-airbnb/paris/listings_(\d{4})-(\d{2})-\d{2}\.csv"   # listings
REVIEWS_PATTERN = r"inside-airbnb/paris/reviews_\d{4}-\d{2}-\d{2}\.csv"         # reviews_AAAA-MM-JJ.csv
RENT_PATTERN = r"encadrement-loyers/paris/encadrement-des-loyers_\d{4}-\d{2}-\d{2}\.csv"

# compteur des WARNING pre-transform
WARNING_COUNT = 0                                 


# --------- FONCTION AFFICHAGE DES LOGS ---------
# Message d'affichage : uniquement pour afficher les messages et compter les warnings lors des checks pre et post transformation.

# on affiche et on continue
def log_ok(message):
    print(f"CHECK OK: {message}")             

# un warning ajoute +1 au compteur, affiche, continue les checks
def log_warning(message):
    global WARNING_COUNT                      
    WARNING_COUNT += 1                        
    print(f"WARNING: {message}")            

# un error bloque la pipeline 
## ex: il n'y a ni de fichier loyer ni de fichier reviews
def log_error(message):
    raise ValueError(message)                 


# --------- 1. FONCTION VERIFICATION FICHIERS PRE-TRANSFORMATION ---------

## --------- FONCTION LISTER LES FICHIERS DE S3 ---------
def list_files(s3, bucket):
    """
    Liste tous les fichiers du bucket S3, triés par nom
    ex. "inside-airbnb/paris/listings_2026-03-21.csv".
    """
    # demander à S3 la liste de tout le bucket 
    response = s3.list_objects_v2(Bucket=bucket)

    # garder seulement les noms des fichiers, pas les "dossiers" (leur nom finit par /)
    files = []
    for obj in response.get("Contents", []):
        if not obj["Key"].endswith("/"):
            files.append(obj["Key"])
    return sorted(files)                                            

## --------- FONCTION SELECTIONNER LES FICHIERS POUR TRANSFORM ---------
def choose_files(files):
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
    
    for file in files:
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
            print(f"Fichier ignoré : {file} (nom non reconnu)")

    # pas d'affichage des fichiers choisis ici : le récap de transform.py s'en charge
    return selected_files

## --------- FONCTION VERIFIER PRESENCE DES FICHIERS POUR LE TRANSFORM ---------
def check_selection(files):
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
            log_ok(f"listings {extract} trouvé")
        else:
            log_warning(f"listings {extract} introuvable, à vérifier")
    # aucun relevé du tout: error
    if not files["listings"]:                                         
        log_error("aucun listings trouvé")
    # Verifier qu'il y a un fichier reviews et un rents
    for source in ["reviews", "rents"]:                                 
        if files[source] is None:
            log_error(f"fichier {source} introuvable")
        else:
            log_ok(f"{source} trouvé ({files[source]})")


# --------- 2. CONTRÔLE DES TABLES PROPRES (point 2, lancé à la fin de transform_all()) ---------
def check_tables(tables):
    """
    Vérifie les tables propres : clés uniques, vides, plages de valeurs, clés étrangères.
    TODO : à écrire.
    """
    print("check_tables() : à écrire")


# --------- 3. CONTRÔLE APRÈS CHARGEMENT (point 3, lancé dans load.py) ---------
def check_db_counts(engine, tables):
    """
    Compare le nombre de lignes de chaque table dans Supabase à celui du DataFrame.
    TODO : à écrire.
    """
    print("check_db_counts() : à écrire")


# --------- 4. BILAN (lancé à la fin de etl.py) ---------
# si on arrive ici, aucune erreur n'a arrêté le pipeline : 0 erreur
def summary():
    print(f"Terminé : 0 erreur, {WARNING_COUNT} attention(s)")

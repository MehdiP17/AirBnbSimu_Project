# Orchestration de toute la pipeline ETL 
## Du chargement dans S3 --> transformation des tables raw --> chargement dans Supabase
# Il enchaîne extract -> transform -> load, puis affiche le bilan des contrôles.
# Pour lancer: depuis la racine du repo : python -m src.etl

from dotenv import load_dotenv

from .extract import extract_all
from .transform import transform_all, export_tables
from .load import load_all
from .checks import summary


# --------- MODE TEST ---------
# True = test à blanc : saute l'ecriture dans Supabase,
# les tables sont exportées en CSV dans data/exports/ pour les vérifier
# False = vrai lancement du pipeline

DRY_RUN = True

def etl_pipeline():
    """
    Lance tout le pipeline ETL: extract dans S3, Transform --> Load : Supabase
    """

    # 1. Lire les secrets du fichier .env (S3, Supabase) : une seule fois, ici
    load_dotenv()
    # 2. Extract : sites web -> S3 (fichiers bruts, aucun nettoyage)
    print("\n--------- EXTRACT ---------\n")
    if DRY_RUN:
            print("DRY_RUN : extract sauté (rien n'est écrit dans S3)")
    else:
        extract_all()
    # 3. Transform : S3 -> dict des tables propres et vérifiées
    print("\n--------- TRANSFORM ---------\n")
    tables = transform_all()
    # 4. Load : tables -> Supabase : si DRY RUN--> export CSV à la place du chargement
    print("\n--------- LOAD ---------\n")
    if DRY_RUN:
        print("DRY_RUN : load sauté (rien n'est écrit dans Supabase), export CSV à la place")
        export_tables(tables)
    else:
        load_all(tables)
    # 5. Bilan : « Terminé : 0 erreur, N attention(s) »
    print("\n--------- BILAN ---------\n")
    summary()


if __name__ == "__main__":
    etl_pipeline()

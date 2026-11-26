import checks
from checks import list_files, select_files, selection_check

# --------- FONCTION VERIFIER LES FICHIERS POUR LE TRANSFORM ---------
## Utilise les fonctions du checks.py pre-transformation
def get_files():
    """
    Récupère les noms des fichiers à transformer grâce aux fonctions de checks.py.
    Renvoie {"listings": {extract: file}, "reviews": file, "rents": file}.
    """
    # lister tous les fichiers bruts puis garder ceux qui nous intéressent
    all_files = list_files()
    files = select_files(all_files)

    # vérifier qu'il ne manque rien (bloque la pipeline si un fichier obligatoire manque)
    selection_check(files)

    return files

# --------- TEST ---------
# Pour tester : python3 src/transform.py
if __name__ == "__main__":
    # 1. choisir les fichiers et lancer le check
    files = get_files()

    # 2. récap des fichiers retenus et du nombre de warnings
    # (checks.WARNING_COUNT et pas un import direct, sinon on garderait la valeur 0 du départ)
    print("\n--------- RECAP FICHIERS À TRANSFORMER ---------")
    print(f"listings : {len(files['listings'])} relevé(s) --> {list(files['listings'])}")
    print(f"reviews  : {files['reviews']}")
    print(f"rents    : {files['rents']}")
    print(f"warnings : {checks.WARNING_COUNT}")

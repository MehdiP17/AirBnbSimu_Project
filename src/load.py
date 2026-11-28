"""Télécharger les jeux de données transformés et les envoyer dans Supabase."""


from dotenv import load_dotenv
import os
from supabase import create_client
import pandas as pd



#---------- Initialisation de la connexion à supabase et tests préalables au chargement ----------


def test_connexion_tables_supabase(url, key, liste_tables):
    """Teste l'URL, la clé et l'existence des tables dans la base de données supabase"""

    try:
        supabase = create_client(url, key)
        for table in liste_tables:
            supabase.table(table).select("*").limit(1).execute()
        print("Connexion Supabase OK. Toutes les tables sont présentes dans la base de données.")
        return supabase
    except Exception as erreur:
        print(f"Erreur de connexion à Supabase: {erreur}")
    return None


def verification_correspondance_colonnes(supabase, tables_transformees, liste_tables):
    """A construire avec sqlalchemy inspect mais vide pour premier test etl de bout en bout"""
    print("pas de vérification de correspondance de colonnes pour l'instant")
    return supabase


# ---------- Chargement des données ----------


def suppression_contenu_tables(supabase, liste_tables):
    """Supprime le contenu des tables - l'ordre de suppression est à revoir avec les clés"""
    
    for table in liste_tables:
        
        reponse = supabase.table(table).select("*").limit(1).execute()

        if not reponse.data:
            print(f"La table {table} est déjà vide.")
            continue  

        colonne_avec_id = next(nom for nom in reponse.data[0] if "id" in nom)
        supabase.table(table).delete().or_(
            f"{colonne_avec_id}.is.null,{colonne_avec_id}.not.is.null"
        ).execute()

    return supabase


def charger_supabase(supabase, tables_transformees):
    """A construire mais imprime les tables transformées pour premier test etl de bout en bout"""
    print(tables_transformees)
    return tables_transformees


# ---------- Programme principal ----------


def load_all(tables_transformees):

    load_dotenv()
    url = os.getenv('SUPABASE_DB_URL')
    key = os.getenv('SUPABASE_KEY')
    liste_tables=["amenities","districts", "listing_amenities", "listing_snapshots", "listings", "rent", "months", "neighborhoods", "reviews"]
    supabase = test_connexion_tables_supabase(url, key, liste_tables)
    if not supabase:
        return
    if not verification_correspondance_colonnes(supabase, tables_transformees, liste_tables):
        return
    suppression_contenu_tables(supabase, liste_tables)
    charger_supabase(supabase, tables_transformees)


if __name__ == "__main__":
    # Pour lancer load seul python -m src.load

    from .transform import transform_all
    load_dotenv()
    load_all(transform_all())
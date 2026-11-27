"""Télécharger les données d'encadrement des loyers et d'inside airbnb et les déposer dans un bucket sur S3."""

import os
import boto3
import pandas as pd
from dotenv import load_dotenv
from datetime import date, timedelta
import requests
from botocore.exceptions import ClientError
   


#---------- Initialisation de la connexion à s3 ----------


def connexion_s3():
    """Connexion à s3"""

    s3 = boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION_NAME"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    return s3


#---------- Tests préalables à l'extraction et au chargement ----------


def mise_a_jour_necessaire(s3):
    """Evalue la nécessité de faire une MAJ (si dernière MAJ a plus de 30 jours ou si le bucket est vide)"""
    
    try:
        infos_fichier_temoin = s3.head_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key="_derniere_maj_reussie.txt")

    except ClientError:
        print("Aucun chargement détecté: les données sont à importer.")
        return True
    
    derniere_maj = infos_fichier_temoin["LastModified"].date()

    if derniere_maj > date.today() - timedelta(days=30):
        print(f"Dernière MAJ des données le {derniere_maj} (moins de 30 jours) : pas de MAJ à effectuer.")
        return False

    print(f"Dernière MAJ des données le {derniere_maj} : MAJ nécessaire.")
    return True


def test_reponse_url(url):
    """Test de réponse de l'url"""

    try:
        reponse = requests.get(url, timeout=60)
    except requests.RequestException:
        return None
    if reponse.status_code != 200:
        return None
    return reponse.content


def verification_contenu_dataset(df, nom_df):
    """Présence des colonnes nécessaires à l'exploitation et contenu non vide"""

    if nom_df == "df_loyers":
        colonnes_requises = ["Année", "Numéro du quartier", "Nombre de pièces principales", "Epoque de construction", "Type de location", "Loyers de référence"]
    elif nom_df == "df_listings":
        colonnes_requises = ["id", "price", "room_type", "neighbourhood_cleansed", "last_scraped",
        "price_quote_checkin_date", "price_quote_checkout_date", "bathrooms_text"]
    elif nom_df == "df_reviews":
        colonnes_requises = ["listing_id", "date"]
        
    if not set(colonnes_requises).issubset(df.columns):
        return None

    if df[colonnes_requises].isna().all().any():
        return None

    return True


def verification_presence_dataset_dans_bucket(s3, s3_key):
    """Teste si le dataset a déjà été importé"""

    try:
        s3.head_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=s3_key)
        return True
    
    except ClientError:
        return False

    
# ---------- Extraction des données ----------


def encadrement_des_loyers(s3):
    """Récupère les données d'encadrement des loyers et les envoie sur S3."""

    url = "https://tabular-api.data.gouv.fr/api/resources/d72d537a-2f7f-40af-bf1a-289ee25d5ae9/data/csv/"

    if not test_reponse_url(url):
        raise Exception("Impossible d'accéder aux données sur l'encadrement des loyers.")
    
    s3_key = f"encadrement-loyers/paris/encadrement-des-loyers_{date.today()}.csv"
    
    df_loyers = pd.read_csv(url)

    if not verification_contenu_dataset(df_loyers,"df_loyers"):
        raise Exception("Les données sur l'encadrement des loyers sont incomplètes et ne permettent pas leur exploitation.")

    chargement_dans_bucket(s3, df_loyers, s3_key)



def inside_airbnb_listings(s3):
    """Récupère les fichiers listings csv d'inside airbnb et les envoie sur S3."""   

    end = date.today()
    start = end - timedelta(days=365)
    calendrier = pd.date_range(start, end, freq="D")
    nb_fichiers_valides = 0

    for day in calendrier[::-1]:
        d = day.date()
        url = f"https://data.insideairbnb.com/france/ile-de-france/paris/{d}/data/listings.csv.gz"
        s3_key = f"inside-airbnb/paris/listings_{d}.csv"

        if verification_presence_dataset_dans_bucket(s3, s3_key):
            print(f"Le dataset suivant est déjà sur S3 : {s3_key}")
            nb_fichiers_valides += 1
            return

        if not test_reponse_url(url):
            continue

        df_listings = pd.read_csv(url)

        if not verification_contenu_dataset(df_listings,"df_listings"):
            print(f"Les données du fichier listings du {d} sont incomplètes et ne permettent pas leur exploitation.")
            continue
            
        chargement_dans_bucket(s3, df_listings, s3_key)
        nb_fichiers_valides += 1
    
    if nb_fichiers_valides == 0:
        raise Exception("Aucun fichier listings valide trouvé sur les 365 derniers jours.")



def inside_airbnb_reviews(s3):
    """Récupère le fichier reviews csv d'inside airbnb le plus récent et les envoie sur S3."""
    
    end = date.today()
    start = end - timedelta(days=365)
    calendrier = pd.date_range(start, end, freq="D")

    for day in calendrier[::-1]:
        d = day.date()
        url = f"https://data.insideairbnb.com/france/ile-de-france/paris/{d}/visualisations/reviews.csv"
        s3_key = f"inside-airbnb/paris/reviews_{d}.csv"

        if verification_presence_dataset_dans_bucket(s3, s3_key):
            print(f"Le dataset suivant est déjà sur S3 : {s3_key}")
            return

        if not test_reponse_url(url):
            continue

        df_reviews = pd.read_csv(url)

        if not verification_contenu_dataset(df_reviews,"df_reviews"):
            print(f"Les données du fichier reviews du {d} sont incomplètes et ne permettent pas leur exploitation.")
            continue
       
        chargement_dans_bucket(s3, df_reviews, s3_key)
        return

    raise Exception("Aucun fichier reviews valide trouvé sur les 365 derniers jours.")


# ---------- Chargement dans bucket et génération du fichier témoin de la MAJ ----------


def chargement_dans_bucket(s3, df, s3_key):
    """Envoie le DataFrame dans le bucket S3."""

    bucket = os.environ["AWS_BUCKET_NAME"]
    s3.put_object(Bucket=bucket, Key=s3_key, Body=df.to_csv(index=False).encode("utf-8"))
    print(f"Fichier envoyé sur s3://{bucket}/{s3_key}")
    return


def fichier_temoin(s3):
    """Dépose le contenu (en octets) dans le bucket, tel quel."""
    
    bucket = os.environ["AWS_BUCKET_NAME"]
    s3.put_object(
        Bucket=bucket,
        Key="_derniere_maj_reussie.txt",
        Body=date.today().isoformat().encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    print(f"Fichier témoin mis à jour sur s3://{bucket}")
    return


# ---------- Programme principal ----------


def extract_all():

    load_dotenv()
    s3 = connexion_s3()
    if not mise_a_jour_necessaire(s3):
        return
    encadrement_des_loyers(s3)
    inside_airbnb_listings(s3)
    inside_airbnb_reviews(s3)
    fichier_temoin(s3)


if __name__ == "__main__":
    extract_all()

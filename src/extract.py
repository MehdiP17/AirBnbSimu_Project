"""Télécharge les données d'encadrement des loyers et d'inside airbnb et les dépose dans un bucket sur S3."""

import os
import boto3
import pandas as pd
from dotenv import load_dotenv
from datetime import date, timedelta
import requests
   

def encadrement_des_loyers():
    """Récupère les données d'encadrement des loyers et les envoie sur S3."""

    url = "https://tabular-api.data.gouv.fr/api/resources/d72d537a-2f7f-40af-bf1a-289ee25d5ae9/data/csv/"
    s3_key = f"encadrement-loyers/paris/encadrement-des-loyers_{date.today()}.csv"
    
    df = pd.read_csv(url)

    load_to_bucket(df, s3_key)



def inside_airbnb_listings():
    """Récupère les fichiers listings csv d'inside airbnb et les envoie sur S3."""   

    end = date.today()
    start = end - timedelta(days=365)
    calendrier = pd.date_range(start, end, freq="D")

    for day in calendrier:
        d = day.date()
        url = f"https://data.insideairbnb.com/france/ile-de-france/paris/{d}/data/listings.csv.gz"
        
        try:
            if requests.head(url, timeout=10).status_code != 200:
                continue
        except requests.RequestException:
            continue

        df = pd.read_csv(url)

        if "price" in df.columns and df["price"].notna().any():
            s3_key = f"inside-airbnb/paris/listings_{d}.csv"
            
            load_to_bucket(df, s3_key)



def inside_airbnb_reviews():
    """Récupère le fichier reviews csv d'inside airbnb le plus récent et les envoie sur S3."""

    today = date.today()

    for i in range(365):
        d = today - timedelta(days=i)
        url = f"https://data.insideairbnb.com/france/ile-de-france/paris/{d}/visualisations/reviews.csv"

        try:
            if requests.head(url, timeout=10).status_code != 200:
                continue
        except requests.RequestException:
            continue

        df = pd.read_csv(url)
        s3_key = f"inside-airbnb/paris/reviews_{d}.csv"
        
        load_to_bucket(df, s3_key)
        return df, s3_key


def load_to_bucket(df, s3_key):
    """Envoie le DataFrame dans le bucket S3."""

    # Se connecter à S3
    s3 = boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION_NAME"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    # Envoyer les données dans le bucket
    bucket = os.environ["AWS_BUCKET_NAME"]
    s3.put_object(Bucket=bucket, Key=s3_key, Body=df.to_csv(index=False).encode("utf-8"))
    print(f"Fichier envoyé sur s3://{bucket}/{s3_key}")


def main():
    load_dotenv(override=True)
    encadrement_des_loyers()
    inside_airbnb_listings()
    inside_airbnb_reviews()



if __name__ == "__main__":
    main()

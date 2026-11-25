"""Télécharge les données d'encadrement des loyers (data.gouv.fr) et les dépose dans un bucket sur S3."""

import os
import boto3
import pandas as pd
from dotenv import load_dotenv
from datetime import date

URL = "https://tabular-api.data.gouv.fr/api/resources/d72d537a-2f7f-40af-bf1a-289ee25d5ae9/data/csv/"
S3_KEY = f"encadrement-loyers/encadrement-des-loyers_{date.today()}.csv"


def main():
    load_dotenv(override=True)

    # Récupérer les données via l'API
    df = pd.read_csv(URL)
    print(f"{len(df)} lignes téléchargées")

    # Se connecter à S3
    s3 = boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION_NAME"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    # Envoyer les données dans le bucket
    bucket = os.environ["AWS_BUCKET_NAME"]
    s3.put_object(Bucket=bucket, Key=S3_KEY, Body=df.to_csv(index=False).encode("utf-8"))
    print(f"Fichier envoyé sur s3://{bucket}/{S3_KEY}")


if __name__ == "__main__":
    main()

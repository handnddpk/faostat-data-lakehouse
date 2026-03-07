from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp
import requests
import sys

def download_faostat_data(dataset_code, output_path):
    api_url = f"https://bulks-faostat.fao.org/production/{dataset_code}_E_All_Data_(Normalized).zip"
    print(f"Downloading {dataset_code} from {api_url}...")
    response = requests.get(api_url)
    if response.status_code == 200:
        zip_path = f"{output_path}/{dataset_code}.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {dataset_code} data to {zip_path}")
        return zip_path
    else:
        print(f"Failed to download data for {dataset_code}. Status code: {response.status_code}")
        return None

def main():
    dataset_code = sys.argv[1] if len(sys.argv) > 1 else 'Production_Crops_Livestock'

    spark = SparkSession.builder \
        .appName("FAOSTAT Data Ingestion") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.lakehouse.catalog-impl", "org.apache.iceberg.jdbc.JdbcCatalog") \
        .config("spark.sql.catalog.lakehouse.uri", "jdbc:postgresql://postgres:5432/metastore") \
        .config("spark.sql.catalog.lakehouse.jdbc.user", "admin") \
        .config("spark.sql.catalog.lakehouse.jdbc.password", "password") \
        .config("spark.sql.catalog.lakehouse.warehouse", "s3a://lakehouse/warehouse") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

    download_path = "/opt/spark/data/raw"
    zip_file = download_faostat_data(dataset_code, download_path)

    if zip_file:
        import zipfile
        import os

        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(download_path)

        csv_file = None
        for file in os.listdir(download_path):
            if file.endswith('.csv') and dataset_code in file and 'All_Data' in file:
                csv_file = os.path.join(download_path, file)
                break

        if csv_file:
            df = spark.read.option("header", "true").option("inferSchema", "true").csv(csv_file)
            df = df.withColumn("ingestion_time", current_timestamp())

            spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.bronze")
            code = 'qcl' if 'Production' in dataset_code else 'tcl'
            table_name = f"lakehouse.bronze.faostat_{code}_raw"

            df.write.format("iceberg").mode("overwrite").saveAsTable(table_name)
            print(f"Data for {dataset_code} ingested into table {table_name}")
            print(f"Total records: {df.count()}")
        else:
            print(f"No CSV file found for {dataset_code} in {download_path}")
    else:
        raise RuntimeError(f"Download failed for {dataset_code}")

    spark.stop()

if __name__ == "__main__":
    main()

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp
import requests
import sys

def download_faostat_data(dataset_code, output_path):
    api_url = f"https://bulks-faostat.fao.org/production/{dataset_code}_E_All_Data_(Normalized).zip"
    response = requests.get(api_url)
    if response.status_code == 200:
        zip_path= f"{output_path}/{dataset_code}.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {dataset_code} data to {zip_path}")
    else:
        print(f"Failed to download data for {dataset_code}. Status code: {response.status_code}")
        
def main():
    dataset_code = sys.argv[1] if len(sys.argv) > 1 else 'Production_Crops_Livestock'
    
    spark = SparkSession.builder \
        .appName("FAOSTAT Data Ingestion") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.lakehouse.type", "jdbc") \
        .config("spark.sql.catalog.lakehouse.uri", "jdbc:postgresql://postgres:5432/metastore") \
        .config("spark.sql.catalog.lakehouse.user", "admin") \
        .config("spark.sql.catalog.lakehouse.password", "password") \
        .config("spark.sql.catalog.lakehouse.warehouse", "s3a://lakehouse/warehouse") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.jars", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,"
                "org.apache.hadoop:hadoop-aws:3.3.4,"
                "org.postgresql:postgresql:42.6.0,"
                "com.amazonaws:aws-java-sdk-bundle:1.12.262") \
        .getOrCreate()
        
    download_path = "/opt/spark/data/raw"
    zip_file = download_faostat_data(dataset_code, download_path)
    
    if zip_file:
        # Unzip and process the data
        import zipfile
        import os
        
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(download_path)
            
        csv_file = None
        for file in os.listdir(download_path):
            if file.endswith('.csv') and dataset_code in file:
                csv_file = os.path.join(download_path, file)
                break
            
        if csv_file:
            df = spark.read.option("header", "true").option("inferSchema", "true").csv(csv_file)
            df = df.withColumn("ingestion_time", current_timestamp())
            
            spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.bronze")
            code = 'qcl' if 'Production' in dataset_code else 'tcl'
            table_name = f"lakehouse.bronze.faostat_{code}"
            
            df.write.format("iceberg").mode("overwrite").saveAsTable(table_name)
            print(f"Data for {dataset_code} ingested into table {table_name}")
            
    spark.stop()
    
if __name__ == "__main__":
    main()
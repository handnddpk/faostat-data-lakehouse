from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, sum, desc

def main():

    spark = SparkSession.builder \
        .appName("Transform Production Data") \
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

    raw_df = spark.read.table("lakehouse.bronze.faostat_qcl_raw")
    production_df = raw_df.filter(col("Element") == "Production") \
        .select(
            col("Area").alias("country"),
            col("Item").alias("crop"),
            col("Year").cast("int").alias("year"),
            col("Value").cast("double").alias("production_tonnes"),
            col("Unit").alias("unit")
        ).filter(col("production_tonnes").isNotNull())

    spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.silver")

    production_df.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.silver.crop_production")
    
    yearly_global = production_df.groupBy("year", "crop").agg(sum("production_tonnes").alias("global_production"))
    top_crops = production_df.groupBy("crop").agg(sum("production_tonnes").alias("global_production")) \
        .orderBy(col("global_production").desc()) \
        .limit(20)
        
    spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.gold")
    yearly_global.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.gold.yearly_crop_production")
    top_crops.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.gold.top_crops")

    print("Production data transformed successfully. Data written to silver and gold tables.")

    spark.stop()

if __name__ == "__main__":
    main()

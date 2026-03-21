from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, sum, desc, round, lag
from pyspark.sql.window import Window

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

    production_df = spark.read.table("lakehouse.silver.crop_production")
    trade_df = spark.read.table("lakehouse.silver.trade_data")
    
    cereals = ["Wheat", "Rice", "Maize (corn)", "Barley", "Sorghum"]
    
    cereal_production = production_df.filter(col("crop").isin(cereals)) \
        .groupBy("country", "year") \
        .agg(sum("production_tonnes").alias("total_cereal_production"))
        
    cereal_imports = trade_df.filter(col("product").isin(cereals) & (col("trade_type") == "Import quantity")) \
        .groupBy("country", "year") \
        .agg(sum("trade_value").alias("total_imports"))
        
    food_security = cereal_production.join(cereal_imports, ["country", "year"], "left").fillna(0, ["total_imports"])
    food_security = food_security.withColumn(
        "self_sufficiency_ratio",
        round(col("total_cereal_production") / (col("total_cereal_production") + col("total_imports")), 2)
    )

    window = Window.partitionBy("country").orderBy("year")
    food_security = food_security.withColumn(
        "production_previous_year",
        lag("total_cereal_production").over(window)
    )

    food_security = food_security.withColumn(
        "production_growth_rate",
        round((col("total_cereal_production") - col("production_previous_year")) / col("production_previous_year"), 2)
    )

    food_security.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.gold.food_security")
    
    print("Food security analysis completed successfully. Data written to gold.food_security table.")
    spark.stop()

if __name__ == "__main__":
    main()
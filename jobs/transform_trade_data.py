from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, sum, desc, when

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
        .config("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh") \
        .getOrCreate()

    raw_df = spark.read.table("lakehouse.bronze.faostat_tcl_raw")
    trade_df = raw_df.select(
        col("Area").alias("country"),
        col("Item").alias("product"),
        col("Year").cast("int").alias("year"),
        col("Value").cast("double").alias("trade_value"),
        col("Unit").alias("unit"),
        col("Element").alias("trade_type")
    ).filter(col("trade_value").isNotNull())

    spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.silver")

    trade_df.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.silver.trade_data")
    
    trade_balance_df = trade_df.groupBy("country", "year", "product") \
        .pivot("trade_type", ["Import quantity", "Export quantity"]) \
        .sum("trade_value") \
        .withColumnRenamed("Import quantity", "imports") \
        .withColumnRenamed("Export quantity", "exports") \
        .fillna(0) \
        .withColumn("trade_balance", col("exports") - col("imports")) \
        .withColumn("net_position", 
                    when(col("trade_balance") > 0, "Net Exporter")
                    .when(col("trade_balance") < 0, "Net Importer")
                    .otherwise("Balanced"))
    
    spark.sql("CREATE DATABASE IF NOT EXISTS lakehouse.gold")
    trade_balance_df.write.format("iceberg").mode("overwrite").saveAsTable("lakehouse.gold.trade_balance")

    print("Trade data transformed successfully. Data written to silver and gold tables.")

    spark.stop()

if __name__ == "__main__":
    main()

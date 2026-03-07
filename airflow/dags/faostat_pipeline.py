from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from datetime import datetime, timedelta
import requests

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'faostat_data_pipeline',
    default_args=default_args,
    description='A simple FAOSTAT data pipeline',
    schedule_interval=timedelta(days=1),
    catchup=False
)

def ingest_data(dataset_code, output_path):
    # import faostat
    # df = faostat.get_data_df(code)
    # df.to_csv(output_path, index=False)
    api_url = f"https://bulks-faostat.fao.org/production/{dataset_code}_E_All_Data_(Normalized).zip"
    response = requests.get(api_url)
    if response.status_code == 200:
        zip_path= f"{output_path}/{dataset_code}.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)

# ingest_production_data = PythonOperator(
#     task_id='ingest_production_data',
#     python_callable=ingest_data,
#     op_kwargs={'dataset_code': 'Production_Crops_Livestock', 'output_path': '/opt/airflow/data'},
#     dag=dag
# )

# ingest_trade_data = PythonOperator(
#     task_id='ingest_trade_data',
#     python_callable=ingest_data,
#     op_kwargs={'dataset_code': 'Trade_CropsLivestock', 'output_path': '/opt/airflow/data'},
#     dag=dag
# )

spark_conf = {
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "spark.sql.catalog.lakehouse": "org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.lakehouse.catalog-impl": "jdbc",
    "spark.sql.catalog.lakehouse.uri": "jdbc:postgresql://postgres:5432/metastore",
    "spark.sql.catalog.lakehouse.user": "admin",
    "spark.sql.catalog.lakehouse.password": "password",
    "spark.sql.catalog.lakehouse.warehouse": "s3a://lakehouse/warehouse",
    "spark.hadoop.fs.s3a.access.key": "minioadmin",
    "spark.hadoop.fs.s3a.secret.key": "minioadmin",
    "spark.hadoop.fs.s3a.endpoint": "http://minio:9000",
    "spark.hadoop.fs.s3a.path.style.access": "true",
    "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
}

spark_packages = (
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,"
    "org.apache.hadoop:hadoop-aws:3.3.4,"
    "org.postgresql:postgresql:42.6.0,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262"
)

ingest_production_data_by_spark = SparkSubmitOperator(
    task_id='ingest_production_data',
    application_args=['Production_Crops_Livestock'],
    conn_id='spark_default',
    conf=spark_conf,
    packages=spark_packages,
    application = '/opt/spark/jobs/ingest_faostat_data.py',
    dag=dag
)

ingest_trade_data_by_spark = SparkSubmitOperator(
    task_id='ingest_trade_data',
    application_args=['Trade_CropsLivestock'],
    conn_id='spark_default',
    conf=spark_conf,
    packages=spark_packages,
    application = '/opt/spark/jobs/ingest_faostat_data.py',
    dag=dag
)

[ingest_production_data_by_spark, ingest_trade_data_by_spark]
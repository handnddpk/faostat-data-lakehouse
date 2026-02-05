from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from datetime import datetime, timedelta
import requests

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.models import Variable
from airflow.operators.empty import EmptyOperator
import os

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

def download_data(dataset_code, output_path):
    # import faostat
    # df = faostat.get_data_df(code)
    # df.to_csv(output_path, index=False)
    output_path = f"{output_path}/raw"
    os.makedirs(output_path, exist_ok=True)
    api_url = f"https://bulks-faostat.fao.org/production/{dataset_code}_E_All_Data_(Normalized).zip"
    response = requests.get(api_url)
    if response.status_code == 200:
        zip_path= f"{output_path}/{dataset_code}.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)

download_production_data = PythonOperator(
    task_id='download_production_data',
    python_callable=download_data,
    op_kwargs={'dataset_code': 'Production_Crops_Livestock', 'output_path': '/data'},
    dag=dag
)

download_trade_data = PythonOperator(
    task_id='download_trade_data',
    python_callable=download_data,
    op_kwargs={'dataset_code': 'Trade_CropsLivestock', 'output_path': '/data'},
    dag=dag
)


# ingest_production_data_by_spark = BashOperator(
#     task_id='ingest_production_data_by_spark',
#     bash_command='spark-submit --master spark://spark:7077 /opt/spark/jobs/ingest_faostat_data.py Production_Crops_Livestock',
#     dag=dag
# )

# ingest_trade_data_by_spark = BashOperator(
#     task_id='ingest_trade_data_by_spark',
#     bash_command='spark-submit --master spark://spark:7077 /opt/spark/jobs/ingest_faostat_data.py Trade_CropsLivestock',
#     dag=dag
# )

spark_secret = Variable.get("spark_auth_secret") ## add variable in airflow web ui with value "secret"
submit_spark_ingest_production_data = SparkSubmitOperator(
    task_id='submit_spark_ingest_production_data',
    application='/opt/spark/jobs/ingest_faostat_data.py',
    conn_id='spark_default',
    packages='org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,org.apache.hadoop:hadoop-aws:3.3.4,org.postgresql:postgresql:42.6.0,com.amazonaws:aws-java-sdk-bundle:1.12.262',
    application_args=['Production_Crops_Livestock'],
    conf={'spark.master': 'spark://spark-master:7077',
            'spark.submit.deployMode': 'client',
            "spark.driver.host": "airflow-scheduler",
            "spark.driver.bindAddress": "0.0.0.0",
            "spark.driver.port": "7000",
            "spark.blockManager.port": "7001",
            "spark.authenticate": "true",
            "spark.authenticate.secret": spark_secret,
          },
    dag=dag
)

spark_submit_cmd = f"""
    spark-submit \
        --master spark://spark-master:7077 \
        --deploy-mode client \
        --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,org.apache.hadoop:hadoop-aws:3.3.4,org.postgresql:postgresql:42.6.0,com.amazonaws:aws-java-sdk-bundle:1.12.262 \
        --conf "spark.driver.bindAddress=0.0.0.0" \
        --conf "spark.driver.host=airflow-scheduler" \
        --conf "spark.driver.port=7000" \
        --conf "spark.blockManager.port=7001" \
        --conf "spark.authenticate=true" \
        --conf "spark.authenticate.secret={spark_secret}" \
        --name spark_ingest_trade_bash \
        /opt/spark/jobs/ingest_faostat_data.py \
        Trade_CropsLivestock
    """

submit_spark_ingest_trade_data_via_bash = BashOperator(
    task_id='submit_spark_ingest_trade_data_via_bash',
    bash_command=spark_submit_cmd,
    dag=dag
)

empty = EmptyOperator(task_id='empty',dag=dag)

# [ingest_production_data_by_spark, ingest_trade_data_by_spark]

[download_production_data, download_trade_data] >> empty
empty >> [submit_spark_ingest_production_data, submit_spark_ingest_trade_data_via_bash]


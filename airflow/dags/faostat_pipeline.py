from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from datetime import datetime, timedelta
import requests

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


ingest_production_data_by_spark = BashOperator(
    task_id='ingest_production_data',
    bash_command='spark-submit --master spark://spark:7077 /opt/spark/jobs/ingest_faostat_data.py Production_Crops_Livestock',
    dag=dag
)

ingest_trade_data_by_spark = BashOperator(
    task_id='ingest_trade_data',
    bash_command='spark-submit --master spark://spark:7077 /opt/spark/jobs/ingest_faostat_data.py Trade_CropsLivestock',
    dag=dag
)

[ingest_production_data_by_spark, ingest_trade_data_by_spark]
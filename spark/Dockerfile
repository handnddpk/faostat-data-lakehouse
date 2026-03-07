FROM apache/spark:3.5.0

USER root

RUN apt-get update && apt-get install -y python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    pyspark==3.5.0 \
    pandas==2.0.3 \
    boto3==1.34.10 \
    requests==2.31.0 \
    pyiceberg[pyarrow,sql-postgres]==0.5.1

USER spark
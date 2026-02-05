#!/bin/bash
set -e

# Initialize the database on first run
if [ "$1" = "webserver" ]; then
    airflow db init
    
    # Create admin user if it doesn't exist
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com \
        --password admin || echo "User already exists"
fi

# Execute the original command
exec airflow "$@"
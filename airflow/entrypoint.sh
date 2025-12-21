#!/bin/bash

set -e

# 1. Clean up stale PID files left over from previous crashes
rm -f "$AIRFLOW_HOME/airflow-webserver.pid"
rm -f "$AIRFLOW_HOME/airflow-scheduler.pid"

# Wait a moment for processes to fully terminate
sleep 2

# 3. Initialize/Upgrade DB
echo "Running DB Migrations..."
airflow db migrate

# 4. Create Admin User
echo "Ensuring Admin user exists..."
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin || echo "Admin user already exists or creation failed."

# 5. Create PostgreSQL Connection
echo "Creating PostgreSQL connection..."
# Delete existing connection if it exists (ignore if not found)
airflow connections delete 'postgres_default' 2>/dev/null || echo "No existing connection to delete."
airflow connections add 'postgres_default' \
    --conn-type 'postgres' \
    --conn-host "${POSTGRES_HOST:-postgres}" \
    --conn-port "${POSTGRES_PORT:-5432}" \
    --conn-login "${POSTGRES_USER:-rag_user}" \
    --conn-password "${POSTGRES_PASSWORD:-rag_password}" \
    --conn-schema "${POSTGRES_DB:-rag_db}"

# 6. Start the Webserver in the background
echo "Starting Airflow webserver..."
airflow webserver --port 8080 &

# 7. Start the Scheduler as the "foreground" process
# Using 'exec' ensures the scheduler receives OS signals directly
echo "Starting Airflow scheduler..."
exec airflow scheduler
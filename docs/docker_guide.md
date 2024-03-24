# Steps to set up local development environment of Airflow with Docker

## Method 1: Use Docker Airflow Image

### Create a Dockerfile

Create a Dockerfile in the root directory of the project.

```Dockerfile
# Use the official Airflow image
FROM apache/airflow:2.2.3

# Set the working directory
WORKDIR /usr/local/airflow

# Copy the requirements file
COPY requirements.txt .

# Install the requirements
RUN pip install --no-cache-dir -r requirements.txt
```

### Create a requirements file

Create a requirements file in the root directory of the project.

```txt
apache-airflow
```

### Build the Docker image

Build the Docker image using the following command:

```bash
docker build -t airflow-local .
```

### Run the Docker container

Run the Docker container using the following command:

```bash
docker run -d -p 8080:8080 airflow-local
```

### Access Airflow Webserver

Access the Airflow webserver using the following URL:

```bash
http://localhost:8080/
```

### Access the Airflow container

Access the Airflow container using the following command:

```bash
docker exec -it <container_id> /bin/bash
```

Replace `<container_id>` with the container ID of the Airflow container.

### Stop the Docker container

Stop the Docker container using the following command:

```bash
docker stop <container_id>
```

## Method 2: Use Docker Compose

### Pull Docker Compose file

Pull the Docker Compose file from the official Airflow repository using the following command:

```bash
curl -LfO 'https://airflow.apache.org/docs/apache-airflow/2.8.1/docker-compose.yaml'
```

### Initialize the Airflow environment

```bash
mkdir -p ./dags ./logs ./plugins ./config
echo -e "AIRFLOW_UID=$(id -u)" > .env
```

Make sure to:
- replace executor with `LocalExecutor`
- comment out redis service
- comment out the `celery worker`
- comment out `flower` service

### Initialize the database

```bash
docker compose up airflow-init
```

### Start Airflow

```bash
docker compose up
```

To remove the containers:

```bash
docker compose down --volumes --remove-orphans --rmi all
```

### Check Docker files

Check the Docker files using the following command:

```bash
docker ps
```

to get container id of webserver or scheduler

```bash
docker exec -it <container_id> bash
```

### Access Airflow Webserver

Access the Airflow webserver using the following URL:

```bash
http://localhost:8080/
```

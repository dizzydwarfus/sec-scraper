import subprocess
import os
import sys

# Define the Airflow version and Python version
AIRFLOW_VERSION = "2.8.2"


def install_airflow(airflow_version: str, python_version: str):
    constraint_url = f"https://raw.githubusercontent.com/apache/airflow/constraints-{airflow_version}/constraints-{python_version}.txt"
    print(
        f"Using constraint URL: {constraint_url}\n-----------------------------------"
    )
    # Install Apache Airflow
    subprocess.run(
        [
            "pip",
            "install",
            f"apache-airflow=={airflow_version}",
            "--constraint",
            constraint_url,
        ],
        check=True,
    )


if __name__ == "__main__":
    # Check if python is installed and the version is correct
    print("-----------------------------------")

    try:
        print("Checking if Python is installed...")
        subprocess.run(["python", "--version"], check=True)

        # store python version
        python_version = subprocess.run(
            ["python", "--version"], stdout=subprocess.PIPE
        ).stdout.decode("utf-8")
        print("-----------------------------------")
        python_version = ".".join(python_version.split(" ")[1].strip().split(".")[:2])
    except FileNotFoundError:
        print("Python is not installed. Please install Python and try again.\n")
        exit(1)

    # Define airflow version
    airflow_version = input(
        "Enter the version of Airflow to install (default: 2.8.2): "
    )

    if airflow_version:
        AIRFLOW_VERSION = airflow_version

    # Define the path to the requirements file
    requirements_path = input(
        "Enter the path to the requirements file [skip if only installing airflow]: "
    )

    # default requirements path to pwd if not provided
    if not requirements_path:
        requirements_path = os.getcwd() + "\\requirements.txt"
        print(
            f"Using default requirements file:\n {requirements_path}\n-----------------------------------"
        )

    # Check if the path to the requirements file is valid
    try:
        with open(requirements_path, "r") as f:
            pass
        print(
            f"Using requirements file: {requirements_path}\n-----------------------------------"
        )
    except FileNotFoundError:
        print(f"The file {requirements_path} does not exist.")
        exit(1)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--airflow-only":
            print(
                "Installing Apache Airflow only without requirements.txt...\n-----------------------------------"
            )
            # Install Apache Airflow
            install_airflow(AIRFLOW_VERSION, python_version)
            exit(0)
        elif sys.argv[1] == "--requirements-only":
            print(
                "Installing from requirements.txt only...\n-----------------------------------"
            )
            # Install dependencies
            subprocess.run(["pip", "install", "-r", requirements_path], check=True)
            exit(0)

    # Install dependencies
    subprocess.run(["pip", "install", "-r", requirements_path], check=True)

    # Install Apache Airflow
    install_airflow(AIRFLOW_VERSION, python_version)

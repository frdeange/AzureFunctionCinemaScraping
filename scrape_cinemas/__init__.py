import logging
import azure.functions as func
import requests
import json
import os
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import OrderedDict
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Inicializar variables de entorno
AZURE_COSMOSDB_URI = os.getenv("AZURE_COSMOSDB_URI")
AZURE_COSMOSDB_KEY = os.getenv("AZURE_COSMOSDB_KEY")
AZURE_COSMOSDB_DATABASE_NAME = os.getenv("AZURE_COSMOSDB_DATABASE_NAME")
AZURE_COSMOSDB_CONTAINER_NAME = os.getenv("AZURE_COSMOSDB_CONTAINER_NAME")
AZURE_COSMOSDB_PARTITION_KEY = os.getenv("AZURE_COSMOSDB_PARTITION_KEY")
WEB_SCRAPING_URL = os.getenv("WEB_SCRAPING_URL")

# Inicializar el cliente de CosmosDB
client = CosmosClient(AZURE_COSMOSDB_URI, AZURE_COSMOSDB_KEY)
database = client.create_database_if_not_exists(id=AZURE_COSMOSDB_DATABASE_NAME)
container = database.create_container_if_not_exists(
    id=AZURE_COSMOSDB_CONTAINER_NAME,
    partition_key=PartitionKey(path=AZURE_COSMOSDB_PARTITION_KEY),
    offer_throughput=400
)

# Función para realizar el scraping
def scrape_cinemas_data():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(WEB_SCRAPING_URL, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    cinemas_data = []
    cinemas = soup.find_all('div', class_='theater-card hred cf card-thumb-large')

    for cinema in cinemas:
        name_element = cinema.find('h3', class_='title')
        name = name_element.text.strip() if name_element else "Name not available"

        address_element = cinema.find('address', class_='address')
        address = address_element.text.strip() if address_element else "Address not available"

        screens_element = cinema.find('div', class_='screen-number')
        screens = screens_element.text.strip() if screens_element else "Number of screens not available"

        cinema_data = OrderedDict([
            ("name", name),
            ("address", address),
            ("num_screens", screens),
            ("movies", [])
        ])
        cinemas_data.append(cinema_data)

    return cinemas_data

# Función para guardar los datos en CosmosDB
def save_to_cosmosdb(data):
    current_date = datetime.now().strftime('%Y%m%d')
    document = {
        "id": current_date,
        "date": current_date,
        "data": data
    }
    container.upsert_item(document)
    logging.info(f"Datos guardados en Azure CosmosDB con ID: {current_date}")

# Verificar si el documento ya existe en CosmosDB
def check_if_document_exists(document_id):
    query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    return len(items) > 0

# Función que une el scraping y guardado
def scrape_and_save():
    current_date = datetime.now().strftime('%Y%m%d')
    if check_if_document_exists(current_date):
        logging.info(f"El documento con ID {current_date} ya existe en CosmosDB. Omisión del scraping.")
        return
    data = scrape_cinemas_data()
    save_to_cosmosdb(data)

# Definir la Azure Function con Timer Trigger
def main(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('¡El temporizador se ha vencido!')
    logging.info('La función de temporizador de Python se ha ejecutado.')
    scrape_and_save()

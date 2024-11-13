import json
from typing import Dict

from databricks import sql
from databricks.sdk import WorkspaceClient
from faker import Faker
from openai import OpenAI
import requests


fake = Faker()
generated_franchises = {}


def call_dbx_api(dbx_url, token, request_json):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    data_json = json.dumps(request_json, allow_nan=True)
    response = requests.request(method='POST', headers=headers, url=dbx_url, data=data_json)
    if response.status_code != 200:
        raise Exception(f'Request failed with status {response.status_code}, {response.text}')
    return response.json()


def init_dbx_openai_client(dbx_url, dbx_token):
    return OpenAI(
        api_key=dbx_token,
        base_url=f"https://{dbx_url}/serving-endpoints"
    )


def init_dbx_workspace_client(dbx_host, dbx_token):
    return WorkspaceClient(host=dbx_host, token=dbx_token)


def init_dbx_db_connection(dbx_host, dbx_token, warehouse_id):
    return sql.connect(
        server_hostname=dbx_host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        access_token=dbx_token)


def sentiment_analysis(openai_client, content) -> str:
    chat_completion = openai_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You will be provided with a tweet, and your task is to classify its sentiment as positive, neutral, or negative, in one word."
            },
            {
                "role": "user",
                "content": content
            }
        ],
        model="databricks-meta-llama-3-1-405b-instruct",
        max_tokens=256
    )
    return chat_completion.choices[0].message.content


def get_sql_prompt(openai_client, main_question) -> str:
    chat_completion = openai_client.chat.completions.create(
        messages=[
            {  # TODO split prompt into table description and general request by us and main ask by them
                "role": "system",
                "content": "You will be asked a question and you will return a SQL query. "
                           "The schema name is bakehouse and the tables are media.reviews and sales.franchises. "
                           "The media.reviews table has a franchiseID column that equals the franchiseID column in the sales.franchises table. "
            },
            {
                "role": "user",
                "content": main_question
            }
        ],
        model="databricks-meta-llama-3-1-70b-instruct",
        max_tokens=256
    )
    return chat_completion.choices[0].message.content


def new_franchise(franchise_id) -> Dict:
    adr = fake.address()
    street = adr.split('\n')[0]
    second_line = adr.split('\n')[1]
    city = second_line.split(',')[0]
    state = second_line.split(',')[1].strip().split(' ')[0]
    post_code = second_line.split(',')[1].strip().split(' ')[1]

    return {
        "id": franchise_id,
        "address": street,
        "city": city,
        "state": state,
        "postcode": post_code,
    }


def generate_and_store_franchise(franchise_id) -> Dict:
    res = generated_franchises.get(franchise_id)
    if res:
        return res
    new_fake_franchise = new_franchise(franchise_id)
    generated_franchises[franchise_id] = new_fake_franchise
    return new_fake_franchise


def get_franchise_details(dbx_sql_connection, franchise_id) -> Dict:
    cursor = dbx_sql_connection.cursor()

    cursor.execute(f"SELECT * from bakehouse.sales.franchises where franchiseID = '{franchise_id}'")
    first_row = cursor.fetchone()
    cursor.close()

    return first_row.asDict()

import csv
import datetime
import json

from decouple import config
from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

import uvicorn

from src import get_logger, get_consumer, get_producer, is_json, record_offsets

app = FastAPI()

templates = Jinja2Templates(directory="templates")

server_address = config("SERVER_ADDRESS", default="0.0.0.0")
server_port = config("SERVER_PORT", default=80, cast=int)

papertrail_url = config("PAPERTRAIL_URL")
papertrail_port = config("PAPERTRAIL_PORT", cast=int)
bootstrap = config('BOOTSTRAP_SERVER')
cc_key = config('SASL_USERNAME')
cc_secret = config('SASL_PASSWORD')

app_name = "App1"

cc_prod = get_producer(bootstrap, cc_key, cc_secret)
cc_cons = get_consumer(bootstrap, cc_key, cc_secret, app_name)

dbx_host = config('DATABRICKS_HOST')
dbx_token = config('DATABRICKS_TOKEN')


raw_data_topic = "raw-data"
chat_input_topic = "chat_input"
chat_output_topic = "chat_output"

if not papertrail_url or not bootstrap:
    raise RuntimeError('PAPERTRAIL_URL and BOOTSTRAP_SERVER must be set')

logger = get_logger(papertrail_url, papertrail_port, app_name)
logger.info("fastapi app initialized")


@app.get("/hello")
def say_hello():
    return "Hello"


def build_franchise_list():
    data_file = "./franchises.tsv"
    label_record = True
    ret_list = []
    with open(data_file) as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        for line in reader:
            if not label_record:
                ret_list.append({'id': line[0], 'name': line[1]})
            else:
                label_record = False
    return ret_list


@app.get("/", response_class=HTMLResponse)
def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request,
                                                     "main_title": "Your friendly assistant",
                                                     "server_address": server_address,
                                                     "server_port": server_port,
                                                     "franchises": build_franchise_list()
                                                     })


@app.get("/load-data")
def load_data():
    data_file = "./raw_reviews.tsv"

    label_record = True
    nb_out = 0

    with open(data_file) as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        for line in reader:
            if not label_record:
                record = {'review': line[0], 'franchise_id': line[1], 'date': line[2]}
                nb_out += 1
                json_str = json.dumps(record)
                cc_prod.produce(raw_data_topic, value=json_str)
            else:
                label_record = False
        cc_prod.flush()

    return {'produced': nb_out, 'topic': raw_data_topic}


def build_raw_data(franchise_id, review_text):
    return json.dumps({
        'review': review_text,
        'date': str(datetime.datetime.now()),
        'franchise_id': str(franchise_id),
    })


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(*, websocket: WebSocket, user_id: str):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        # record = {'review': line[0], 'franchise_id': line[1], 'date': line[2]}
        logger.info(f"[{user_id}] {data}")
        # record topic offsets
        offsets = record_offsets(cc_cons, chat_output_topic)

        if is_json(data):
            data_obj = json.loads(data)
            post_data = build_raw_data(data_obj['franchise'], data_obj['review'])
        else:
            post_data = data

        # produce to chat input topic with user_id as key
        cc_prod.produce(raw_data_topic, value=post_data, key=user_id)

        # start consuming and filter in user_id as key
        cc_cons.assign(offsets)
        cc_cons.subscribe([chat_output_topic])
        response = ""
        try:
            while True:
                msg = cc_cons.poll(1.0)
                if msg is None:
                    continue
                elif msg.error():
                    logger.error('error: {}'.format(msg.error()))
                else:
                    # logger.info("Message received")
                    msg_user_id = msg.key().decode('utf-8')
                    if msg_user_id == user_id:
                        response = msg.value().decode('utf-8')
                        # take out the quotes if any
                        if response.startswith('"'):
                            response = response[1:]
                        if response.endswith('"'):
                            response = response[:-1]
                        break
        finally:
            # Leave group and commit final offsets
            cc_cons.close()

        # send back msg received in chat
        logger.info(f"[{user_id}] {response}")
        await websocket.send_text(response)


if __name__ == "__main__":
    logger.info("Starting as __main__")
    uvicorn.run(app, host="0.0.0.0", port=8080)

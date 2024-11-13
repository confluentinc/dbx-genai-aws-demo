import json

from decouple import config

from src import (consume_loop, get_franchise_details, get_consumer, get_logger, get_producer, is_json,
                 init_dbx_openai_client, init_dbx_workspace_client, sentiment_analysis, init_dbx_db_connection)

papertrail_url = config("PAPERTRAIL_URL")
papertrail_port = config("PAPERTRAIL_PORT", cast=int)
bootstrap = config('BOOTSTRAP_SERVER')
cc_key = config('SASL_USERNAME')
cc_secret = config('SASL_PASSWORD')

dbx_host = config('DATABRICKS_HOST')
dbx_token = config('DATABRICKS_TOKEN')

app_name = "App2"
in_topic = "raw-data"
out_topic = "rich-data"


if not papertrail_url or not bootstrap:
    raise RuntimeError('PAPERTRAIL_URL and BOOTSTRAP_SERVER must be set')

logger = get_logger(papertrail_url, papertrail_port, app_name)

warehouse_id = "9e918132ee6abae4"
dbx_sql_client = init_dbx_db_connection(dbx_host, dbx_token, warehouse_id)
openai_client = init_dbx_openai_client(dbx_host, dbx_token)
# workspace_client = init_dbx_workspace_client(dbx_host, dbx_token)


def transform_record(json_obj):
    if review := json_obj.get("review"):
        try:
            sentiment = sentiment_analysis(openai_client, review)
            json_obj["sentiment"] = sentiment
        except Exception as e:
            json_obj["sentiment"] = "unavailable"
        json_obj["franchise"] = get_franchise_details(dbx_sql_client, json_obj.get("franchise_id"))
    return json_obj


def transform_msg(msg):
    return msg


def transform_message_item(message_bytes):
    # logger.info(f'Processing message item (size={len(message_bytes)})')
    msg_str = message_bytes.decode("utf-8")
    if is_json(msg_str):
        json_obj = json.loads(msg_str)
        transformed_item = transform_record(json_obj)
        return json.dumps(transformed_item)
    else:
        return transform_msg(msg_str)


def process_message(message, producer, output_topic):
    transformed_value = transform_message_item(message.value()) if message.value() else None
    transformed_key = transform_message_item(message.key()) if message.key() else None
    producer.produce(output_topic, value=transformed_value, key=transformed_key, headers=message.headers())


if __name__ == "__main__":
    logger.info("Starting as __main__")

    cc_producer = get_producer(bootstrap, cc_key, cc_secret)
    cc_consumer = get_consumer(bootstrap, cc_key, cc_secret, group_id=app_name)

    consume_loop(cc_consumer, cc_producer, in_topic, out_topic, process_callback=process_message, logger=logger)


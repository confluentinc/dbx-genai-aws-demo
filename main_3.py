import json

from decouple import config

from src import (consume_loop, get_consumer, get_logger, get_producer, is_json,
                 init_dbx_openai_client)

SENTIMENT_POSITIVE = "positive"
SENTIMENT_NEGATIVE = "negative"

papertrail_url = config("PAPERTRAIL_URL")
papertrail_port = config("PAPERTRAIL_PORT", cast=int)
bootstrap = config('BOOTSTRAP_SERVER')
cc_key = config('SASL_USERNAME')
cc_secret = config('SASL_PASSWORD')

dbx_host = config('DATABRICKS_HOST')
dbx_token = config('DATABRICKS_TOKEN')

app_name = "App3"
chat_input_topic = "rich-data"
chat_output_topic = "chat_output"

if not papertrail_url or not bootstrap:
    raise RuntimeError('PAPERTRAIL_URL and BOOTSTRAP_SERVER must be set')

logger = get_logger(papertrail_url, papertrail_port, app_name)

openai_client = init_dbx_openai_client(dbx_host, dbx_token)


def is_positive(sentiment: str):
    return sentiment.strip().lower() == SENTIMENT_POSITIVE


def is_negative(sentiment: str):
    return sentiment.strip().lower() == SENTIMENT_NEGATIVE


def process_positive(value_object) -> str:
    return ("http://"
            "To make it up to you, we'd like to offer you with this VIP coupon of a free croissant at any of our stores. Thank you!")


def process_negative(value_object) -> str:
    return ("We are sorry you had a less-than-perfect experience at our location. "
            "To make it up to you, we'd like to offer you with this VIP coupon of a free croissant at any of our stores. Thank you!")


def process_value(value_object) -> str:
    try:
        if is_positive(value_object["sentiment"]):
            return process_positive(value_object)
        elif is_negative(value_object["sentiment"]):
            return process_negative(value_object)
    except Exception as e:
        logger.error(e)
        return "Thanks for your review. We appreciate your feedback, but something went wrong."

    return "Thanks for your review. We appreciate your feedback."


def process_message(message, producer, output_topic):
    response = "The data in the input topic did not match what I was expecting."

    if message.value():
        # check sentiment and process accordingly
        value_str = message.value().decode("utf-8")
        if is_json(value_str):
            value_obj = json.loads(value_str)
            response = process_value(value_obj)

    producer.produce(output_topic, value=response, key=message.key(), headers=message.headers())


if __name__ == "__main__":
    logger.info("Starting as __main__")

    cc_producer = get_producer(bootstrap, cc_key, cc_secret)
    cc_consumer = get_consumer(bootstrap, cc_key, cc_secret, group_id=app_name)

    consume_loop(cc_consumer, cc_producer, chat_input_topic, chat_output_topic,
                 process_callback=process_message, logger=logger)


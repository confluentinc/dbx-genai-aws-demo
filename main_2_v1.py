import json
import logging
from typing import NamedTuple

from asyncio import get_event_loop
from aiokafka.helpers import create_ssl_context
from decouple import config
from faust import App, SASLCredentials
from faust.types.auth import AuthProtocol, SASLMechanism

from src import get_logger


class Auth(NamedTuple):
    username: str
    password: str


auth_env_var = 'USE_AUTH'
use_authorisation = config(auth_env_var, default=True, cast=bool)

faust_creds = SASLCredentials(username=config('SASL_USERNAME'), password=config('SASL_PASSWORD'),
                              mechanism=SASLMechanism.PLAIN,
                              ssl_context=create_ssl_context()) if use_authorisation else None
faust_creds.protocol = AuthProtocol.SASL_SSL

num_topic_partitions = config('TOPIC_PARTITIONS', default=3, cast=int)
topic_replication_factor = config('TOPIC_REPLICATION_FACTOR', default=3, cast=int)

offset = config('OFFSET', default='earliest')
offset_reset_policy = offset if not offset.isdigit() else None

broker_url = config('BOOTSTRAP_SERVER', default='localhost:9092')
print(f"Broker URL: {broker_url}")

app = App('dbx-genai-demo-2',
          broker="kafka://" + broker_url,
          broker_credentials=faust_creds,
          topic_replication_factor=topic_replication_factor,
          topic_partitions=num_topic_partitions,
          consumer_auto_offset_reset=offset_reset_policy)

in_topic = app.topic(config('IN_TOPIC'), internal=True, value_serializer='raw', key_serializer='raw')
out_topic = app.topic(config('OUT_TOPIC'))

papertrail_url = config("PAPERTRAIL_URL")
papertrail_port = config("PAPERTRAIL_PORT", cast=int)

app_name = "App2"

logger = get_logger(papertrail_url, papertrail_port, app_name)
logger.info("faust app (2) initialized")

class PartitionOffsetter:
    def __init__(self, index: int, offset: int):
        self._index = index
        self._offset = offset

    async def set_offset(self):
        from faust.types import TP
        await app.consumer.seek(TP(in_topic.get_topic_name(), self._index), self._offset)
        logging.info(f'Moved partition {self._index} offset to: {self._offset}')


if offset.isdigit():
    offset = int(offset)
    for partition in range(num_topic_partitions):
        app.task()(PartitionOffsetter(partition, offset).set_offset)


def is_json(some_string):
    try:
        json.loads(some_string)
    except ValueError:
        return False
    return True


async def transform_record(json_obj):
    json_obj["truc"] = "truc"
    logger.warning("transform_record()")
    return json_obj


async def transform_msg(msg):
    logger.warning("transform_msg()")
    return msg + "-truc"


@app.agent(in_topic, sink=[out_topic])
async def transform(stream):
    async for message_bytes in stream:
        logging.info(f'Processing message (size={len(message_bytes)})')
        msg_str = message_bytes.decode("utf-8")
        if is_json(msg_str):
            json_obj = json.loads(msg_str)
            encoded_out_message = await transform_record(json_obj)
        else:
            encoded_out_message = await transform_msg(msg_str)
        yield encoded_out_message


def main():
    event_loop = get_event_loop()
    for topic in (in_topic, out_topic):
        event_loop.run_until_complete(topic.maybe_declare())
    app.main()


if __name__ == '__main__':
    main()

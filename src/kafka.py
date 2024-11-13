from typing import Dict

from confluent_kafka import Consumer, Producer, TopicPartition

BOOTSTRAP_SERVERS = "bootstrap.servers"

SECURITY_PROTOCOL = "security.protocol"
SECURITY_PROTOCOL_SASL_SSL = "SASL_SSL"

SASL_MECHANISMS = "sasl.mechanisms"
SASL_MECHANISM_PLAIN = "PLAIN"
SASL_USERNAME = "sasl.username"
SASL_PASSWORD = "sasl.password"

SESSION_TIMEOUT = "session.timeout.ms"
GROUP_ID = "group.id"


def confluent_cloud_config(bootstrap_server, key, secret, group_id = None):
    ret = {
        BOOTSTRAP_SERVERS: bootstrap_server,
        SECURITY_PROTOCOL: SECURITY_PROTOCOL_SASL_SSL,
        SASL_MECHANISMS: SASL_MECHANISM_PLAIN,
        SASL_USERNAME: key,
        SASL_PASSWORD: secret,
        SESSION_TIMEOUT: "45000",
    }
    if group_id:
        ret[GROUP_ID] = group_id
    return ret


def get_producer(bootstrap_server, key, secret):
    config = confluent_cloud_config(bootstrap_server, key, secret)
    return Producer(config)


def get_consumer(bootstrap_server, key, secret, group_id):
    config = confluent_cloud_config(bootstrap_server, key, secret, group_id)
    return Consumer(config)


def record_offsets(client, topic):
    partition_offsets = []
    topic_meta_data = client.list_topics(topic)
    for partition_id in topic_meta_data.topics[topic].partitions.keys():
        partition_values = client.get_watermark_offsets(TopicPartition(topic, partition_id))
        partition_offsets.append(TopicPartition(topic, partition_id,  partition_values[1]))

    return partition_offsets


def consume_loop(consumer, producer, input_topic, output_topic, process_callback, logger):
    consumer.subscribe([input_topic])
    try:
        while True:
            msg = consumer.poll(2.0)
            if msg is None:
                continue
            elif msg.error():
                logger.error('error: {}'.format(msg.error()))
            else:
                process_callback(msg, producer, output_topic)
    finally:
        consumer.close()

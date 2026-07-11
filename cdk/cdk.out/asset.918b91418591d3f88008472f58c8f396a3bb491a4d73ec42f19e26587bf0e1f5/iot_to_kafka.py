"""
Bridges AWS IoT Core rule invocations into the MSK 'iot-events' topic.
Deployed inside the VPC so it can reach MSK's private brokers.
Requires the 'kafka-python' package bundled as a Lambda layer (see cdk/lambda/layer/README.md).
"""
import json
import os
import logging

from kafka import KafkaProducer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_producer = None


def get_producer():
    global _producer
    if _producer is None:
        brokers = os.environ["MSK_BROKERS"].split(",")
        _producer = KafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            security_protocol="PLAINTEXT",  # matches TLS_PLAINTEXT client-broker setting in msk_stack.py
        )
    return _producer


def handler(event, context):
    logger.info("Received IoT event: %s", json.dumps(event))
    producer = get_producer()
    producer.send("iot-events", event)
    producer.flush()
    return {"status": "ok"}

from rest_framework.decorators import api_view
from rest_framework.response import Response
from confluent_kafka import Producer, Consumer, KafkaError
import json
import uuid

conf = {'bootstrap.servers': 'kafka:9092'}
consumer_conf = {
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'search_response_group',
    'auto.offset.reset': 'earliest'
}

produser = Producer(conf)
consumer = Consumer(consumer_conf)



@api_view(['POST'])
def search_view(request):
    correlation_id = str(uuid.uuid4())
    query = {
        'data': request.data.get('query', ''),
        'correlation_id': correlation_id
    }
    topic = 'search_requests'
    response_topic = 'search_results'
    value = json.dumps(query)
    print(f'query type {value}')
    produser.produce(topic, value=value.encode('utf-8'))
    produser.flush()

    consumer.subscribe([response_topic])

    response = None
    while response is None:
        msg = consumer.poll(timeout=0.5)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return Response({'status': 'topic is  empty'})
                continue
            else:
                return Response({'status': str(msg.error())})
            break
        else:
            received_message = json.loads(msg.value().decode('utf-8'))
            if received_message.get('correlation_id') == correlation_id:
                response = json.loads(msg.value().decode('utf-8'))
                break
    consumer.close()
    return Response({'status': [response]})

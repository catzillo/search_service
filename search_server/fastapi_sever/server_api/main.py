from fastapi import FastAPI, HTTPException
from confluent_kafka import Consumer, Producer, KafkaError
import asyncpg
import asyncio
import json
import uuid

app = FastAPI()

KAFKA_BOOTSTRAP_SERVERS = 'kafka:9092'
SEARCH_REQUESTS_TOPIC = 'search_requests'
SEARCH_RESULTS_TOPIC = 'search_results'

DATABASE_URL = 'postgresql://postgres:password@localhost/items'

consumer = Consumer({
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'search_service',
    'auto.offset.reset': 'earliest'
})

producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def search_in_db(query: str):
    conn = await get_db_connection()
    try:
        results = await conn.fetch(
            "SELECT id, name, description FROM items WHERE name ILIKE $1",
            f'%{query}%'
        )
        return [dict(result) for result in results]
    finally:
        await conn.close()

def send_results_to_kafka(result, correlation_id):
    result_with_id = {
        **result,
        'correlation_id': correlation_id
    }
    producer.produce(SEARCH_RESULTS_TOPIC, json.dumps(result_with_id).encode('utf-8'))
    producer.flush()

async def process_kafka_messages():
    consumer.subscribe([SEARCH_REQUESTS_TOPIC])

    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f'kafka error {msg.error()}')
                break

        try:
            data = json.loads(msg.value().decode('utf-8'))
            query = data.get('data')
            correlation_id = data.get('correkation_id')

            if query or not correlation_id:
                continue

            results = await search_in_db(query)

            response = {
                'results': results,
                'status': 'success'
            }

            send_results_to_kafka(response, correlation_id)

        except Exception as e:
            print(f'Error processing message {e}')

@app.on_event('startup')
async def startup_create():
    asyncio.create_task(process_kafka_messages())


@app.get('/health')
async def health_check():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8010)




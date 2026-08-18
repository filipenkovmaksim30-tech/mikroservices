import aio_pika

from aio_pika.abc import AbstractRobustConnection, AbstractChannel



async def connect_rabbitmq(url: str) -> AbstractRobustConnection:
    return await aio_pika.connect_robust(url, timeout=10)

async def declare_channel(connection: AbstractRobustConnection) -> AbstractChannel:
    return await connection.channel(publisher_confirms=True, on_return_raises=True)
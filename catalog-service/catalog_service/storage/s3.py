from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

import aioboto3
from aiobotocore.config import AioConfig

from catalog_service.config import MediaSettings


class S3ObjectClient(Protocol):
    async def put_object(
        self, *, Bucket: str, Key: str, Body: bytes, ContentType: str
    ) -> object: ...

    async def delete_object(self, *, Bucket: str, Key: str) -> object: ...


class S3MediaStorage:

    def __init__(
        self,
        client: S3ObjectClient,
        bucket: str,
    ) -> None:
        self._client = client
        self._bucket = bucket

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def delete(self, key: str) -> None:
        await self._client.delete_object(
            Bucket=self._bucket,
            Key=key,
        )


@asynccontextmanager
async def create_s3_storage(
    settings: MediaSettings,
) -> AsyncIterator[S3MediaStorage]:
    session = aioboto3.Session()

    async with session.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key.get_secret_value(),
        region_name="us-east-1",
        config=AioConfig(s3={"addressing_style": "path"}),
    ) as client:
        yield S3MediaStorage(client, bucket=settings.bucket)

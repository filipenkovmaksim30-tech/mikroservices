import asyncio
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.product_image import ProductImage
from catalog_service.exceptions import ProductImageLimitError, ProductImageNotFoundError, ProductNotFoundError
from catalog_service.media.image_processing import process_product_image
from catalog_service.repositories.product_image import ProductImageRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.storage.s3 import S3MediaStorage

logger = logging.getLogger(__name__)



class ProductMediaService:
    def __init__(
        self,
        session: AsyncSession,
        products: ProductRepository,
        images: ProductImageRepository,
        storage: S3MediaStorage,
    ) -> None:
        self._session = session
        self._products = products
        self._images = images
        self._storage = storage

    async def add_image(self, product_id: UUID, file_bytes: bytes) -> ProductImage:
        processed = await asyncio.to_thread(process_product_image, file_bytes)

        image_id = uuid4()
        prefix = f"products/{product_id}/images/{image_id}"
        large_key = f"{prefix}/large.webp"
        thumbnail_key = f"{prefix}/thumbnail.webp"

        attempted_keys: list[str] = []
        committed = False

        try:
            attempted_keys.append(large_key)
            await self._storage.put(large_key, processed.large, "image/webp")

            attempted_keys.append(thumbnail_key)
            await self._storage.put(thumbnail_key, processed.thumbnail, "image/webp")

            async with self._session.begin():
                product = await self._products.get_by_id_for_update(product_id)
                if product is None:
                    raise ProductNotFoundError(product_id)

                existing = await self._images.list_by_product_id(product_id)
                occupied = {image.position for image in existing}
                free_position = next(
                    (position for position in range(8) if position not in occupied),
                    None,
                )
                if free_position is None:
                    raise ProductImageLimitError()

                image = ProductImage(
                    id=image_id,
                    product_id=product_id,
                    large_object_key=large_key,
                    thumbnail_object_key=thumbnail_key,
                    position=free_position,
                )

                await self._images.add(image)

            committed = True
            return image

        finally:
            if not committed:
                for key in reversed(attempted_keys):
                    try:
                        await self._storage.delete(key)
                    except Exception:
                        logger.exception("media.cleanup.failed")

    async def delete_image(self, product_id: UUID, image_id: UUID) -> None:
        async with self._session.begin():
            product = await self._products.get_by_id_for_update(product_id)
            if product is None:
                raise ProductNotFoundError(product_id)

            image = await self._images.get_by_id(image_id, product_id)
            if not image:
                raise ProductImageNotFoundError(image_id)

            keys = (image.large_object_key, image.thumbnail_object_key)
            await self._images.delete(image)

            remaining = await self._images.list_by_product_id(product_id)
            for position, remaining_image in enumerate(remaining):
                remaining_image.position = position

        for key in keys:
            try:
                await self._storage.delete(key)
            except Exception:
                logger.exception("media.cleanup.failed")
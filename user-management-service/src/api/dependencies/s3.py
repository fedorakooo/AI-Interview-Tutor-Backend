from functools import lru_cache

from src.config import settings
from src.domain.interfaces.storage.s3_client import IS3Client
from src.infrastructure.s3.s3_client import S3Client


@lru_cache
def get_s3_client() -> IS3Client:
    return S3Client(
        access_key=settings.s3_settings.access_key,
        secret_key=settings.s3_settings.secret_access_key,
        endpoint=settings.s3_settings.endpoint_url,
        region_name=settings.s3_settings.region_name,
        bucket_name=settings.s3_settings.bucket_name,
    )

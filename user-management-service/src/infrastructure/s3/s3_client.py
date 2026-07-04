import aioboto3
from botocore.config import Config
from src.domain.interfaces.storage.s3_client import IS3Client


class S3Client(IS3Client):
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        endpoint: str,
        region_name: str,
        bucket_name: str,
    ):
        self._config = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "endpoint_url": endpoint,
            "region_name": region_name,
            "config": Config(signature_version="s3v4"),
        }
        self._bucket_name = bucket_name
        self._session = aioboto3.Session()

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        async with self._session.client("s3", **self._config) as s3:
            await s3.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

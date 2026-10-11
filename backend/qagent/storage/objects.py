from typing import Optional, BinaryIO
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from qagent.config import settings


class ObjectStore:
    def __init__(self):
        self.endpoint = settings.neon_s3_endpoint
        self.bucket = settings.neon_s3_bucket
        self.client = None

        if self.endpoint and settings.neon_s3_access_key_id and settings.neon_s3_secret_access_key:
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name=settings.neon_s3_region,
                aws_access_key_id=settings.neon_s3_access_key_id,
                aws_secret_access_key=settings.neon_s3_secret_access_key,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )

    def is_configured(self) -> bool:
        return self.client is not None

    def put_object(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        """Uploads bytes to S3/Neon object storage. Returns the key or URL."""
        if not self.client:
            # Fallback or mock mode: return local key representation
            return f"local://{key}"

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return key

    def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        if not self.client:
            return f"/api/artifacts/{key}"

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )


object_store = ObjectStore()

from pathlib import Path
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from qagent.config import settings


class ObjectStore:
    def __init__(self):
        self.endpoint = settings.neon_s3_endpoint
        self.bucket = settings.neon_s3_bucket
        self.client = None
        self.local_dir = Path(settings.local_artifact_dir)

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
            # No Neon credentials: keep artifacts on local disk so runs still work offline.
            path = self._local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            return f"local://{key}"

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return key

    def _local_path(self, key: str) -> Path:
        path = (self.local_dir / key).resolve()
        if self.local_dir.resolve() not in path.parents:
            raise ValueError("invalid object key")
        return path

    def get_bytes(self, key: str) -> Optional[bytes]:
        """Reads an object (local fallback only; remote objects are served via presigned URL)."""
        if self.client:
            try:
                return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            except ClientError:
                return None
        path = self._local_path(key)
        return path.read_bytes() if path.exists() else None

    def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        if not self.client:
            return f"/api/artifacts/{key}"

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )


object_store = ObjectStore()

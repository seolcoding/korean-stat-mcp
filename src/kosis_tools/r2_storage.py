"""Cloudflare R2 Storage Client.

S3-compatible object storage for charts, reports, and data artifacts.
Falls back to local storage when R2 is not configured.

Usage:
    storage = get_storage()
    url = storage.upload_file("chart.html", "charts/my_chart.html")
    # Returns: https://pub-xxx.r2.dev/charts/my_chart.html (R2)
    # Or: /app/artifacts/charts/my_chart.html (local fallback)
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def upload_file(self, local_path: str, key: str) -> str:
        """Upload a file and return its public URL."""
        pass

    @abstractmethod
    def upload_bytes(self, data: bytes, key: str) -> str:
        """Upload bytes and return its public URL."""
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file. Returns True if successful."""
        pass

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Check if a file exists."""
        pass


class LocalStorage(StorageBackend):
    """Local filesystem storage backend (development/fallback)."""

    def __init__(self, base_path: str = "/app/artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage initialized at {self.base_path}")

    def upload_file(self, local_path: str, key: str) -> str:
        """Copy file to local artifacts directory."""
        import shutil

        dest_path = self.base_path / key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(local_path, dest_path)
        logger.debug(f"Local: uploaded {local_path} -> {dest_path}")

        return str(dest_path)

    def upload_bytes(self, data: bytes, key: str) -> str:
        """Write bytes to local file."""
        dest_path = self.base_path / key
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        dest_path.write_bytes(data)
        logger.debug(f"Local: wrote {len(data)} bytes -> {dest_path}")

        return str(dest_path)

    def delete_file(self, key: str) -> bool:
        """Delete local file."""
        file_path = self.base_path / key
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def file_exists(self, key: str) -> bool:
        """Check if local file exists."""
        return (self.base_path / key).exists()


class R2Storage(StorageBackend):
    """Cloudflare R2 storage backend (production).

    Uses boto3 with S3-compatible API.
    Requires environment variables:
        - R2_ACCOUNT_ID
        - R2_ACCESS_KEY_ID
        - R2_SECRET_ACCESS_KEY
        - R2_BUCKET_NAME
        - R2_PUBLIC_URL
        - R2_REGION (optional, default: auto)
    """

    def __init__(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError("boto3 is required for R2 storage. Install with: uv add boto3")

        self.account_id = os.environ["R2_ACCOUNT_ID"]
        self.bucket_name = os.environ["R2_BUCKET_NAME"]
        self.public_url = os.environ["R2_PUBLIC_URL"].rstrip("/")
        region = os.environ.get("R2_REGION", "auto")

        # Create S3-compatible client
        # Note: boto3 1.36.0+ requires checksum config for R2 compatibility
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name=region,
            config=Config(
                signature_version="s3v4",
                request_checksum_calculation="WHEN_REQUIRED",
                response_checksum_validation="WHEN_REQUIRED",
            ),
        )

        logger.info(f"R2Storage initialized: bucket={self.bucket_name}")

    def _get_content_type(self, key: str) -> str:
        """Determine content type from file extension."""
        ext = Path(key).suffix.lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".csv": "text/csv; charset=utf-8",
        }
        return content_types.get(ext, "application/octet-stream")

    def upload_file(self, local_path: str, key: str) -> str:
        """Upload file to R2 bucket."""
        content_type = self._get_content_type(key)

        self.client.upload_file(
            local_path,
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )

        url = f"{self.public_url}/{key}"
        logger.info(f"R2: uploaded {local_path} -> {url}")
        return url

    def upload_bytes(self, data: bytes, key: str) -> str:
        """Upload bytes to R2 bucket."""
        content_type = self._get_content_type(key)

        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        url = f"{self.public_url}/{key}"
        logger.info(f"R2: uploaded {len(data)} bytes -> {url}")
        return url

    def delete_file(self, key: str) -> bool:
        """Delete file from R2 bucket."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"R2: deleted {key}")
            return True
        except Exception as e:
            logger.warning(f"R2: failed to delete {key}: {e}")
            return False

    def file_exists(self, key: str) -> bool:
        """Check if file exists in R2 bucket."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False


def is_r2_configured() -> bool:
    """Check if R2 environment variables are configured."""
    required_vars = [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
        "R2_PUBLIC_URL",
    ]
    return all(os.environ.get(var) for var in required_vars)


def get_storage(force_local: bool = False) -> StorageBackend:
    """Get appropriate storage backend based on configuration.

    Args:
        force_local: If True, always use local storage regardless of R2 config.

    Returns:
        StorageBackend instance (R2Storage or LocalStorage)
    """
    storage_mode = os.environ.get("ARTIFACT_STORAGE", "auto")

    if force_local or storage_mode == "local":
        return LocalStorage()

    if storage_mode == "r2" or (storage_mode == "auto" and is_r2_configured()):
        try:
            return R2Storage()
        except Exception as e:
            logger.warning(f"Failed to initialize R2 storage: {e}. Falling back to local.")
            return LocalStorage()

    return LocalStorage()


def generate_artifact_key(prefix: str, filename: str, add_hash: bool = True) -> str:
    """Generate a storage key for an artifact.

    Args:
        prefix: Directory prefix (e.g., "charts", "reports", "data")
        filename: Original filename
        add_hash: If True, add content hash to prevent collisions

    Returns:
        Storage key like "charts/abc123_myfile.html"
    """
    if add_hash:
        # Generate short hash from filename + timestamp
        import time
        hash_input = f"{filename}{time.time()}".encode()
        short_hash = hashlib.sha256(hash_input).hexdigest()[:8]

        name, ext = os.path.splitext(filename)
        return f"{prefix}/{short_hash}_{name}{ext}"

    return f"{prefix}/{filename}"


# Convenience functions for common operations
def upload_chart(html_content: str, filename: str) -> str:
    """Upload HTML chart content and return URL."""
    storage = get_storage()
    key = generate_artifact_key("charts", filename)
    return storage.upload_bytes(html_content.encode("utf-8"), key)


def upload_report(html_content: str, filename: str) -> str:
    """Upload HTML report content and return URL."""
    storage = get_storage()
    key = generate_artifact_key("reports", filename)
    return storage.upload_bytes(html_content.encode("utf-8"), key)


def upload_data(json_content: str, filename: str) -> str:
    """Upload JSON data and return URL."""
    storage = get_storage()
    key = generate_artifact_key("data", filename)
    return storage.upload_bytes(json_content.encode("utf-8"), key)

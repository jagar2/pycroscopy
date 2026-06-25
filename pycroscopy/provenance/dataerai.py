"""Optional DataErai preservation helpers for pycroscopy workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence


DATAERAI_METADATA_SCHEMA_VERSION = 1
_DEFAULT_TAGS = ("pycroscopy", "dataerai", "provenance")


@dataclass
class PreservedAsset:
    """Result returned after preserving a pycroscopy artifact in DataErai."""

    asset_id: str
    content_id: str
    transfer_id: str
    metadata: dict[str, Any]
    relationships: list[Any] = field(default_factory=list)


def _json_safe(value: Any) -> Any:
    """Convert common scientific Python values to JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return _json_safe(value.tolist())
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def file_metadata(local_path: str | Path, *, chunk_size: int = 1024 * 1024) -> dict[str, Any]:
    """Return preservation metadata for a local file.

    The SHA-256 digest makes the DataErai asset independently verifiable after
    upload or download.
    """
    path = Path(local_path).expanduser().resolve()
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "filename": path.name,
        "suffix": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "sha256": digest.hexdigest(),
    }


def summarize_dataset(dataset: Any) -> dict[str, Any]:
    """Summarize a sidpy-like dataset without taking a hard dependency on sidpy."""
    if dataset is None:
        return {}

    summary: dict[str, Any] = {}
    for attr in ("title", "name", "data_type", "quantity", "units"):
        if hasattr(dataset, attr):
            value = getattr(dataset, attr)
            if value is not None:
                summary[attr] = _json_safe(value)

    for attr in ("shape", "dtype", "ndim"):
        if hasattr(dataset, attr):
            value = getattr(dataset, attr)
            if value is not None:
                summary[attr] = _json_safe(value)

    metadata = getattr(dataset, "metadata", None)
    if isinstance(metadata, dict):
        summary["metadata"] = _json_safe(metadata)

    dimensions = []
    for index in range(int(summary.get("ndim") or len(summary.get("shape") or []))):
        dim = getattr(dataset, f"dim_{index}", None)
        if dim is None:
            continue
        dim_summary = {}
        for attr in ("name", "quantity", "units", "dimension_type"):
            if hasattr(dim, attr):
                value = getattr(dim, attr)
                if value is not None:
                    dim_summary[attr] = _json_safe(value)
        if dim_summary:
            dimensions.append(dim_summary)
    if dimensions:
        summary["dimensions"] = dimensions

    return summary


def build_preservation_metadata(
    local_path: str | Path,
    *,
    dataset: Any = None,
    source_asset_ids: Optional[Sequence[str]] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the structured metadata attached to a DataErai asset."""
    pycroscopy_metadata: dict[str, Any] = {
        "schema_version": DATAERAI_METADATA_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file": file_metadata(local_path),
    }

    dataset_summary = summarize_dataset(dataset)
    if dataset_summary:
        pycroscopy_metadata["dataset"] = dataset_summary

    if source_asset_ids:
        pycroscopy_metadata["lineage"] = {
            "source_asset_ids": [str(asset_id) for asset_id in source_asset_ids],
        }

    if extra_metadata:
        pycroscopy_metadata["extra"] = _json_safe(extra_metadata)

    return {"pycroscopy": pycroscopy_metadata}


def _merged_tags(tags: Optional[Iterable[str]]) -> list[str]:
    seen = set()
    merged: list[str] = []
    for tag in [*_DEFAULT_TAGS, *(tags or [])]:
        if tag and tag not in seen:
            seen.add(tag)
            merged.append(tag)
    return merged


class DataEraiProvenanceClient:
    """Preserve pycroscopy artifacts as DataErai assets and link provenance."""

    def __init__(self, client: Any = None, **client_kwargs: Any) -> None:
        self._client = client
        self._client_kwargs = client_kwargs
        self._owns_client = client is None

    def __enter__(self) -> "DataEraiProvenanceClient":
        self._ensure_client()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def client(self) -> Any:
        return self._ensure_client()

    def close(self) -> None:
        if not self._owns_client or self._client is None:
            return
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = None

    def preserve_asset(
        self,
        local_path: str | Path,
        *,
        title: str,
        owner_type: str,
        owner_id: str,
        dataset: Any = None,
        source_asset_ids: Optional[Sequence[str]] = None,
        relationship_type: str = "derived_from",
        analysis_mode: Optional[str] = "non_destructive",
        description: Optional[str] = None,
        alias: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        collection_id: Optional[str] = None,
        extra_metadata: Optional[dict[str, Any]] = None,
        on_progress: Optional[Callable[[Any], None]] = None,
        transfer_timeout_s: float = 3600.0,
    ) -> PreservedAsset:
        """Upload an artifact and link it to source assets when supplied."""
        source_ids = [str(asset_id) for asset_id in (source_asset_ids or [])]
        metadata = build_preservation_metadata(
            local_path,
            dataset=dataset,
            source_asset_ids=source_ids,
            extra_metadata=extra_metadata,
        )
        client = self._ensure_client()
        create_relationship = getattr(client, "create_relationship", None)
        if source_ids and not callable(create_relationship):
            raise RuntimeError(
                "The DataErai SDK client must provide create_relationship() "
                "when source_asset_ids are supplied."
            )

        upload = client.upload(
            str(Path(local_path).expanduser().resolve()),
            title=title,
            owner_type=owner_type,
            owner_id=owner_id,
            collection_id=collection_id,
            description=description,
            alias=alias,
            tags=_merged_tags(tags),
            metadata=metadata,
            on_progress=on_progress,
            transfer_timeout_s=transfer_timeout_s,
        )

        relationships = []
        if source_ids:
            for source_id in source_ids:
                relationships.append(
                    create_relationship(
                        upload.asset_id,
                        source_id,
                        relationship_type=relationship_type,
                        analysis_mode=analysis_mode,
                        qualifier_note="Created by pycroscopy preservation workflow.",
                        qualifiers={
                            "tool": "pycroscopy",
                            "metadata_schema_version": DATAERAI_METADATA_SCHEMA_VERSION,
                        },
                    )
                )

        return PreservedAsset(
            asset_id=upload.asset_id,
            content_id=upload.content_id,
            transfer_id=upload.transfer_id,
            metadata=metadata,
            relationships=relationships,
        )

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from dataerai import DataEraiClient
        except ImportError as exc:
            raise ImportError(
                "Install the optional DataErai SDK with `pip install dataerai` "
                "to use pycroscopy.provenance.DataEraiProvenanceClient."
            ) from exc

        self._client = DataEraiClient(**self._client_kwargs)
        self._client.connect()
        return self._client

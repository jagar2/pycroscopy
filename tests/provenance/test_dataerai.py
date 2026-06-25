from types import SimpleNamespace

import pytest

from pycroscopy.provenance import (
    DATAERAI_METADATA_SCHEMA_VERSION,
    DataEraiProvenanceClient,
    build_preservation_metadata,
)


class FakeDataset:
    title = "Cleaned AFM image"
    data_type = "image"
    quantity = "height"
    units = "nm"
    shape = (2, 3)
    ndim = 2
    dtype = "float32"
    metadata = {"instrument": "AFM", "bias_v": 1.5}


class FakeDataEraiClient:
    def __init__(self):
        self.uploads = []
        self.relationships = []

    def upload(self, *args, **kwargs):
        self.uploads.append((args, kwargs))
        return SimpleNamespace(
            asset_id="asset-derived",
            content_id="content-derived",
            transfer_id="transfer-derived",
        )

    def create_relationship(self, *args, **kwargs):
        self.relationships.append((args, kwargs))
        return SimpleNamespace(id="relationship-1")


class FakeUploadOnlyClient:
    def __init__(self):
        self.uploads = []

    def upload(self, *args, **kwargs):
        self.uploads.append((args, kwargs))
        return SimpleNamespace(
            asset_id="asset-derived",
            content_id="content-derived",
            transfer_id="transfer-derived",
        )


def test_build_preservation_metadata_hashes_file(tmp_path):
    local_file = tmp_path / "result.npy"
    local_file.write_bytes(b"pycroscopy result")

    metadata = build_preservation_metadata(
        local_file,
        dataset=FakeDataset(),
        source_asset_ids=["asset-raw"],
        extra_metadata={"workflow": "clean_svd"},
    )

    px = metadata["pycroscopy"]
    assert px["schema_version"] == DATAERAI_METADATA_SCHEMA_VERSION
    assert px["file"]["filename"] == "result.npy"
    assert px["file"]["size_bytes"] == len(b"pycroscopy result")
    assert len(px["file"]["sha256"]) == 64
    assert px["dataset"]["title"] == "Cleaned AFM image"
    assert px["lineage"]["source_asset_ids"] == ["asset-raw"]
    assert px["extra"] == {"workflow": "clean_svd"}


def test_preserve_asset_uploads_and_links_sources(tmp_path):
    local_file = tmp_path / "cleaned.npy"
    local_file.write_bytes(b"cleaned")
    fake_client = FakeDataEraiClient()

    result = DataEraiProvenanceClient(client=fake_client).preserve_asset(
        local_file,
        title="Cleaned AFM image",
        owner_type="project",
        owner_id="project-1",
        dataset=FakeDataset(),
        source_asset_ids=["asset-raw"],
        tags=["afm"],
        extra_metadata={"workflow": "clean_svd"},
    )

    assert result.asset_id == "asset-derived"
    assert result.content_id == "content-derived"
    assert len(result.relationships) == 1

    args, kwargs = fake_client.uploads[0]
    assert args[0].endswith("cleaned.npy")
    assert kwargs["title"] == "Cleaned AFM image"
    assert kwargs["owner_type"] == "project"
    assert kwargs["owner_id"] == "project-1"
    assert kwargs["tags"] == ["pycroscopy", "dataerai", "provenance", "afm"]
    assert kwargs["metadata"]["pycroscopy"]["lineage"]["source_asset_ids"] == ["asset-raw"]

    rel_args, rel_kwargs = fake_client.relationships[0]
    assert rel_args == ("asset-derived", "asset-raw")
    assert rel_kwargs["relationship_type"] == "derived_from"
    assert rel_kwargs["analysis_mode"] == "non_destructive"
    assert rel_kwargs["qualifiers"]["tool"] == "pycroscopy"


def test_preserve_asset_requires_relationship_capable_client_for_sources(tmp_path):
    local_file = tmp_path / "cleaned.npy"
    local_file.write_bytes(b"cleaned")
    fake_client = FakeUploadOnlyClient()

    with pytest.raises(RuntimeError, match="create_relationship"):
        DataEraiProvenanceClient(client=fake_client).preserve_asset(
            local_file,
            title="Cleaned AFM image",
            owner_type="project",
            owner_id="project-1",
            source_asset_ids=["asset-raw"],
        )
    assert fake_client.uploads == []

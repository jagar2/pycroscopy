"""
Provenance and preservation helpers.

The DataErai integration is optional. Importing this module does not require
the ``dataerai`` SDK unless a caller asks :class:`DataEraiProvenanceClient` to
create its own SDK client.
"""

from .dataerai import (
    DATAERAI_METADATA_SCHEMA_VERSION,
    DataEraiProvenanceClient,
    PreservedAsset,
    build_preservation_metadata,
    file_metadata,
    summarize_dataset,
)

__all__ = [
    "DATAERAI_METADATA_SCHEMA_VERSION",
    "DataEraiProvenanceClient",
    "PreservedAsset",
    "build_preservation_metadata",
    "file_metadata",
    "summarize_dataset",
]

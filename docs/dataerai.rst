DataErai provenance
===================

``pycroscopy.provenance`` provides optional helpers for preserving analysis
artifacts in `DataErai <https://dataerai.com/>`_. The integration keeps
DataErai out of the default dependency set: install the DataErai SDK only in
the environment that will upload assets.

Installation
------------

.. code:: bash

  pip install dataerai

The DataErai command line application must also be installed and authenticated:

.. code:: bash

  dataerai auth login

Preserve an analysis result
---------------------------

The helper uploads a local artifact through the DataErai Python SDK, records
file preservation metadata such as SHA-256 and size, captures useful
``sidpy.Dataset`` metadata when available, and links the new asset to upstream
source assets.

.. code:: python

  import numpy as np
  import sidpy

  from pycroscopy.provenance import DataEraiProvenanceClient

  result_path = "cleaned_afm.npy"
  cleaned = sidpy.Dataset.from_array(np.random.random((64, 64)))
  cleaned.title = "Cleaned AFM image"
  cleaned.data_type = "image"
  np.save(result_path, np.asarray(cleaned))

  with DataEraiProvenanceClient(binary_path="/usr/local/bin/dataerai") as provenance:
      preserved = provenance.preserve_asset(
          result_path,
          title="Cleaned AFM image",
          owner_type="project",
          owner_id="proj-abc123",
          dataset=cleaned,
          source_asset_ids=["raw-asset-id"],
          relationship_type="derived_from",
          tags=["afm", "clean_svd"],
          extra_metadata={"workflow": "clean_svd"},
      )

  print("asset_id:", preserved.asset_id)
  print("content_id:", preserved.content_id)
  print("sha256:", preserved.metadata["pycroscopy"]["file"]["sha256"])
  print("relationship:", preserved.relationships[0].type)

Metadata schema
---------------

DataErai receives a top-level ``pycroscopy`` metadata object:

.. code:: json

  {
    "pycroscopy": {
      "schema_version": 1,
      "created_at": "2026-06-25T00:00:00+00:00",
      "file": {
        "filename": "cleaned_afm.npy",
        "suffix": ".npy",
        "size_bytes": 32768,
        "sha256": "..."
      },
      "dataset": {
        "title": "Cleaned AFM image",
        "data_type": "image",
        "shape": [64, 64],
        "dtype": "float64"
      },
      "lineage": {
        "source_asset_ids": ["raw-asset-id"]
      }
    }
  }

The DataErai relationship is created from the preserved asset to each source
asset. For derived analysis results, use ``derived_from`` or ``analysis_of`` as
the relationship type.

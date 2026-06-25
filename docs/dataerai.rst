DataErai provenance tutorials
=============================

Pycroscopy notebooks can preserve analysis outputs in
`DataErai <https://dataerai.com/>`_ by calling the DataErai Python SDK directly.
This guide does not add a pycroscopy API or dependency. Install and authenticate
DataErai only in notebook environments that need to upload assets.

Installation
------------

.. code:: bash

  pip install dataerai
  dataerai auth login

If your notebook should start the local DataErai daemon automatically, set the
``binary_path`` argument in ``DataeraiClient`` to the installed ``dataerai``
binary. If the daemon is already running, the default socket connection is
enough.

Notebook workflow
-----------------

The same pattern works in the example notebooks:

1. Save the pycroscopy or ``sidpy.Dataset`` result to a file.
2. Build a small ``pycroscopy`` metadata dictionary for search and audit.
3. Upload the file with ``DataeraiClient.upload``.
4. Link the uploaded asset to each source asset with
   ``DataeraiClient.create_relationship``.

.. code:: python

  import hashlib
  from datetime import datetime, timezone
  from pathlib import Path

  import numpy as np
  from dataerai import DataeraiClient

  result_path = Path("cleaned_afm.npy")
  np.save(result_path, np.asarray(cleaned_dataset))

  digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
  pycroscopy_metadata = {
      "pycroscopy": {
          "schema_version": 1,
          "created_at": datetime.now(timezone.utc).isoformat(),
          "file": {
              "filename": result_path.name,
              "suffix": result_path.suffix,
              "size_bytes": result_path.stat().st_size,
              "sha256": digest,
          },
          "dataset": {
              "title": getattr(cleaned_dataset, "title", None),
              "data_type": str(getattr(cleaned_dataset, "data_type", "")),
              "shape": list(getattr(cleaned_dataset, "shape", [])),
              "dtype": str(getattr(cleaned_dataset, "dtype", "")),
          },
          "lineage": {
              "source_asset_ids": ["raw-asset-id"],
          },
      }
  }

  with DataeraiClient(binary_path="/usr/local/bin/dataerai") as client:
      uploaded = client.upload(
          str(result_path),
          title="Cleaned AFM image",
          owner_type="project",
          owner_id="proj-abc123",
          tags=["pycroscopy", "afm"],
          metadata=pycroscopy_metadata,
      )

      relationship = client.create_relationship(
          uploaded.asset_id,
          "raw-asset-id",
          "derived_from",
          analysis_mode="non_destructive",
          qualifier_note="Created by a pycroscopy notebook.",
          qualifiers={"tool": "pycroscopy"},
      )

  print("asset_id:", uploaded.asset_id)
  print("content_id:", uploaded.content_id)
  print("relationship:", relationship.type)

Metadata shape
--------------

Use a top-level ``pycroscopy`` key so DataErai records can be searched and
audited without requiring DataErai to understand every pycroscopy object:

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

Relationship types
------------------

Create relationships from the uploaded result asset to upstream source assets.
Use ``derived_from`` for processed data products and ``analysis_of`` when the
asset is an analysis output that should point back to raw or intermediate data.

File format follow-up
---------------------

The notebook examples save NumPy ``.npy`` files so the DataErai workflow is easy
to run in a tutorial. A follow-up ADR should decide the preferred preservation
formats for pycroscopy workflows, including when to preserve original source
files, ``sidpy``/HDF5 artifacts, or compact derived arrays.

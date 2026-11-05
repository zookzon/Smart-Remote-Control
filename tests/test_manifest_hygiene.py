"""Manifest hygiene checks (hassfest-aligned)."""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "manifest.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_no_unknown_root_keys() -> None:
    """hassfest validates the manifest with extra keys forbidden.

    ``translation_key`` is not a manifest key (it is an entity/flow concept);
    shipping it fails hassfest validation.
    """
    assert "translation_key" not in _manifest()


def test_declares_file_upload_dependency() -> None:
    """config_flow.py calls file_upload.process_uploaded_file.

    Without the dependency declared, HA does not set the integration up first
    and the upload path fails with ``profile_read_failed / File does not exist``.
    """
    assert "file_upload" in _manifest().get("dependencies", [])


def test_version_and_domain_intact() -> None:
    manifest = _manifest()
    assert manifest["domain"] == "smart_remote_control"
    assert manifest["config_flow"] is True

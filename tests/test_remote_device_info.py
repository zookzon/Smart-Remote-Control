from pathlib import Path

SOURCE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "smart_remote_control"
    / "remote.py"
).read_text()


def test_standalone_remote_device_model_is_clean():
    """Device info uses a backend-neutral model label without parentheses."""
    assert 'model="IR Remote Blaster"' in SOURCE
    assert 'model=f"IR Remote ({self._backend})"' not in SOURCE

from pathlib import Path

SOURCE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "smart_remote_control"
    / "config_flow.py"
).read_text()


def test_broadlink_schema_restores_saved_remote_entity():
    """Broadlink Options Flow must preload the entity saved as CONF_REMOTE_ENTITY."""
    assert (
        'default=d.get("entity_id") or d.get(CONF_REMOTE_ENTITY, "")'
        in SOURCE
    )


def test_broadlink_options_uses_saved_definitions():
    """Options Flow must pass existing entry values into the Broadlink schema."""
    assert 'data_schema=_schema_broadlink(self._defs())' in SOURCE

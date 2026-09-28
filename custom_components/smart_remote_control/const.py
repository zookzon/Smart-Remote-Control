"""Constants for Smart Remote Control."""
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TEMPERATURE,
)

DOMAIN = "smart_remote_control"

CONF_DEVICE_CODE = "device_code"
CONF_DEVICE_PROFILE = "device_profile"
CONF_PROFILE_FILE = "Upload profile"
CONF_REMOTE_TYPE = "remote_type"
CONF_TARGET = "target"
CONF_TEMPERATURE = "temperature"
CONF_TEMPERATURE_STEP = "temperature_step"
CONF_FAN_MODES = "fan_modes"
CONF_PRESET_MODES = "preset_modes"
CONF_SWING = "swing"
CONF_HVAC_MODES = "hvac_modes"
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_REMOTE_ENTITY = "remote_entity"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_DEVICE_ID = "device_id"
CONF_DP = "dp"
CONF_HA_DEVICE_ID = "ha_device_id"
CONF_GROUPING_ATTRIBUTES = "grouping_attributes"
CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE = "grouping_attributes_as_sequence"
CONF_CURRENT_TEMPERATURE_SENSOR_ENTITY_ID = "current_temperature_sensor_entity_id"
CONF_CURRENT_HUMIDITY_SENSOR_ENTITY_ID = "current_humidity_sensor_entity_id"
ATTR_TEMPERATURE_RANGE = "temperature_range"
CONF_DEVICE_TYPE = "device_type"
CONF_REMOTE_BACKEND = "remote_backend"
CONF_IR_PREFIX = "ir_prefix"

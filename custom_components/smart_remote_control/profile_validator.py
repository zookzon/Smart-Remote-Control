"""Climate IR profile validation for Smart Remote Control."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from decimal import Decimal, InvalidOperation

ALLOWED_HVAC_MODES = {"auto", "cool", "dry", "fan_only", "heat", "heat_cool"}
ALLOWED_FAN_MODES = {"auto", "low", "medium", "high", "quiet", "turbo", "strong", "on", "off"}


@dataclass
class ProfileValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v for v in value)


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _temperature_keys(minimum: Any, maximum: Any, precision: Any) -> list[str]:
    """Return the exact JSON temperature keys implied by the profile range."""
    try:
        low = Decimal(str(minimum))
        high = Decimal(str(maximum))
        step = Decimal(str(precision))
    except (InvalidOperation, ValueError):
        return []
    if step <= 0 or low > high:
        return []
    keys: list[str] = []
    value = low
    # Hard safety limit also catches accidentally tiny precision values.
    while value <= high and len(keys) <= 1000:
        normalized = value.normalize()
        keys.append(str(int(normalized)) if normalized == normalized.to_integral() else format(normalized, "f"))
        value += step
    return keys if len(keys) <= 1000 else []


def _valid_ir_command(value: Any) -> bool:
    """Profiles may store one command or a non-empty command sequence."""
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def validate_climate_profile(profile: Any, transmitter: str) -> ProfileValidationResult:
    """Validate Climate Profile v1 and transmitter compatibility."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(profile, dict):
        return ProfileValidationResult(False, ["Profile root must be a JSON object."])

    hvac = profile.get("operationModes")
    fan = profile.get("fanModes")
    swing = profile.get("swingModes")
    preset = profile.get("presetModes")
    commands = profile.get("commands")

    if not _nonempty_string_list(hvac):
        errors.append("operationModes is required and must contain at least one HVAC mode.")
    else:
        invalid = [m for m in hvac if m not in ALLOWED_HVAC_MODES]
        if invalid:
            errors.append(f"Unsupported HVAC mode(s): {', '.join(invalid)}")

    if not _nonempty_string_list(fan):
        errors.append("fanModes is required and must contain at least one fan mode.")
    else:
        invalid = [m for m in fan if m not in ALLOWED_FAN_MODES]
        if invalid:
            errors.append(
                "Unsupported fan mode(s): " + ", ".join(invalid)
                + ". Allowed: auto, low, medium, high, quiet, turbo, strong, on, off."
            )

    for key, value in (("operationModes", hvac), ("fanModes", fan), ("swingModes", swing), ("presetModes", preset)):
        if isinstance(value, list):
            duplicates = _duplicate_values(value)
            if duplicates:
                errors.append(f"{key} contains duplicate value(s): {', '.join(duplicates)}.")

    for key, value in (("swingModes", swing), ("presetModes", preset)):
        if value is not None and not _nonempty_string_list(value):
            errors.append(f"{key} must be a non-empty list when present; remove it if unsupported.")

    # Swing/Preset can each use exactly one command model.  Missing type keeps
    # legacy profiles backward compatible by treating the feature as full_state.
    swing_type = str(profile.get("swingType", "full_state" if swing else "")).strip().lower()
    preset_type = str(profile.get("presetType", "full_state" if preset else "")).strip().lower()
    swing_commands = profile.get("swingCommands")
    preset_commands = profile.get("presetCommands")

    for feature, modes, feature_type, standalone in (
        ("swing", swing, swing_type, swing_commands),
        ("preset", preset, preset_type, preset_commands),
    ):
        type_key = f"{feature}Type"
        commands_key = f"{feature}Commands"
        if not modes:
            if profile.get(type_key) is not None or standalone is not None:
                errors.append(f"{type_key}/{commands_key} cannot be used without {feature}Modes.")
            continue
        if feature_type not in {"full_state", "standalone"}:
            errors.append(f"{type_key} must be 'full_state' or 'standalone' (found: {profile.get(type_key)!r}).")
            continue
        if feature_type == "standalone":
            if not isinstance(standalone, dict):
                errors.append(f"{type_key} is 'standalone', but {commands_key} is missing or is not an object.")
            else:
                missing = [mode for mode in modes if not standalone.get(mode)]
                if missing:
                    errors.append(f"{commands_key} is missing command(s) for: {', '.join(missing)}.")
        elif standalone is not None:
            errors.append(f"{type_key} is 'full_state', but {commands_key} was also found. Use only one {feature} command type.")

    for key in ("minTemperature", "maxTemperature", "precision"):
        if not isinstance(profile.get(key), (int, float)):
            errors.append(f"{key} is required and must be a number.")
    if isinstance(profile.get("minTemperature"), (int, float)) and isinstance(profile.get("maxTemperature"), (int, float)):
        if profile["minTemperature"] >= profile["maxTemperature"]:
            errors.append("minTemperature must be lower than maxTemperature.")
    if isinstance(profile.get("precision"), (int, float)) and profile["precision"] <= 0:
        errors.append("precision must be greater than 0.")

    expected_temperatures = _temperature_keys(
        profile.get("minTemperature"), profile.get("maxTemperature"), profile.get("precision")
    )
    if (
        isinstance(profile.get("minTemperature"), (int, float))
        and isinstance(profile.get("maxTemperature"), (int, float))
        and isinstance(profile.get("precision"), (int, float))
        and profile.get("precision", 0) > 0
    ):
        span = Decimal(str(profile["maxTemperature"])) - Decimal(str(profile["minTemperature"]))
        step = Decimal(str(profile["precision"]))
        if span >= 0 and span % step != 0:
            errors.append("Temperature range must be exactly divisible by precision so maxTemperature is selectable.")
        if not expected_temperatures:
            errors.append("Temperature range produces too many values or cannot be validated.")

    if not isinstance(commands, dict):
        errors.append("commands is required and must be an object.")
    elif not _valid_ir_command(commands.get("off")):
        errors.append("commands.off is required and must contain a valid IR command.")

    controller = str(profile.get("supportedController", "")).strip().lower()
    encoding = str(profile.get("commandsEncoding", "")).strip().lower()
    if transmitter == "broadlink":
        if controller != "broadlink":
            errors.append(f"Profile controller must be Broadlink (found: {profile.get('supportedController')!r}).")
        if encoding not in {"base64", "hex", "pronto"}:
            errors.append(
                f"Broadlink profile commandsEncoding must be Base64, Hex, or Pronto "
                f"(found: {profile.get('commandsEncoding')!r})."
            )
    elif transmitter == "zigbee2mqtt":
        if controller != "zigbee2mqtt":
            errors.append(f"Zigbee2MQTT profile controller must be Zigbee2MQTT (found: {profile.get('supportedController')!r}).")
        if encoding not in {"raw", "base64"}:
            errors.append(f"Zigbee2MQTT profile encoding must be Raw or Base64 (found: {profile.get('commandsEncoding')!r}).")
    elif transmitter == "localtuya":
        if controller != "localtuya":
            errors.append(f"LocalTuya profile controller must be LocalTuya (found: {profile.get('supportedController')!r}).")
        if encoding != "raw":
            errors.append(f"LocalTuya Direct IR requires commandsEncoding Raw (found: {profile.get('commandsEncoding')!r}).")

    # Structural validation follows SmartIR ordering:
    # HVAC -> Preset? -> Fan -> Swing? -> Temperature.
    # Every combination declared by the profile must exist. Missing branches are
    # errors because otherwise a profile can pass setup and fail only when the
    # user selects that state later.
    if isinstance(commands, dict) and _nonempty_string_list(hvac) and _nonempty_string_list(fan):
        def validate_state_tree(node: Any, path: str) -> None:
            if not isinstance(node, dict):
                errors.append(f"Command branch {path} must be an object.")
                return
            fan_nodes: list[tuple[str, dict[str, Any]]] = []
            for fan_mode in fan:
                child = node.get(fan_mode)
                fan_path = f"{path} -> {fan_mode}"
                if not isinstance(child, dict):
                    errors.append(f"Missing command branch: {fan_path}")
                else:
                    fan_nodes.append((fan_path, child))

            state_nodes = fan_nodes
            if swing and swing_type == "standalone":
                for state_path, state_node in state_nodes:
                    if any(k in state_node for k in swing):
                        errors.append(
                            f"swingType is 'standalone', but full-state Swing branches were also found under {state_path}. "
                            "Use only one Swing command type."
                        )
            elif swing and swing_type == "full_state":
                swing_nodes: list[tuple[str, dict[str, Any]]] = []
                for state_path, state_node in state_nodes:
                    for swing_mode in swing:
                        child = state_node.get(swing_mode)
                        swing_path = f"{state_path} -> {swing_mode}"
                        if not isinstance(child, dict):
                            errors.append(f"Missing command branch: {swing_path}")
                        else:
                            swing_nodes.append((swing_path, child))
                state_nodes = swing_nodes

            for state_path, state_node in state_nodes:
                for temp_key in expected_temperatures:
                    if not _valid_ir_command(state_node.get(temp_key)):
                        errors.append(f"Missing or invalid temperature command: {state_path} -> {temp_key}")

        for mode in hvac:
            mode_node = commands.get(mode)
            if not isinstance(mode_node, dict):
                errors.append(f"commands.{mode} is missing.")
                continue

            if preset and preset_type == "standalone" and any(k in mode_node for k in preset):
                errors.append(
                    f"presetType is 'standalone', but full-state Preset branches were also found under commands.{mode}. "
                    "Use only one Preset command type."
                )

            # The neutral preset state ('none') skips the Preset layer at runtime,
            # so a full-state Preset profile needs a normal/base HVAC->Fan tree as
            # well as each explicit Preset branch.
            validate_state_tree(mode_node, mode)

            if preset and preset_type == "full_state":
                for preset_mode in preset:
                    preset_node = mode_node.get(preset_mode)
                    preset_path = f"{mode} -> {preset_mode}"
                    if not isinstance(preset_node, dict):
                        errors.append(f"Missing command branch: {preset_path}")
                    else:
                        validate_state_tree(preset_node, preset_path)

    return ProfileValidationResult(not errors, errors, warnings)


def profile_summary(profile: dict[str, Any]) -> dict[str, str]:
    """Return display-ready profile summary placeholders."""
    return {
        "manufacturer": str(profile.get("manufacturer", "Unknown")),
        "models": ", ".join(map(str, profile.get("supportedModels", []))) or "Unknown",
        "controller": str(profile.get("supportedController", "Unknown")),
        "encoding": str(profile.get("commandsEncoding", "Unknown")),
        "temperature": f"{profile.get('minTemperature')}–{profile.get('maxTemperature')} °{profile.get('temperatureUnit', 'C')} (step {profile.get('precision')})",
        "hvac": f"{len(profile.get('operationModes', []))} mode(s): " + ", ".join(profile.get("operationModes", [])),
        "fan": f"{len(profile.get('fanModes', []))} mode(s): " + ", ".join(profile.get("fanModes", [])),
        "swing": ((f"{len(profile.get('swingModes', []))} mode(s): " + ", ".join(profile.get("swingModes", [])) + f" (type: {profile.get('swingType', 'full_state')})") if profile.get("swingModes") else "Not supported"),
        "preset": ((f"{len(profile.get('presetModes', []))} mode(s): " + ", ".join(profile.get("presetModes", [])) + f" (type: {profile.get('presetType', 'full_state')})") if profile.get("presetModes") else "Not supported"),
    }

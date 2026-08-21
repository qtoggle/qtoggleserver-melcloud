import abc

from typing import Any, cast

from qtoggleserver.core import ports as core_ports
from qtoggleserver.core.typing import Attribute, NullablePortValue, PortValue
from qtoggleserver.lib.polled import PolledPort

from . import MELCloud


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class MELCloudPort(PolledPort, metaclass=abc.ABCMeta):
    def get_peripheral(self) -> MELCloud:
        return cast(MELCloud, super().get_peripheral())


class MELCloudDevicePort(MELCloudPort, metaclass=abc.ABCMeta):
    PROPERTY_NAME = "change_me"

    def __init__(self, device_name: str, **kwargs) -> None:
        self._device_name: str = device_name

        super().__init__(**kwargs)

    async def read_value(self) -> NullablePortValue:
        return self.get_device_property(self.PROPERTY_NAME)

    async def write_value(self, value: PortValue) -> None:
        await self.set_device_property(self.PROPERTY_NAME, value)

    async def attr_get_value(self, name: str) -> Attribute:
        value = self.get_device_property(name)
        attrdef = self.ADDITIONAL_ATTRDEFS.get(name)
        if attrdef:
            get_transform = attrdef.get("_get_transform")
            if get_transform:
                value = get_transform(value)

        return value

    async def attr_set_value(self, name: str, value: Attribute) -> None:
        attrdef = self.ADDITIONAL_ATTRDEFS.get(name)
        if attrdef:
            set_transform = attrdef.get("_set_transform")
            if set_transform:
                value = set_transform(value)

        await self.set_device_property(name, value)

    def get_device_name(self) -> str:
        return self._device_name

    def get_device_property(self, property_name: str) -> Any:
        return self.get_peripheral().get_device_property(self._device_name, property_name)

    async def set_device_property(self, property_name: str, value: Any) -> Any:
        return await self.get_peripheral().set_device_property(self._device_name, property_name, value)


class DevicePowerPort(MELCloudDevicePort):
    ADDITIONAL_ATTRDEFS = {
        "mac": {
            "display_name": "MAC Address",
            "description": "Device MAC address",
            "type": "string",
            "modifiable": False,
        },
        "serial": {
            "display_name": "Serial Number",
            "description": "Device serial number",
            "type": "string",
            "modifiable": False,
        },
        "last_seen": {
            "display_name": "Last Seen",
            "description": "Moment when device was last seen online (UTC)",
            "type": "string",
            "modifiable": False,
            "_get_transform": lambda v: v.strftime(DATETIME_FORMAT) if v else None,
        },
        "wifi_signal": {
            "display_name": "Wi-Fi Signal",
            "description": "Wi-Fi signal strength",
            "type": "number",
            "unit": "dBm",
            "modifiable": False,
        },
    }

    TYPE = core_ports.TYPE_BOOLEAN
    WRITABLE = True
    PROPERTY_NAME = "power"


class TemperaturePort(MELCloudDevicePort, metaclass=abc.ABCMeta):
    def attr_get_unit(self) -> Attribute:
        temp_unit = self.get_device_property("temp_unit") or ""
        temp_unit = temp_unit[0].upper()
        if temp_unit == "C":
            temp_unit = "°C"
        return temp_unit


class ChoicesPort(MELCloudDevicePort, metaclass=abc.ABCMeta):
    TYPE = core_ports.TYPE_NUMBER
    CHOICES_PROPERTY_NAME = "change_me"
    DISPLAY_NAMES_MAPPING = {}

    def get_choices_str(self) -> list[str]:
        choices_str = list(self.get_device_property(self.CHOICES_PROPERTY_NAME)) or []
        if not choices_str:
            return []
        if choices_str[0] == "auto":
            choices_str.pop(0)
            choices_str.append("auto")

        return choices_str

    def attr_get_choices(self) -> Attribute:
        return [
            {
                "value": i + 1,
                "display_name": self.DISPLAY_NAMES_MAPPING.get(choice, choice.replace("_", " ").title()),
            }
            for i, choice in enumerate(self.get_choices_str())
        ]

    async def read_value(self) -> Attribute:
        choices_str = self.get_choices_str()
        value_str = self.get_device_property(self.PROPERTY_NAME)
        try:
            return choices_str.index(value_str) + 1
        except ValueError:
            return None

    async def write_value(self, value: PortValue) -> None:
        choices_str = self.get_choices_str()
        value_str = choices_str[int(value - 1)]
        await self.set_device_property(self.PROPERTY_NAME, value_str)


class RoomTemperaturePort(TemperaturePort):
    TYPE = core_ports.TYPE_NUMBER
    WRITABLE = False
    PROPERTY_NAME = "room_temperature"


class OutdoorTemperaturePort(TemperaturePort):
    TYPE = core_ports.TYPE_NUMBER
    WRITABLE = False
    PROPERTY_NAME = "outdoor_temperature"


class TargetTemperaturePort(TemperaturePort):
    TYPE = core_ports.TYPE_NUMBER
    WRITABLE = True
    PROPERTY_NAME = "target_temperature"

    def attr_get_min(self) -> Attribute:
        return self.get_device_property("target_temperature_min")

    def attr_get_max(self) -> Attribute:
        return self.get_device_property("target_temperature_max")

    def attr_get_step(self) -> Attribute:
        return self.get_device_property("target_temperature_step")


class OperationModePort(ChoicesPort):
    WRITABLE = True
    PROPERTY_NAME = "operation_mode"
    CHOICES_PROPERTY_NAME = "operation_modes"
    DISPLAY_NAMES_MAPPING = {
        "heat_cool": "Heat/Cool",
    }


class FanSpeedPort(ChoicesPort):
    WRITABLE = True
    PROPERTY_NAME = "fan_speed"
    CHOICES_PROPERTY_NAME = "fan_speeds"


class HorizontalVane(ChoicesPort):
    WRITABLE = True
    PROPERTY_NAME = "vane_horizontal"
    CHOICES_PROPERTY_NAME = "vane_horizontal_positions"
    DISPLAY_NAMES_MAPPING = {
        "1_up": "1 (Up)",
        "5_down": "5 (Down)",
    }


class VerticalVane(ChoicesPort):
    WRITABLE = True
    PROPERTY_NAME = "vane_vertical"
    CHOICES_PROPERTY_NAME = "vane_vertical_positions"
    DISPLAY_NAMES_MAPPING = {
        "1_up": "1 (Up)",
        "5_down": "5 (Down)",
    }

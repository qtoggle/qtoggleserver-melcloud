import logging
import re

from typing import Any, cast

import aiohttp
import pymelcloud

from qtoggleserver.lib.polled import PolledPeripheral
from qtoggleserver.utils.misc import to_underscore_case


class MELCloud(PolledPeripheral):
    TRIGGER_UPDATE_AFTER_POLL = True

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        *,
        username: str,
        password: str,
        device_names: list[str] | None = None,
        **kwargs,
    ) -> None:
        self._username: str = username
        self._password: str = password
        self._device_names: list[str] | None = device_names

        self._properties_cache: dict[str, Any] = {}
        self._devices_cache: dict[str, pymelcloud.Device] = {}

        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None

        super().__init__(**kwargs)

    async def make_port_args(self) -> list[dict[str, Any]]:
        return []

    async def _do_login(self) -> tuple[aiohttp.ClientSession, str]:
        self.debug('logging into MELCloud using username = "%s"', self._username)
        session = aiohttp.ClientSession()
        return session, await pymelcloud.login(self._username, self._password, session=session)

    async def _ensure_session(self) -> None:
        if self._session is None or self._token is None:
            self._session, self._token = await self._do_login()

    def get_device_property(self, device_name: str, property_name: str) -> Any:
        return self._properties_cache.get(device_name, {}).get(property_name)

    async def set_device_property(self, device_name: str, property_name: str, value: str) -> Any:
        await self._ensure_session()

        try:
            device = self._devices_cache[device_name]
        except KeyError:
            raise ValueError(f'Device "{device_name}" not found.')

        self.debug('setting "%s.%s" = "%s"', device_name, property_name, value)
        await device.set({property_name: value})
        self._properties_cache.setdefault(device_name, {})[property_name] = value

    async def poll(self) -> None:
        await self._update_devices()

    async def _update_devices(self) -> None:
        await self._ensure_session()

        devices_by_type = await pymelcloud.get_devices(self._token, session=self._session)
        for device_type in (pymelcloud.DEVICE_TYPE_ATA, pymelcloud.DEVICE_TYPE_ATW, pymelcloud.DEVICE_TYPE_ERV):
            devices = devices_by_type[device_type]
            for device in devices:
                self.debug('updating device "%s"', device.name)
                await device.update()
                self._devices_cache[device.name] = device

                self._update_cache_common(device)
                await self._ensure_device_common_ports(device)
                match device_type:
                    case pymelcloud.DEVICE_TYPE_ATA:
                        self._update_cache_ata(cast(pymelcloud.AtaDevice, device))
                        await self._ensure_device_ata_ports(cast(pymelcloud.AtaDevice, device))
                    case pymelcloud.DEVICE_TYPE_ATW:
                        self._update_cache_atw(cast(pymelcloud.AtwDevice, device))
                        await self._ensure_device_atw_ports(cast(pymelcloud.AtwDevice, device))
                    case pymelcloud.DEVICE_TYPE_ERV:
                        self._update_cache_erv(cast(pymelcloud.ErvDevice, device))
                        await self._ensure_device_erv_ports(cast(pymelcloud.ErvDevice, device))

    @staticmethod
    def _get_base_port_id(device: pymelcloud.Device) -> str:
        base_port_id = to_underscore_case(device.name)
        base_port_id = re.sub("[^a-z0-9_]", "", base_port_id)

        return base_port_id

    async def _ensure_device_common_ports(self, device: pymelcloud.Device) -> None:
        from .ports import DevicePowerPort

        existing_port_ids = set(self.get_ports_by_id())
        power_port_id = f"{self._get_base_port_id(device)}.power"
        if power_port_id not in existing_port_ids:
            port_args = {
                "driver": DevicePowerPort,
                "id": power_port_id,
                "device_name": device.name,
            }
            await self.add_port(port_args)

    async def _ensure_device_ata_ports(self, device: pymelcloud.AtaDevice) -> None:
        from .ports import (
            FanSpeedPort,
            HorizontalVane,
            OperationModePort,
            OutdoorTemperaturePort,
            RoomTemperaturePort,
            TargetTemperaturePort,
            VerticalVane,
        )

        for port_class in (
            FanSpeedPort,
            HorizontalVane,
            OperationModePort,
            OutdoorTemperaturePort,
            RoomTemperaturePort,
            TargetTemperaturePort,
            VerticalVane,
        ):
            existing_port_ids = set(self.get_ports_by_id())
            port_id = f"{self._get_base_port_id(device)}.{port_class.PROPERTY_NAME}"
            if port_id not in existing_port_ids:
                port_args = {
                    "driver": port_class,
                    "id": port_id,
                    "device_name": device.name,
                }
                await self.add_port(port_args)

    async def _ensure_device_atw_ports(self, device: pymelcloud.AtwDevice) -> None:
        pass

    async def _ensure_device_erv_ports(self, device: pymelcloud.ErvDevice) -> None:
        pass

    def _safe_get_last_seen(self, device: pymelcloud.Device) -> Any:
        try:
            return device.last_seen
        except ValueError:
            # Sometimes the string value for `last_seen` comes in a different format (without microseconds suffix).
            return self._properties_cache.get(device.name, {}).get("last_seen")

    def _update_cache_common(self, device: pymelcloud.Device) -> None:
        self._properties_cache.setdefault(device.name, {}).update(
            {
                "mac": device.mac,
                "serial": device.serial,
                "temp_unit": device.temp_unit,
                "last_seen": self._safe_get_last_seen(device),
                "power": device.power,
                "daily_energy_consumed": device.daily_energy_consumed,
                "wifi_signal": device.wifi_signal,
            }
        )

    def _update_cache_ata(self, device: pymelcloud.AtaDevice) -> None:
        self._properties_cache.setdefault(device.name, {}).update(
            {
                "room_temperature": device.room_temperature,
                "outdoor_temperature": device.outdoor_temperature,
                "target_temperature": device.target_temperature,
                "target_temperature_step": device.target_temperature_step,
                "target_temperature_min": device.target_temperature_min,
                "target_temperature_max": device.target_temperature_max,
                "operation_mode": device.operation_mode,
                "operation_modes": device.operation_modes,
                "fan_speed": device.fan_speed,
                "fan_speeds": device.fan_speeds,
                "vane_horizontal": device.vane_horizontal,
                "vane_horizontal_positions": device.vane_horizontal_positions,
                "vane_vertical": device.vane_vertical,
                "vane_vertical_positions": device.vane_vertical_positions,
                "total_energy_consumed": device.total_energy_consumed,
            }
        )

    def _update_cache_atw(self, device: pymelcloud.AtwDevice) -> None:
        self._properties_cache.setdefault(device.name, {}).update(
            {
                "tank_temperature": device.tank_temperature,
                "target_tank_temperature": device.target_tank_temperature,
                "target_tank_temperature_min": device.target_tank_temperature_min,
                "target_tank_temperature_max": device.target_tank_temperature_max,
                "outside_temperature": device.outside_temperature,
                "zones": device.zones,
                "status": device.status,
                "operation_mode": device.operation_mode,
                "operation_modes": device.operation_modes,
            }
        )

    def _update_cache_erv(self, device: pymelcloud.ErvDevice) -> None:
        self._properties_cache.setdefault(device.name, {}).update(
            {
                "room_temperature": device.room_temperature,
                "outside_temperature": device.outside_temperature,
                "fan_speed": device.fan_speed,
                "fan_speeds": device.fan_speeds,
                "actual_supply_fan_speed": device.actual_supply_fan_speed,
                "actual_exhaust_fan_speed": device.actual_exhaust_fan_speed,
                "ventilation_mode": device.ventilation_mode,
                "ventilation_modes": device.ventilation_modes,
                "actual_ventilation_mode": device.actual_ventilation_mode,
                "total_energy_consumed": device.total_energy_consumed,
                "presets": device.presets,
                "error_code": device.error_code,
                "core_maintenance_required": device.core_maintenance_required,
                "filter_maintenance_required": device.filter_maintenance_required,
                "night_purge_mode": device.night_purge_mode,
                "room_co2_level": device.room_co2_level,
            }
        )

"""Sensoren für Dyness Battery Integration."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE, UnitOfPower, UnitOfElectricCurrent, UnitOfEnergy
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

SENSORS = [
    # key, translation_key, unit, device_class, state_class, icon
    ("soc",                         "battery_soc",          PERCENTAGE,                   SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-high"),
    ("realTimePower",               "battery_power",        UnitOfPower.WATT,             SensorDeviceClass.POWER,   SensorStateClass.MEASUREMENT, "mdi:lightning-bolt"),
    ("realTimeCurrent",             "battery_current",      UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc"),
    ("createTime",                  "last_update",          None,                         None,                      None,                          "mdi:clock-outline"),
    ("batteryCapacity",             "battery_capacity",     UnitOfEnergy.KILO_WATT_HOUR,  SensorDeviceClass.ENERGY,  None,                          "mdi:battery"),
    ("installedPower",              "installed_power",      UnitOfPower.KILO_WATT,        SensorDeviceClass.POWER,   None,                          "mdi:solar-power"),
    ("deviceCommunicationStatus",   "communication_status", None,                         None,                      None,                          "mdi:wifi"),
    ("firmwareVersion",             "firmware_version",     None,                         None,                      None,                          "mdi:chip"),
    ("dataUpdateTime",              "data_update_time",     None,                         None,                      None,                          "mdi:clock-check-outline"),
    ("workStatus",                  "work_status",          None,                         None,                      None,                          "mdi:home-battery"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        DynessSensor(coordinator, entry, key, translation_key, unit, device_class, state_class, icon)
        for key, translation_key, unit, device_class, state_class, icon in SENSORS
    ])


class DynessSensor(CoordinatorEntity, SensorEntity):

    def __init__(self, coordinator, entry, key, translation_key, unit, device_class, state_class, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_has_entity_name = True
        self._attr_icon = icon

    @property
    def device_info(self):
        device_info = self.coordinator.device_info
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_sn)},
            "name": device_info.get("stationName", "Dyness Battery"),
            "manufacturer": "Dyness",
            "model": device_info.get("deviceModelName", "Junior Box"),
            "sw_version": device_info.get("firmwareVersion"),
        }

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._key)
        return None

    @property
    def available(self):
        return self.coordinator.last_update_success and self.native_value is not None

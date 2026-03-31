"""Sensors for Dyness Battery Integration."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfElectricCurrent, UnitOfEnergy, UnitOfTemperature, UnitOfElectricPotential
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN

_D = EntityCategory.DIAGNOSTIC

# FIX: Replaced translation keys with explicit hardcoded names. Removed Insulation sensors.
SENSORS = [
    ("soc", "State of Charge", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-high", None, None),
    ("realTimePower", "Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:lightning-bolt", None, None),
    ("realTimeCurrent", "Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc", None, None),
    ("packVoltage", "Pack Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:sine-wave", 1, None),
    ("cellVoltageDiffMv", "Cell Voltage Spread", "mV", None, SensorStateClass.MEASUREMENT, "mdi:arrow-expand-horizontal", 1, None),
    ("energyChargeTotal", "Total Energy Charged", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:counter", None, None),
    ("cycleCount", "Cycle Count", None, None, SensorStateClass.TOTAL_INCREASING, "mdi:battery-sync", None, None),
    ("balancingStatus", "Balancing Status", None, None, None, "mdi:scale-balance", None, None),
    ("masterAlarm", "Master Alarm", None, None, None, "mdi:alert", None, _D),
    ("al_afe", "Alarm Internal Comm", None, None, None, "mdi:lan-disconnect", None, _D),
    ("al_insul", "Alarm Insulation", None, None, None, "mdi:shield-alert", None, _D),
    ("boxCount", "Module Count", None, None, None, "mdi:package-variant", None, _D),
    ("workStatus", "Work Status", None, None, None, "mdi:home-battery", None, _D),
]

ALWAYS_REGISTER = {"soc", "realTimePower", "realTimeCurrent", "workStatus"}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DynessSensor(coordinator, entry, *s) for s in SENSORS if s[0] in ALWAYS_REGISTER or coordinator.data.get(s[0]) is not None])
    known_module_ids = set()
    def _add_new_modules():
        m_data = (coordinator.data or {}).get("module_data", {})
        for mid in [m for m in m_data if m not in known_module_ids]:
            known_module_ids.add(mid)
            async_add_entities([DynessModuleSensor(coordinator, entry, mid, *s) for s in MODULE_SENSORS])
    _add_new_modules()
    coordinator.async_add_listener(_add_new_modules)

class DynessSensor(CoordinatorEntity, SensorEntity):
    # FIX: Assign the name directly to self._attr_name instead of self._attr_translation_key
    def __init__(self, coord, entry, key, name, unit, dev, state, icon, prec, cat):
        super().__init__(coord)
        self._key, self._attr_name, self._attr_native_unit_of_measurement = key, name, unit
        self._attr_device_class, self._attr_state_class, self._attr_icon = dev, state, icon
        self._attr_unique_id, self._attr_has_entity_name = f"{entry.entry_id}_{key}", True
        if prec: self._attr_suggested_display_precision = prec
        if cat: self._attr_entity_category = cat
        
    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.device_sn)}, "name": "Dyness Main Unit", "manufacturer": "Dyness", "model": "Tower BDU"}
        
    @property
    def native_value(self): return self.coordinator.data.get(self._key)

# FIX: Applied explicit names to module sensors as well
MODULE_SENSORS = [
    ("cell_temp_1", "Temperature 1", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer", None),
    ("cell_temp_2", "Temperature 2", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer", None),
    ("cell_voltage_spread_mv", "Voltage Spread", "mV", None, SensorStateClass.MEASUREMENT, "mdi:arrow-expand-horizontal", 1),
    *[(f"cell_{i:02d}", f"Cell {i:02d}", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:battery-outline", 3) for i in range(1, 31)],
]

class DynessModuleSensor(CoordinatorEntity, SensorEntity):
    # FIX: Assign the name directly to self._attr_name
    def __init__(self, coord, entry, mid, key, name, unit, dev, state, icon, prec=None):
        super().__init__(coord)
        self._mid, self._key, self._attr_name = mid, key, name
        self._attr_native_unit_of_measurement, self._attr_device_class = unit, dev
        self._attr_state_class, self._attr_icon, self._attr_has_entity_name = state, icon, True
        self._attr_unique_id = f"{entry.entry_id}_{mid}_{key}"
        if prec: self._attr_suggested_display_precision = prec
        
    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"{self.coordinator.device_sn}_{self._mid}")}, "name": f"Dyness Module {self._mid}", "manufacturer": "Dyness", "model": "Battery Pack", "via_device": (DOMAIN, self.coordinator.device_sn)}
        
    @property
    def native_value(self): return self.coordinator.data.get("module_data", {}).get(self._mid, {}).get(self._key)
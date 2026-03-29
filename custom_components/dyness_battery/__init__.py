"""Dyness Battery Integration for Home Assistant."""
import asyncio
import hashlib
import hmac
import base64
import json
import logging
import time
from email.utils import formatdate
from datetime import timedelta

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dyness_battery"
PLATFORMS = [Platform.SENSOR]

# API Rate-Limit: max ~60 Calls/Hour = 1/Minute
_MIN_CALL_INTERVAL = 1.5
_RATE_LIMIT_BACKOFF = 10
_MAX_RETRIES = 3

# Valid BMS Suffixes
_BMS_SUFFIXES = ("-BMS", "-BDU")

def _scan_interval_for_modules(n: int) -> timedelta:
    """Dynamic scan interval based on module count."""
    if n <= 2:
        return timedelta(minutes=5)
    elif n <= 4:
        return timedelta(minutes=10)
    else:
        return timedelta(minutes=15)

def _get_gmt_time() -> str:
    return formatdate(timeval=None, localtime=False, usegmt=True)

def _get_md5(body: str) -> str:
    md5 = hashlib.md5(body.encode("utf-8")).digest()
    return base64.b64encode(md5).decode("utf-8")

def _get_signature(api_secret: str, content_md5: str, date: str, path: str) -> str:
    string_to_sign = (
        "POST" + "\n" + content_md5 + "\n" +
        "application/json" + "\n" + date + "\n" + path
    )
    sig = hmac.new(
        api_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        "sha1"
    ).digest()
    return base64.b64encode(sig).decode("utf-8")

def _build_headers(api_id: str, api_secret: str, body: str, sign_path: str) -> dict:
    date = _get_gmt_time()
    content_md5 = _get_md5(body)
    signature = _get_signature(api_secret, content_md5, date, sign_path)
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Content-MD5": content_md5,
        "Date": date,
        "Authorization": f"API {api_id}:{signature}",
    }

def _to_float(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None

def _is_success(result: dict) -> bool:
    """Checks if API response is successful."""
    code = result.get("code")
    return str(code) in ("0", "200") or code == 0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = DynessDataCoordinator(
        hass,
        entry.data["api_id"],
        entry.data["api_secret"],
        entry.data["api_base"],
        device_sn=entry.data.get("device_sn"),
        dongle_sn=entry.data.get("dongle_sn"),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class DynessDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_id, api_secret, api_base, device_sn=None, dongle_sn=None):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5))
        self.api_id     = api_id
        self.api_secret = api_secret
        self.api_base   = api_base
        self.device_sn  = device_sn
        self.dongle_sn  = dongle_sn
        self.station_info  = {}
        self.device_info   = {}
        self.storage_info  = {}
        self.realtime_data = {}
        self.module_data: dict[str, dict] = {}
        self._bound: bool = False
        self._module_sns: list[str] = []
        self._last_call_time: float = 0.0

    async def _call(self, session: aiohttp.ClientSession, path: str, body_dict: dict) -> dict:
        """Rate-limited API call with retry."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < _MIN_CALL_INTERVAL:
            await asyncio.sleep(_MIN_CALL_INTERVAL - elapsed)
        url = f"{self.api_base}/openapi/ems-device{path}"
        body = json.dumps(body_dict, separators=(',', ':'))
        for attempt in range(_MAX_RETRIES + 1):
            self._last_call_time = time.monotonic()
            headers = _build_headers(self.api_id, self.api_secret, body, path)
            try:
                async with session.post(url, headers=headers, data=body) as response:
                    if response.status == 429:
                        wait = _RATE_LIMIT_BACKOFF * (2 ** attempt)
                        if attempt < _MAX_RETRIES:
                            await asyncio.sleep(wait)
                            continue
                        return {}
                    raw_text = await response.text()
                    return json.loads(raw_text)
            except aiohttp.ClientError as e:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        return {}

    async def _async_update_data(self):
        async with aiohttp.ClientSession() as session:
            try:
                async with async_timeout.timeout(90):
                    # Auto-Discovery BMS SN
                    if not self.device_sn:
                        sl_result = await self._call(session, "/v1/device/storage/list", {})
                        if _is_success(sl_result):
                            device_list = (sl_result.get("data", {}) or {}).get("list", [])
                            bms = next((d for d in device_list if str(d.get("device_sn", "")).endswith(_BMS_SUFFIXES)), None) or (device_list[0] if device_list else None)
                            if bms:
                                self.device_sn = bms.get("deviceSn", "")
                            else:
                                raise UpdateFailed("Dyness: No devices found.")

                    # Bind device
                    if not self._bound:
                        bind_body = {"deviceSn": self.device_sn}
                        if self.dongle_sn:
                            bind_body["collectorSn"] = self.dongle_sn
                        await self._call(session, "/v1/device/bindSn", bind_body)
                        self._bound = True

                    # Static info
                    if not self.station_info:
                        result = await self._call(session, "/v1/station/info", {"deviceSn": self.device_sn})
                        if _is_success(result):
                            self.station_info = result.get("data", {}) or {}

                    if not self.device_info:
                        body = {"deviceSn": self.device_sn}
                        if self.dongle_sn:
                            body["collectorSn"] = self.dongle_sn
                        result = await self._call(session, "/v1/device/household/storage/detail", body)
                        if _is_success(result):
                            self.device_info = result.get("data", {}) or {}

                    # Real-time update
                    body = {"deviceSn": self.device_sn}
                    if self.dongle_sn:
                        body["collectorSn"] = self.dongle_sn
                    rt_result = await self._call(session, "/v1/device/realTime/data", body)
                    if _is_success(rt_result):
                        raw = rt_result.get("data", []) or []
                        self.realtime_data = {item["pointId"]: item["pointValue"] for item in raw if isinstance(item, dict)}
                        
                        # Module Discovery
                        if not self._module_sns:
                            sub_raw = self.realtime_data.get("SUB", "")
                            if sub_raw:
                                candidates = [s.strip() for s in str(sub_raw).split(",") if s.strip()]
                                self._module_sns = [s for s in candidates if not s.endswith(_BMS_SUFFIXES)]

                    # Per-Module data (Cells 1-30)
                    new_module_data = {}
                    for sn in self._module_sns:
                        m_result = await self._call(session, "/v1/device/realTime/data", {"deviceSn": sn})
                        if _is_success(m_result):
                            m_raw = m_result.get("data", []) or []
                            m_pts = {item["pointId"]: item["pointValue"] for item in m_raw if isinstance(item, dict)}
                            mid = sn.split("-")[-1] if "-" in sn else sn[-8:]
                            new_module_data[mid] = _parse_module_points(sn, mid, m_pts)
                    self.module_data = new_module_data

                    # Power Data
                    body = {"pageNo": 1, "pageSize": 1, "deviceSn": self.device_sn}
                    if self.dongle_sn:
                        body["collectorSn"] = self.dongle_sn
                    result = await self._call(session, "/v1/device/getLastPowerDataBySn", body)
                    data = result.get("data", {})
                    if isinstance(data, list):
                        data = data[-1] if data else {}

                    # Mappings & Capacity Fix
                    data["batteryCapacity"] = _to_float(self.station_info.get("batteryCapacity"))
                    data["firmwareVersion"] = self.device_info.get("firmwareVersion")
                    data["workStatus"] = self.storage_info.get("workStatus")

                    rt = self.realtime_data
                    if "1400" in rt: # Tower Schema
                        data["soh"] = rt.get("1500")
                        data["tempMax"] = rt.get("3000")
                        data["tempMin"] = rt.get("3300")
                        data["cellVoltageMax"] = rt.get("2400")
                        data["cellVoltageMin"] = rt.get("2700")
                        data["cycleCount"] = rt.get("1800")
                        data["chargeLimit"] = rt.get("2000")
                        data["dischargeLimit"] = rt.get("2100")
                        data["fanStatus"] = rt.get("3800")
                        data["heatingStatus"] = rt.get("3900")
                        data["maxCellBox"] = rt.get("2500")
                        data["minCellBox"] = rt.get("2800")

                    # Calculations
                    vmax = _to_float(data.get("cellVoltageMax"))
                    vmin = _to_float(data.get("cellVoltageMin"))
                    if vmax and vmin:
                        data["cellVoltageDiffMv"] = round((vmax - vmin) * 1000, 1)

                    data["module_data"] = self.module_data
                    return data

            except Exception as err:
                raise UpdateFailed(f"Unexpected error: {err}") from err

def _parse_module_points(sn: str, mid: str, pts: dict) -> dict:
    """Parses Sub-Module data including all 30 individual cell voltages."""
    def g(key): return pts.get(key) if pts.get(key) not in (None, "") else None
    d = {"sn": sn, "module_id": mid, "voltage": _to_float(g("13500")), "current": _to_float(g("13400"))}
    cells = []
    for i in range(1, 31):
        pid = str(11100 + i * 100)
        val = _to_float(pts.get(pid))
        if val is not None:
            d[f"cell_{i:02d}"] = val
            cells.append(val)
    if cells:
        d["cell_voltage_max"] = max(cells)
        d["cell_voltage_min"] = min(cells)
        d["cell_voltage_spread_mv"] = round((max(cells) - min(cells)) * 1000, 1)
    d["cell_temp_1"] = _to_float(g("14300"))
    d["cell_temp_2"] = _to_float(g("14400"))
    return d
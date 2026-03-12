"""Dyness Battery Integration für Home Assistant."""
import hashlib
import hmac
import base64
import json
import logging
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
SCAN_INTERVAL = timedelta(minutes=5)


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


async def _api_call(session, api_id, api_secret, api_base, sign_path, body_dict):
    url = f"{api_base}/openapi/ems-device{sign_path}"
    body = json.dumps(body_dict, separators=(',', ':'))
    headers = _build_headers(api_id, api_secret, body, sign_path)
    async with session.post(url, headers=headers, data=body) as response:
        raw_text = await response.text()
        _LOGGER.debug("Dyness %s: %s", sign_path, raw_text)
        return json.loads(raw_text)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = DynessDataCoordinator(
        hass,
        entry.data["api_id"],
        entry.data["api_secret"],
        entry.data["device_sn"],
        entry.data["dongle_sn"],
        entry.data["api_base"],
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

    def __init__(self, hass, api_id, api_secret, device_sn, dongle_sn, api_base):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api_id = api_id
        self.api_secret = api_secret
        self.device_sn = device_sn
        self.dongle_sn = dongle_sn
        self.api_base = api_base
        self.station_info = {}
        self.device_info = {}
        self.storage_info = {}

    async def _async_update_data(self):
        async with aiohttp.ClientSession() as session:
            try:
                async with async_timeout.timeout(30):

                    # Statische Daten einmalig beim Start laden
                    if not self.station_info:
                        try:
                            result = await _api_call(
                                session, self.api_id, self.api_secret, self.api_base,
                                "/v1/station/info",
                                {"deviceSn": self.device_sn}
                            )
                            if str(result.get("code", "")) in ("0", "200"):
                                self.station_info = result.get("data", {}) or {}
                                _LOGGER.debug("Dyness station/info geladen: %s", self.station_info)
                            else:
                                _LOGGER.warning(
                                    "Dyness station/info: API antwortete mit Code %s – %s",
                                    result.get("code"), result.get("info")
                                )
                        except Exception as e:
                            _LOGGER.warning("Dyness station/info nicht erreichbar: %s", e)

                    if not self.device_info:
                        try:
                            result = await _api_call(
                                session, self.api_id, self.api_secret, self.api_base,
                                "/v1/device/household/storage/detail",
                                {"deviceSn": self.device_sn, "collectorSn": self.dongle_sn}
                            )
                            if str(result.get("code", "")) in ("0", "200"):
                                self.device_info = result.get("data", {}) or {}
                                _LOGGER.debug("Dyness household/storage/detail geladen: %s", self.device_info)
                            else:
                                _LOGGER.warning(
                                    "Dyness household/storage/detail: API antwortete mit Code %s – %s",
                                    result.get("code"), result.get("info")
                                )
                        except Exception as e:
                            _LOGGER.warning("Dyness household/storage/detail nicht erreichbar: %s", e)

                    # storage/list bei jedem Update abrufen (liefert workStatus)
                    try:
                        result = await _api_call(
                            session, self.api_id, self.api_secret, self.api_base,
                            "/v1/device/storage/list",
                            {"deviceSn": self.device_sn, "collectorSn": self.dongle_sn}
                        )
                        if str(result.get("code", "")) in ("0", "200"):
                            device_list = (result.get("data", {}) or {}).get("list", [])
                            match = next(
                                (d for d in device_list if d.get("deviceSn") == self.device_sn),
                                device_list[0] if device_list else {}
                            )
                            self.storage_info = match
                            _LOGGER.debug("Dyness workStatus: %s", match.get("workStatus"))
                        else:
                            _LOGGER.warning(
                                "Dyness storage/list: API antwortete mit Code %s – %s",
                                result.get("code"), result.get("info")
                            )
                    except Exception as e:
                        _LOGGER.warning("Dyness storage/list nicht erreichbar: %s", e)

                    # Aktuelle Leistungsdaten abrufen (alle 5 Minuten)
                    result = await _api_call(
                        session, self.api_id, self.api_secret, self.api_base,
                        "/v1/device/getLastPowerDataBySn",
                        {"pageNo": 1, "pageSize": 1,
                         "deviceSn": self.device_sn, "collectorSn": self.dongle_sn}
                    )

                    code = str(result.get("code", ""))
                    if code not in ("0", "200"):
                        _LOGGER.error(
                            "Dyness getLastPowerDataBySn fehlgeschlagen – Code %s: %s "
                            "(deviceSn=%s)",
                            code, result.get("info"), self.device_sn
                        )
                        raise UpdateFailed(
                            f"Dyness API Fehler (Code {code}): {result.get('info', 'Unbekannt')} "
                            f"– deviceSn={self.device_sn}"
                        )

                    data = result.get("data", {})
                    _LOGGER.debug("Dyness Rohdaten empfangen: %s Einträge", len(data) if isinstance(data, list) else 1)

                    # API gibt Liste zurück — neuesten gültigen Eintrag nehmen
                    if isinstance(data, list):
                        valid = [d for d in data if d.get("soc") is not None]
                        if not valid:
                            _LOGGER.warning(
                                "Dyness: Alle %d Datenpunkte haben soc=null – "
                                "Gerät offline oder keine aktuellen Daten (deviceSn=%s)",
                                len(data), self.device_sn
                            )
                        data = valid[-1] if valid else (data[-1] if data else {})

                    # Statische Felder ergänzen
                    data["batteryCapacity"]           = self.station_info.get("batteryCapacity")
                    data["installedPower"]             = self.station_info.get("installedPower")
                    data["deviceCommunicationStatus"] = self.device_info.get("deviceCommunicationStatus")
                    data["firmwareVersion"]            = self.device_info.get("firmwareVersion")
                    data["dataUpdateTime"]             = self.device_info.get("dataUpdateTime")
                    data["workStatus"]                 = self.storage_info.get("workStatus")

                    return data

            except UpdateFailed:
                raise
            except aiohttp.ClientError as err:
                _LOGGER.error("Dyness Verbindungsfehler: %s", err)
                raise UpdateFailed(f"Verbindungsfehler zur Dyness API: {err}") from err
            except Exception as err:
                _LOGGER.error("Dyness unerwarteter Fehler: %s", err, exc_info=True)
                raise UpdateFailed(f"Unerwarteter Fehler: {err}") from err

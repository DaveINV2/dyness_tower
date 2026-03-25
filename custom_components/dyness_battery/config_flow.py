"""Config Flow für Dyness Battery Integration."""
import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("api_id"): str,
    vol.Required("api_secret"): str,
})

STEP_MANUAL_DATA_SCHEMA = vol.Schema({
    vol.Required("api_id"): str,
    vol.Required("api_secret"): str,
    vol.Required("device_sn"): str,
    vol.Optional("dongle_sn", default=""): str,
})


class DynessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Dyness Battery."""

    VERSION = 1

    def __init__(self):
        self._api_id = None
        self._api_secret = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Schritt 1: Nur API-Zugangsdaten — Auto-Discovery."""
        if user_input is not None:
            self._api_id = user_input["api_id"]
            self._api_secret = user_input["api_secret"]
            data = {
                "api_id": self._api_id,
                "api_secret": self._api_secret,
                "api_base": "https://open-api.dyness.com",
            }
            await self.async_set_unique_id(str(uuid.uuid4()))
            return self.async_create_entry(title="Dyness Battery", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "manual_link": "manual"
            },
        )

    async def async_step_manual(self, user_input=None) -> FlowResult:
        """Schritt 2 (optional): Manuelle Eingabe der Seriennummern."""
        errors = {}

        if user_input is not None:
            data = {
                "api_id": user_input["api_id"],
                "api_secret": user_input["api_secret"],
                "api_base": "https://open-api.dyness.com",
                "device_sn": user_input["device_sn"],
                "dongle_sn": user_input.get("dongle_sn") or None,
            }
            await self.async_set_unique_id(str(uuid.uuid4()))
            return self.async_create_entry(title="Dyness Battery", data=data)

        # API ID vorausfüllen falls bereits eingegeben
        schema = vol.Schema({
            vol.Required("api_id", default=self._api_id or ""): str,
            vol.Required("api_secret", default=self._api_secret or ""): str,
            vol.Required("device_sn"): str,
            vol.Optional("dongle_sn", default=""): str,
        })

        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
        )

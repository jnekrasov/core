"""Support for Freebox base features."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CATEGORY_TO_MODEL, DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


class FreeboxHomeEntity(Entity):
    """Representation of a Freebox base entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        router: FreeboxRouter,
        node: dict[str, Any],
        sub_node: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a Freebox Home entity."""
        self._hass = hass
        self._router = router
        self._node = node
        self._sub_node = sub_node
        self._id = node["id"]
        self._device_name = node["label"].strip()
        self._attr_name = self._device_name
        self._attr_unique_id = f"{self._router.mac}-node_{self._id}"

        if sub_node is not None:
            self._attr_name += " " + sub_node["label"].strip()
            self._attr_unique_id += "-" + sub_node["name"].strip()

        self._available = True
        self._firmware = node["props"].get("FwVersion")
        self._manufacturer = "Freebox SAS"
        self._remove_signal_update: Any

        self._model = CATEGORY_TO_MODEL.get(node["category"])
        if self._model is None:
            if node["type"].get("inherit") == "node::rts":
                self._manufacturer = "Somfy"
                self._model = CATEGORY_TO_MODEL.get("rts")
            elif node["type"].get("inherit") == "node::ios":
                self._manufacturer = "Somfy"
                self._model = CATEGORY_TO_MODEL.get("iohome")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            manufacturer=self._manufacturer,
            model=self._model,
            name=self._device_name,
            sw_version=self._firmware,
            via_device=(
                DOMAIN,
                router.mac,
            ),
        )

    async def async_update_signal(self):
        """Update signal."""
        self._node = self._router.home_devices[self._id]
        # Update name
        if self._sub_node is None:
            self._attr_name = self._node["label"].strip()
        else:
            self._attr_name = (
                self._node["label"].strip() + " " + self._sub_node["label"].strip()
            )
        self.async_write_ha_state()

    async def set_home_endpoint_value(self, command_id: Any, value=None) -> None:
        """Set Home endpoint value."""
        if command_id is None:
            _LOGGER.error("Unable to SET a value through the API. Command is None")
            return
        await self._router.home.set_home_endpoint_value(
            self._id, command_id, {"value": value}
        )

    def get_command_id(self, nodes, name) -> int | None:
        """Get the command id."""
        node = next(
            filter(lambda x: (x["name"] == name), nodes),
            None,
        )
        if not node:
            _LOGGER.warning("The Freebox Home device has no value for: %s", name)
            return None
        return node["id"]

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.remove_signal_update(
            async_dispatcher_connect(
                self._hass,
                self._router.signal_home_device_update,
                self.async_update_signal,
            )
        )

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self._remove_signal_update()

    def remove_signal_update(self, dispacher: Any):
        """Register state update callback."""
        self._remove_signal_update = dispacher

    def get_value(self, ep_type, name):
        """Get the value."""
        node = next(
            filter(
                lambda x: (x["name"] == name and x["ep_type"] == ep_type),
                self._node["show_endpoints"],
            ),
            None,
        )
        if not node:
            _LOGGER.warning(
                "The Freebox Home device has no node for: " + ep_type + "/" + name
            )
            return None
        return node.get("value")

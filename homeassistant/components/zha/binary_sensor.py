"""Binary sensors on Zigbee Home Automation networks."""
import functools
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_MOVING,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_VIBRATION,
    DOMAIN,
    BinarySensorDevice,
)
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import discovery
from .core.const import (
    CHANNEL_ACCELEROMETER,
    CHANNEL_OCCUPANCY,
    CHANNEL_ON_OFF,
    CHANNEL_ZONE,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

# Zigbee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000D: DEVICE_CLASS_MOTION,
    0x0015: DEVICE_CLASS_OPENING,
    0x0028: DEVICE_CLASS_SMOKE,
    0x002A: DEVICE_CLASS_MOISTURE,
    0x002B: DEVICE_CLASS_GAS,
    0x002D: DEVICE_CLASS_VIBRATION,
}

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN] = []

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


class BinarySensor(ZhaEntity, BinarySensorDevice):
    """ZHA BinarySensor."""

    DEVICE_CLASS = None

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel = channels[0]
        self._device_class = self.DEVICE_CLASS

    async def get_device_class(self):
        """Get the HA device class from the channel."""
        pass

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.get_device_class()
        await self.async_accept_signal(
            self._channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        super().async_restore_last_state(last_state)
        self._state = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on based on the state machine."""
        if self._state is None:
            return False
        return self._state

    @property
    def device_class(self) -> str:
        """Return device class from component DEVICE_CLASSES."""
        return self._device_class

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Set the state."""
        self._state = bool(value)
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Attempt to retrieve on off state from the binary sensor."""
        await super().async_update()
        attribute = getattr(self._channel, "value_attribute", "on_off")
        self._state = await self._channel.get_attribute_value(attribute)


@STRICT_MATCH(channel_names=CHANNEL_ACCELEROMETER)
class Accelerometer(BinarySensor):
    """ZHA BinarySensor."""

    DEVICE_CLASS = DEVICE_CLASS_MOVING


@STRICT_MATCH(channel_names=CHANNEL_OCCUPANCY)
class Occupancy(BinarySensor):
    """ZHA BinarySensor."""

    DEVICE_CLASS = DEVICE_CLASS_OCCUPANCY


@STRICT_MATCH(channel_names=CHANNEL_ON_OFF)
class Opening(BinarySensor):
    """ZHA BinarySensor."""

    DEVICE_CLASS = DEVICE_CLASS_OPENING


@STRICT_MATCH(channel_names=CHANNEL_ZONE)
class IASZone(BinarySensor):
    """ZHA IAS BinarySensor."""

    async def get_device_class(self) -> None:
        """Get the HA device class from the channel."""
        zone_type = await self._channel.get_attribute_value("zone_type")
        self._device_class = CLASS_MAPPING.get(zone_type)

    async def async_update(self):
        """Attempt to retrieve on off state from the binary sensor."""
        await super().async_update()
        value = await self._channel.get_attribute_value("zone_status")
        if value is not None:
            self._state = value & 3

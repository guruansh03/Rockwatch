"""ThermalSensorAgent: daily Tmax/Tmin per zone from the cached archive."""
from rockwatch.agents.sensor_rain import RainSensorAgent


class ThermalSensorAgent(RainSensorAgent):
    name = "sensor_thermal"
    topic_out = "sensor.thermal"
    fields = ["temperature_2m_max", "temperature_2m_min"]

    def __init__(self, ctx, agent_id=None, **kw):
        super().__init__(ctx, agent_id or "sensor_thermal", group=0, n_groups=1)

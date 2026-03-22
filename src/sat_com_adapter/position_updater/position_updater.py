import struct

from sat_com_application.simulation_manager import SimulationManager


class PositionUpdater:
    def __init__(self, simulation_manager: SimulationManager):
        self._sat_index_map = {}
        self.simulation_manager = simulation_manager

    def build_index_map(self):
        """
        Call this once after satellites are loaded.
        Sends the mapping to the client via Socket.IO for decoding.
        """
        satellites = self.simulation_manager.get_satellites()
        self._sat_index_map = {
            sat.topology_uniq_id: idx for idx, sat in enumerate(satellites)
        }
        return self._sat_index_map  # emit this to client on handshake

    def pack_positions_binary(self) -> bytes:
        """
        Packs all satellite positions into a compact binary buffer.

        Buffer layout:
          [0:4]   uint32  - unix timestamp
          [4:5]   uint8   - version/flags (reserved)
          [5:7]   uint16  - satellite count
          Then per satellite (15 bytes each):
            uint16  - satellite index
            float32 - latitude  (degrees)
            float32 - longitude (degrees)
            float32 - altitude  (km)
            uint8   - ascending node flag (0 or 1)

        Returns:
            bytes: the packed binary buffer
        """
        satellites = list(self.simulation_manager.get_satellites())
        timestamp = int(self.simulation_manager.time_manager.current_time.timestamp())
        count = len(satellites)

        buffer = struct.pack("<IHH", timestamp, 0, count)

        SAT_FORMAT = "<Hffff B"
        for satellite in satellites:
            idx = self._sat_index_map.get(satellite.topology_uniq_id)
            if idx is None:
                continue

            lla = satellite.get_coordinates().to_longitude_latitude_altitude()
            lat, lon, alt = lla

            buffer += struct.pack(
                SAT_FORMAT,
                idx,
                float(lat),
                float(lon),
                float(alt),
                int(satellite.is_ascending()),
            )

        return buffer

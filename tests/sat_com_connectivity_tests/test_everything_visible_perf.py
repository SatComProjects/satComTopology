import cProfile
import io
import pstats
import sys
import time
from pathlib import Path
from typing import List

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sat_com_model.models import (
    GroundObject,
    Satellite,
    SpatialPosition,
    GroundObjectDomain,
    GroundStation,
    MovementModel,
)
from sat_com_connectivity.ground_object_to_space_connectivity.strategies import (
    ConnectToEverythingVisibleStrategy,
)
import datetime


class MockMovementModel(MovementModel):
    """Simple mock movement model for testing"""

    def __init__(self, lat: float, lon: float, alt: float):
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)

    def get_longitude_latitude(self):
        """Return lon/lat (deprecated method)"""
        return (self.lon, self.lat)

    def get_longitude_latitude_altitude(self, delta_t: float = 0):
        """Return fixed coordinates"""
        return SpatialPosition(latitude=self.lat, longitude=self.lon, altitude=self.alt)

    def get_datetime(self):
        return self.timestamp

    def is_ascending(self) -> bool:
        return True

    def get_position_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        """Return dummy EGI position"""
        return (0.0, 0.0, 0.0)

    def get_velocity_earth_general_inertial(
        self, delta: float = 0.0
    ) -> tuple[float, float, float]:
        """Return dummy EGI velocity"""
        return (0.0, 0.0, 0.0)


def load_ground_stations(file_path: str) -> List[GroundObject]:
    """Load ground stations from the 55_ground_stations.txt file"""
    ground_stations = []

    # Create a default domain
    default_domain = GroundObjectDomain(
        identifier="test",
        type="ground_station",
        elevation_above_horizon=20,
    )

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            station_id = int(parts[0])
            name = parts[1]
            lat = float(parts[2])
            lon = float(parts[3])
            alt = float(parts[4])

            gs = GroundStation(
                topology_uniq_id=station_id,
                spatial_position_info=SpatialPosition(
                    latitude=lat,
                    longitude=lon,
                    altitude=alt,
                ),
                ground_object_domain=default_domain,
            )
            # Override after __post_init__ resets them
            gs.spatial_position.latitude = lat
            gs.spatial_position.longitude = lon
            gs.spatial_position.altitude = alt
            ground_stations.append(gs)

    return ground_stations


def create_test_satellites(num_satellites: int = 750) -> List[Satellite]:
    """Create test satellites with mock movement models"""

    satellites = []

    # Create mock satellites with simple coordinate increments
    # Simulate LEO constellation at 550km altitude
    altitude_km = 550_000  # in meters

    for sat_id in range(num_satellites):
        # Distribute satellites across orbital planes
        plane_idx = sat_id % 6  # 6 planes
        sat_in_plane = sat_id // 6

        # Simple lat/lon distribution
        lat = -53 + (plane_idx * 20)
        lon = (sat_in_plane * 360 / max(1, (num_satellites // 6))) % 360

        movement_model = MockMovementModel(lat=lat, lon=lon, alt=altitude_km)

        sat = Satellite(
            topology_uniq_id=sat_id,
            satellite_name=f"LEO_{sat_id}",
            movement_model=movement_model,
            constellation=None,
            shell=None,
        )
        satellites.append(sat)

    return satellites


def profile_everything_visible_strategy():
    """Profile the everything-visible strategy"""

    # Load ground stations
    gs_file = Path(__file__).parent / "55_ground_stations.txt"
    ground_stations = load_ground_stations(str(gs_file))
    print(f"Loaded {len(ground_stations)} ground stations")

    # Create satellites
    satellites = create_test_satellites(750)
    print(f"Created {len(satellites)} satellites")

    # Initialize strategy
    strategy = ConnectToEverythingVisibleStrategy()

    # Warm-up run
    for gs in ground_stations[:5]:
        strategy.compute_ground_object_connection_strategy(gs, satellites)

    print("\n--- Profiling everything-visible strategy ---")

    # Profile with cProfile
    pr = cProfile.Profile()
    pr.enable()

    start_time = time.time()

    # Run for all ground stations
    for gs in ground_stations:
        strategy.compute_ground_object_connection_strategy(gs, satellites)

    pr.disable()
    elapsed = time.time() - start_time

    print(f"\nTotal time for {len(ground_stations)} ground stations: {elapsed:.4f}s")
    print(f"Time per ground station: {elapsed/len(ground_stations)*1000:.2f}ms")

    # Print top functions
    print("\n--- Top 15 functions by cumulative time ---")
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(15)
    print(s.getvalue())

    print("\n--- Top 15 functions by time within function ---")
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("time")
    ps.print_stats(15)
    print(s.getvalue())


def simple_benchmark():
    """Simple timing benchmark"""

    # Load ground stations
    gs_file = Path(__file__).parent / "55_ground_stations.txt"
    ground_stations = load_ground_stations(str(gs_file))
    print(f"Loaded {len(ground_stations)} ground stations")

    # Create satellites
    satellites = create_test_satellites(750)
    print(f"Created {len(satellites)} satellites")

    # Initialize strategy
    strategy = ConnectToEverythingVisibleStrategy()

    # Warm-up
    for gs in ground_stations[:5]:
        strategy.compute_ground_object_connection_strategy(gs, satellites)

    # Time single ground station
    print("\n--- Single Ground Station Performance ---")
    start = time.time()
    result = strategy.compute_ground_object_connection_strategy(
        ground_stations[0], satellites
    )
    single_time = time.time() - start
    print(f"Single GS time: {single_time*1000:.2f}ms")
    print(f"  - New connections: {len(result.new_ground_object_connections)}")
    print(f"  - Updated links: {len(result.updated_links)}")
    print(f"  - Obsolete links: {len(result.obsolete_links)}")

    # Time all ground stations
    print("\n--- All Ground Stations Performance ---")
    start = time.time()
    for gs in ground_stations:
        strategy.compute_ground_object_connection_strategy(gs, satellites)
    total_time = time.time() - start

    print(f"Total time: {total_time:.4f}s")
    print(f"Time per GS: {total_time/len(ground_stations)*1000:.2f}ms")

    # Estimate for simulation scale
    print("\n--- Extrapolation ---")
    print(f"For each iteration with 55 GS: {total_time:.4f}s")
    print(f"For 100 iterations: {total_time*100:.2f}s")


if __name__ == "__main__":
    print("=" * 60)
    print("Everything-Visible Strategy Performance Analysis")
    print("=" * 60)

    simple_benchmark()
    print("\n" + "=" * 60)
    profile_everything_visible_strategy()

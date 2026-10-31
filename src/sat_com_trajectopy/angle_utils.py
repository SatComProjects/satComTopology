"""
Deprecated: these functions moved to `sat_com_connectivity.utils`.

They are kept as aliases that emit a FutureWarning and call the moved function,
so their results are the ones of `sat_com_connectivity.utils` (WGS72 ellipsoid).
"""

import functools
import warnings


def _moved_to_connectivity_utils(name: str):
    def decorator(_placeholder):
        @functools.wraps(_placeholder)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"sat_com_trajectopy.angle_utils.{name} has moved to "
                f"sat_com_connectivity.utils.{name}. The sat_com_trajectopy "
                "version will be removed in a future version.",
                FutureWarning,
                stacklevel=2,
            )
            # Imported here: sat_com_connectivity imports this package's siblings.
            from sat_com_connectivity import utils

            return getattr(utils, name)(*args, **kwargs)

        return wrapper

    return decorator


@_moved_to_connectivity_utils("latitude_longitude_altitude_to_x_y_z")
def latitude_longitude_altitude_to_x_y_z(lat, lon, elev):
    """Deprecated: use sat_com_connectivity.utils.latitude_longitude_altitude_to_x_y_z."""


@_moved_to_connectivity_utils("get_elevation_angle")
def get_elevation_angle(sat_coordinates, gnd_coordinates):
    """Deprecated: use sat_com_connectivity.utils.get_elevation_angle."""


@_moved_to_connectivity_utils("get_elevation_angle_and_distance")
def get_elevation_angle_and_distance(sat_coordinates, gnd_coordinates):
    """Deprecated: use sat_com_connectivity.utils.get_elevation_angle_and_distance."""


@_moved_to_connectivity_utils("ground_to_up_vector")
def ground_to_up_vector(gnd_coords):
    """Deprecated: use sat_com_connectivity.utils.ground_to_up_vector."""


@_moved_to_connectivity_utils("satellites_to_ecef")
def satellites_to_ecef(satellites):
    """Deprecated: use sat_com_connectivity.utils.satellites_to_ecef."""


@_moved_to_connectivity_utils("compute_elevations")
def compute_elevations(sat_ecef, gnd_ecef, up):
    """Deprecated: use sat_com_connectivity.utils.compute_elevations."""


@_moved_to_connectivity_utils("compute_elevations_and_distances")
def compute_elevations_and_distances(sat_ecef, gnd_ecef, up):
    """Deprecated: use sat_com_connectivity.utils.compute_elevations_and_distances."""

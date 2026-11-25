from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sat_com_constellation.utils import (
    TwoLineElement,
    generate_sso_dawn_dusk,
)
from sat_com_constellation.walker_constellation.walker_propagation import (
    generate_two_line_elements,
)


class ConstellationProperty(BaseModel):
    identifier: str


class Constellation:
    identifier: str

    generated_two_line_elements: Optional[list[TwoLineElement]] = None

    def __init__(self, constellation_property: ConstellationProperty):
        self.identifier = constellation_property.identifier


class DawnDuskSunSynchronousOrbitConstellationProperty(ConstellationProperty):
    altitude_in_km: float
    amount_of_satellite: int
    epoch: Optional[datetime] = Field(default=None)


class DawnDuskSunSynchronousOrbitConstellation(Constellation):

    def __init__(
        self,
        sun_synchronous_orbit_constellation_property: DawnDuskSunSynchronousOrbitConstellationProperty,
    ):
        super().__init__(sun_synchronous_orbit_constellation_property)

        self.altitude_in_km = (
            sun_synchronous_orbit_constellation_property.altitude_in_km
        )
        self.amount_of_satellite = (
            sun_synchronous_orbit_constellation_property.amount_of_satellite
        )

        self.epoch = sun_synchronous_orbit_constellation_property.epoch

        self.__init_constellation()

    def __init_constellation(self):
        self.generated_two_line_elements = generate_sso_dawn_dusk(
            constellation_name=self.identifier,
            number_of_satellites=self.amount_of_satellite,
            epoch=self.epoch,
            altitude_km=self.altitude_in_km,
        )

    def __get_configuration(self) -> "DawnDuskSunSynchronousOrbitConstellationData":
        return DawnDuskSunSynchronousOrbitConstellationData(
            constellation_property=DawnDuskSunSynchronousOrbitConstellationProperty(
                identifier=self.identifier,
                amount_of_satellite=self.amount_of_satellite,
                epoch=self.epoch,
                altitude_in_km=self.altitude_in_km,
            ),
            constellation_two_line_elements=self.generated_two_line_elements,
        )

    def update_constellation(self, epoch: datetime = None):
        """
            Update the constellation's epoch and LTAN hours, and regenerate the two-line elements accordingly.
        :param epoch: New epoch for the constellation. If None, the epoch will not be updated.
        :return:
        """
        if epoch is not None:
            self.epoch = epoch

        self.__init_constellation()


class DeltaDesignProperty(BaseModel):
    """Ballard options for a Walker Delta shell.

    ``mode="layout"`` keeps the configured plane count, satellites per plane,
    inclination and mean motion fixed and selects only the inter-plane phasing
    ``F``.  Input values are never changed.

    ``mode="sizing"`` co-designs the constellation: it may change the
    ``T/P/Q`` factorization, inclination and altitude.  The fast hierarchical
    search returns a design in seconds and raises the altitude when needed so
    adjacent same-plane ISLs clear the atmosphere.
    """

    method: str = "ballard"
    mode: str = "layout"
    min_elevation_deg: float = 10.0
    coverage_multiplicity: int = 1
    phasing_factors: Optional[list[int]] = None
    time_samples: int = 360
    time_refinement_rounds: int = 1
    search_effort: str = "fast"
    finalists: int = 3
    raan_offset_deg: float = 0.0
    argument_of_latitude_offset_deg: float = 0.0
    grid_points: int = 20000

    # Sizing-only fields.
    altitude_mode: str = "solve"
    altitude_km: Optional[float] = None
    max_altitude_km: Optional[float] = 5880.0
    plane_counts: Optional[list[int]] = None
    inclination_min_deg: float = 20.0
    inclination_max_deg: float = 80.0
    inclination_step_deg: float = 5.0
    inclination_refine_steps_deg: list[float] = Field(
        default_factory=lambda: [1.0, 0.1]
    )
    max_evaluations: int = 20000


class WalkerConstellationProperty(ConstellationProperty):
    identifier: str
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int
    inclination: float
    phase_difference_between_satellites: bool
    mean_revolution_per_day: float
    phasing_factor: Optional[int] = None
    design: Optional[DeltaDesignProperty] = None


class DawnDuskSunSynchronousOrbitConstellationData(BaseModel):
    constellation_property: DawnDuskSunSynchronousOrbitConstellationProperty
    constellation_two_line_elements: list[TwoLineElement]


class WalkerConstellationData(BaseModel):
    constellation_property: WalkerConstellationProperty
    constellation_two_line_elements: list[TwoLineElement]


class WalkerConstellation(Constellation):
    amount_of_orbit_plane: int
    amount_of_satellite_per_orbit_plane: int
    inclination: float

    ORBIT_SPREADING_DEGREE = 360

    def __init__(self, walker_constellation_property: WalkerConstellationProperty):
        super().__init__(walker_constellation_property)
        self.amount_of_orbit_plane = walker_constellation_property.amount_of_orbit_plane
        self.amount_of_satellite_per_orbit_plane = (
            walker_constellation_property.amount_of_satellite_per_orbit_plane
        )
        self.inclination = walker_constellation_property.inclination
        self.phase_difference_between_satellites = (
            walker_constellation_property.phase_difference_between_satellites
        )
        self.mean_revolution_per_day = (
            walker_constellation_property.mean_revolution_per_day
        )
        self.phasing_factor = walker_constellation_property.phasing_factor
        self.design_property = walker_constellation_property.design
        self.design_result = None
        self.raan_offset_degree = 0.0
        self.argument_of_latitude_offset_degree = 0.0
        self.argument_of_perigee_degree = 0.0
        self.eccentricity = 0.0001

        self.__init_constellation()

    def _apply_design(self):
        if self.design_property is not None:
            raise ValueError(
                "Numerical constellation design is only supported for Walker "
                "Delta constellations"
            )

    def __init_constellation(self):
        self._apply_design()
        self.generated_two_line_elements = generate_two_line_elements(
            constellation_name=self.identifier,
            number_of_orbits=self.amount_of_orbit_plane,
            number_of_satellites_per_plane=self.amount_of_satellite_per_orbit_plane,
            phase_difference=self.phase_difference_between_satellites,
            mean_motion_revolution_per_day=self.mean_revolution_per_day,
            eccentricity=self.eccentricity,
            inclination_degree=self.inclination,
            argument_of_perigee_degree=self.argument_of_perigee_degree,
            orbit_spreading_degree=self.ORBIT_SPREADING_DEGREE,
            phasing_factor=self.phasing_factor,
            raan_offset_degree=self.raan_offset_degree,
            argument_of_latitude_offset_degree=(
                self.argument_of_latitude_offset_degree
            ),
        )

    def __get_configuration(self) -> WalkerConstellationData:
        return WalkerConstellationData(
            constellation_property=WalkerConstellationProperty(
                identifier=self.identifier,
                amount_of_orbit_plane=self.amount_of_orbit_plane,
                amount_of_satellite_per_orbit_plane=self.amount_of_satellite_per_orbit_plane,
                inclination=self.inclination,
                phase_difference_between_satellites=self.phase_difference_between_satellites,
                mean_revolution_per_day=self.mean_revolution_per_day,
                phasing_factor=self.phasing_factor,
                design=self.design_property,
            ),
            constellation_two_line_elements=self.generated_two_line_elements,
        )


class WalkerStarConstellation(WalkerConstellation):
    ORBIT_SPREADING_DEGREE = 180


class WalkerDeltaConstellation(WalkerConstellation):
    ORBIT_SPREADING_DEGREE = 360

    def _apply_design(self):
        """Run the selected Ballard mode for this delta shell."""
        if self.design_property is None:
            return

        from sat_com_constellation.walker_constellation.ballard_design import (
            altitude_from_mean_motion_km,
            optimize_delta_constellation,
            optimize_delta_phasing,
        )

        design_property = self.design_property
        if design_property.method != "ballard":
            raise ValueError(
                "Unsupported Delta design method "
                f"{design_property.method!r}; expected 'ballard'"
            )
        if design_property.mode not in {"layout", "sizing"}:
            raise ValueError(
                "Unsupported Delta design mode "
                f"{design_property.mode!r}; expected 'layout' or 'sizing'"
            )

        if design_property.mode == "layout":
            result = optimize_delta_phasing(
                planes=self.amount_of_orbit_plane,
                satellites_per_plane=self.amount_of_satellite_per_orbit_plane,
                inclination_deg=self.inclination,
                mean_revolution_per_day=self.mean_revolution_per_day,
                min_elevation_deg=design_property.min_elevation_deg,
                coverage_multiplicity=design_property.coverage_multiplicity,
                phasing_factors=design_property.phasing_factors,
                time_samples=design_property.time_samples,
                time_refinement_rounds=design_property.time_refinement_rounds,
                search_effort=design_property.search_effort,
                raan_offset_deg=design_property.raan_offset_deg,
                argument_of_latitude_offset_deg=(
                    design_property.argument_of_latitude_offset_deg
                ),
                grid_points=design_property.grid_points,
                finalists=design_property.finalists,
            )
            self.design_result = result
            self.phasing_factor = result.phasing_factor
            return

        fixed_altitude_km = design_property.altitude_km
        if design_property.altitude_mode == "fixed" and fixed_altitude_km is None:
            fixed_altitude_km = altitude_from_mean_motion_km(
                self.mean_revolution_per_day
            )

        result = optimize_delta_constellation(
            total_satellites=(
                self.amount_of_orbit_plane * self.amount_of_satellite_per_orbit_plane
            ),
            min_elevation_deg=design_property.min_elevation_deg,
            coverage_multiplicity=design_property.coverage_multiplicity,
            altitude_mode=design_property.altitude_mode,
            fixed_altitude_km=fixed_altitude_km,
            max_altitude_km=design_property.max_altitude_km,
            plane_counts=design_property.plane_counts,
            phasing_factors=design_property.phasing_factors,
            reference_planes=self.amount_of_orbit_plane,
            reference_phasing_factor=self.phasing_factor,
            inclination_min_deg=design_property.inclination_min_deg,
            inclination_max_deg=design_property.inclination_max_deg,
            inclination_step_deg=design_property.inclination_step_deg,
            inclination_refine_steps_deg=design_property.inclination_refine_steps_deg,
            time_samples=design_property.time_samples,
            time_refinement_rounds=design_property.time_refinement_rounds,
            search_effort=design_property.search_effort,
            max_evaluations=design_property.max_evaluations,
            finalists=design_property.finalists,
            raan_offset_deg=design_property.raan_offset_deg,
            argument_of_latitude_offset_deg=(
                design_property.argument_of_latitude_offset_deg
            ),
            grid_points=design_property.grid_points,
        )

        if not result.meets_elevation_requirement:
            raise ValueError(
                "The optimized Delta geometry does not meet the requested "
                f"minimum elevation of {result.min_elevation_deg:.3f} deg at "
                f"the fixed altitude of {result.altitude_km:.1f} km "
                f"(achieved {result.achieved_min_elevation_deg:.3f} deg). "
                "Increase the altitude or use altitude_mode='solve'."
            )

        self.design_result = result
        self.amount_of_orbit_plane = result.planes
        self.amount_of_satellite_per_orbit_plane = result.satellites_per_plane
        self.inclination = result.inclination_deg
        self.phasing_factor = result.phasing_factor
        self.mean_revolution_per_day = result.mean_revolution_per_day
        self.phase_difference_between_satellites = False
        self.raan_offset_degree = result.raan_offset_deg
        self.argument_of_latitude_offset_degree = result.argument_of_latitude_offset_deg

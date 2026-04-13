import datetime

from pydantic import BaseModel, Field

from sat_com_model.models import OpticalConstraint, Satellite, InterSatelliteLink


class AssociationState(BaseModel):
    optical_constraint_a_to_b: OpticalConstraint | None = Field(default=None)
    optical_constraint_b_to_a: OpticalConstraint | None = Field(default=None)
    satellite_a: Satellite | None = Field(default=None)
    satellite_b: Satellite | None = Field(default=None)
    temporary_unavailable: bool | None = Field(default=None)
    recovery_time: datetime.datetime = Field(default=None)

    def __has_optical_constraints(self) -> bool:
        return (
            self.optical_constraint_a_to_b is not None
            or self.optical_constraint_b_to_a is not None
        )

    def get_link_source_and_destination_optical_constraint_ordered(
        self, link: InterSatelliteLink
    ) -> tuple[OpticalConstraint | None, OpticalConstraint | None]:

        if not self.__has_optical_constraints():
            return None, None

        if self.satellite_a is None or self.satellite_b is None:
            raise ValueError(
                "Satellite a and b not provided, cannot identify constraints"
            )

        if (
            link.get_satellite_source() == self.satellite_a
            and link.get_satellite_destination() == self.satellite_b
        ):
            return self.optical_constraint_a_to_b, self.optical_constraint_b_to_a
        elif (
            link.get_satellite_source() == self.satellite_b
            and link.get_satellite_destination() == self.satellite_a
        ):
            return self.optical_constraint_b_to_a, self.optical_constraint_a_to_b
        else:
            raise ValueError("Incoherence between satellites")

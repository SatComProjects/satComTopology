from sat_com_model.models import SpatialPosition


def create_point(sphere_name: str, position: SpatialPosition, color: str = "BLACK"):
    return (
        "\n"
        + "    viewer.entities.add({\n"
        + f'      name: "{sphere_name}",\n'
        + f'      position: Cesium.Cartesian3.fromDegrees("{position.longitude}","{position.latitude}", "{position.altitude}"),\n'
        + "      ellipsoid: {\n"
        + "        radii: new Cesium.Cartesian3(30000.0, 30000.0, 30000.0),\n"
        + f"        material: Cesium.Color.{color},\n"
        + "        outline: true,\n"
        + "        outlineColor: Cesium.Color.BLACK,\n"
        + "          },\n"
        + "    });\n"
        + "    "
    )


def create_line(
    position_a: SpatialPosition,
    position_b: SpatialPosition,
    a_name: str = "A",
    b_name: str = "B",
    color: str = "GREEN",
):
    link = (
        "\n"
        + "       viewer.entities.add({\n"
        + f'          name: "Link from {a_name} to {b_name}",\n'
        + "           polyline: {\n"
        + "            positions: Cesium.Cartesian3.fromDegreesArrayHeights([\n"
        + f"              {position_a.longitude},\n"
        + f"              {position_a.latitude},\n"
        + f"              {position_a.altitude},\n"
        + f"              {position_b.longitude},\n"
        + f"              {position_b.latitude},\n"
        + f"              {position_b.altitude},\n"
        + "            ]),\n"
        + "            width: 10,\n"
        + "            arcType: Cesium.ArcType.NONE,\n"
        + f"           material: Cesium.Color.{color},\n"
        + "          },\n"
        + "       });\n"
    )

    return link

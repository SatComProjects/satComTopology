from sat_com_model.models import SpatialPosition


def create_point(
    sphere_name: str,
    position: SpatialPosition,
    color: str = "BLACK",
    radius: float = 30000.0,
    description: str = "",
):
    return (
        "\n"
        + "    viewer.entities.add({\n"
        + f'      name: "Topology object id: {sphere_name}",\n'
        + f"      position: Cesium.Cartesian3.fromDegrees({position.longitude},{position.latitude}, {position.altitude * 1000}),\n"
        + f'      description: "{description}",\n'
        + "      ellipsoid: {\n"
        + f"        radii: new Cesium.Cartesian3({radius}, {radius},{radius}),\n"
        + f"        material: Cesium.Color.{color}.withAlpha(0.75),\n"
        + "        outline: true,\n"
        + f"        outlineColor: Cesium.Color.{color},\n"
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
    description: str = "",
):
    link = (
        "\n"
        + "       viewer.entities.add({\n"
        + f'          name: "Link from {a_name} to {b_name}",\n'
        + f'          description: "{description}",\n'
        + "           polyline: {\n"
        + "            positions: Cesium.Cartesian3.fromDegreesArrayHeights([\n"
        + f"              {position_a.longitude},\n"
        + f"              {position_a.latitude},\n"
        + f"              {position_a.altitude * 1000},\n"
        + f"              {position_b.longitude},\n"
        + f"              {position_b.latitude},\n"
        + f"              {position_b.altitude * 1000},\n"
        + "            ]),\n"
        + "            width: 1,\n"
        + "            arcType: Cesium.ArcType.NONE,\n"
        + f"           material: Cesium.Color.{color},\n"
        + "          },\n"
        + "       });\n"
    )

    return link


def create_background_color(color: str = "WHITESMOKE") -> str:
    return f"scene.backgroundColor = Cesium.Color.{color};"


def create_polygon_on_earth_surface(
    coordinate_list: list, color="RED", description: str = str()
) -> str:
    coordinate_list_to_str = ", ".join(
        str(coordinate) for coordinate in coordinate_list
    )

    html = "var polygonOutlineInstance = new Cesium.GeometryInstance({\n"
    html += "  geometry: new Cesium.PolygonOutlineGeometry({\n"
    html += "    polygonHierarchy: {\n"
    html += f"      positions: Cesium.Cartesian3.fromDegreesArray([{coordinate_list_to_str}]),\n"
    html += "    },\n"
    html += "  }),\n"
    html += "});\n"
    html += "scene.primitives.add(new Cesium.Primitive({\n"
    html += "  geometryInstances: polygonOutlineInstance,\n"
    html += "  appearance: new Cesium.PerInstanceColorAppearance({\n"
    html += "    flat: true,\n"
    html += "    renderState: {\n"
    html += "      depthTest: {\n"
    html += "        enabled: true\n"
    html += "      },\n"
    html += "      lineWidth: Math.min(2.0, scene.maximumAliasedLineWidth)\n"
    html += "    }\n"
    html += "  }),\n"
    html += "}));\n"

    # html = "var polygon = new Cesium.PolygonOutlineGeometry({\n"
    # html += "  polygonHierarchy: {\n"
    # html += f"    positions: Cesium.Cartesian3.fromDegreesArray([{coordinate_list_to_str}]),\n"
    # html += "  },\n"
    # html += "});\n"
    # html += "var geometry = Cesium.PolygonOutlineGeometry.createGeometry(polygon);\n"
    # html += "var entity = viewer.entities.add({\n"
    # html += '  name: "Polygon Outline",\n'
    # html += f'  description: "{description}",\n'
    # html += "  position: geometry.center,\n"
    # html += "  polygon: {\n"
    # html += "    hierarchy: polygon.polygonHierarchy,\n"
    # html += f"    outline: true,\n"
    # html += f"    outlineColor: Cesium.Color.{color},\n"
    # html += "  },\n"
    # html += "});\n"
    return html

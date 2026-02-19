import json

from sat_com_adapter.cesium_renderer.utils import color_to_rgba
from sat_com_model.models import SpatialPosition


def get_color_js(color):
    if color.startswith("COLOR_GREEN_TO_RED_"):
        color_rgba = color_to_rgba(color)
        if len(color_rgba) == 4:
            return (
                f"new Cesium.Color("
                f"Cesium.Color.byteToFloat({color_rgba[0]}), "
                f"Cesium.Color.byteToFloat({color_rgba[1]}), "
                f"Cesium.Color.byteToFloat({color_rgba[2]}), "
                f"Cesium.Color.byteToFloat({color_rgba[3]})"
                f")"
            )
        else:
            return "Incorrect Color:" + color + "  " + str(color_rgba)
    else:
        return f"Cesium.Color.{color}"


class CesiumElementFactory:
    def create_line(
        self,
        position_a: SpatialPosition,
        position_b: SpatialPosition,
        cesium_uniq_identifier: str,
        a_name: str = "A",
        b_name: str = "B",
        width: float = 1.0,
        color: str = "GREEN",
        description: str = "",
        on_ground: bool = False,
        properties=None,
    ):
        pass

    def create_sphere(
        self,
        sphere_name: str,
        position: SpatialPosition,
        cesium_uniq_identifier: str,
        color: str = "BLACK",
        radius: float = 30000.0,
        description: str = "",
        properties=None,
    ):
        pass


class CesiumCZMLElementFactory(CesiumElementFactory):
    def create_sphere(
        self,
        sphere_name: str,
        position: SpatialPosition,
        cesium_uniq_identifier: str,
        color: str = "BLACK",
        radius: float = 30000.0,
        description: str = "",
        properties=None,
    ) -> dict:
        """
        Create a CZML dictionary for a sphere.

        :param sphere_name: Name of the sphere.
        :param position: Position of the sphere.
        :param cesium_uniq_identifier: Unique identifier for the sphere.
        :param color: Color of the sphere. Default is BLACK.
        :param radius: Radius of the sphere. Default is 30000.
        :param description: Description of the sphere in HTML. Default is empty.
        :param properties: Additional properties of the sphere.
        :return: CZML dictionary representing the sphere.
        """
        czml_dict = {
            "id": cesium_uniq_identifier,
            "name": f"Topology object: {sphere_name}",
            "position": {
                "cartographicDegrees": [
                    position.longitude,
                    position.latitude,
                    position.altitude,
                ]
            },
            "description": description,
            "ellipsoid": {
                "radii": {"cartesian": [radius, radius, radius]},
                "material": {
                    "solidColor": {"color": {"rgba": color_to_rgba(color, alpha=0.75)}}
                },
                "outline": True,
                "outlineColor": {"rgba": color_to_rgba(color)},
            },
        }

        if properties:
            czml_dict["properties"] = json.dumps(properties)

        return czml_dict

    def create_line(
        self,
        position_a: SpatialPosition,
        position_b: SpatialPosition,
        cesium_uniq_identifier: str,
        a_name: str = "A",
        b_name: str = "B",
        width: float = 1.0,
        color: str = "GREEN",
        description: str = "",
        on_ground: bool = False,
        properties=None,
    ) -> dict:
        """
        Create a CZML dictionary for a line.
        :param on_ground:
        :param width: Link width of the line.
        :param position_a: Starting position of the line.
        :param position_b: Ending position of the line.
        :param cesium_uniq_identifier: Unique identifier for the line.
        :param a_name: Name of the first line.
        :param b_name: Name of the second line.
        :param color: Color of the line.
        :param description: Description of the line.
        :param properties: Additional properties of the line.
        :return: CZML dictionary representing the line.
        """

        arc_type = "GEODESIC" if on_ground else "NONE"
        czml_dict = {
            "id": cesium_uniq_identifier,
            "name": f"Link from {a_name} to {b_name}",
            "description": description,
            "polyline": {
                "positions": {
                    "cartographicDegrees": [
                        position_a.longitude,
                        position_a.latitude,
                        position_a.altitude,
                        position_b.longitude,
                        position_b.latitude,
                        position_b.altitude,
                    ]
                },
                "width": width,
                "arcType": arc_type,
                "material": {"solidColor": {"color": {"rgba": color_to_rgba(color)}}},
            },
        }

        if properties:
            czml_dict["properties"] = json.dumps(properties)

        return czml_dict


def get_full_html(cesium_token: str, elements: str):
    return '<html lang="en">\n <head>\n <meta charset="utf-8">\n <script src="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Cesium.js">\n</script>\n <link href="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Widgets/widgets.css" rel="stylesheet">\n <title>\nCesium Viewer</title>\n </head>\n <body>\n <div id="cesiumContainer" style="width: 100%; height:100%">\n</div>\n <script>\n Cesium.Ion.defaultAccessToken = "{cesium_token}";\n const viewer = new Cesium.Viewer("cesiumContainer", {{ skyBox: false, skyAtmosphere: false, baseLayerPicker: true, geocoder: false, homeButton: false, infoBox: true, sceneModePicker: false, navigationHelpButton: false, shouldAnimate: true, contextOptions: {{ webgl: {{ alpha: true }} }} }});\n  var infoBox = new Cesium.InfoBox(\'cesiumContainer\');\n  var scene = viewer.scene;\n {get_elements} </script>\n </body>\n'.format(
        cesium_token=cesium_token, get_elements=elements
    )


def create_background_color(color: str = "WHITESMOKE") -> str:
    """

    :rtype: object
    """
    return f"scene.backgroundColor = Cesium.Color.{color};"


def create_polygon_on_earth_surface_js(
    coordinate_list: list, color="RED", description: str = str()
) -> str:
    coordinate_list_to_str = ", ".join(
        str(coordinate) for coordinate in coordinate_list
    )

    html = "viewer.entities.add({\n"
    html += f'  name: "Polygon",\n'
    html += f'  description: "{description}",\n'
    html += "  polygon: {\n"
    html += f"    hierarchy: Cesium.Cartesian3.fromDegreesArray([{coordinate_list_to_str}]),\n"
    html += f"    material: Cesium.Color.{color},\n"
    html += "  },\n"
    html += "});\n"

    return html


def create_polygon_on_earth_surface_czml(
    coordinate_list: list,
    color="RED",
    description: str = str(),
    name: str = "Polygon Area",
    properties=None,
) -> dict:
    coordinate_list_to_str = ", ".join(
        str(coordinate) for coordinate in coordinate_list
    )

    czml_dict = {
        "id": name + "_" + coordinate_list_to_str.replace(",", "_").replace(" ", ""),
        "name": name,
        "description": description,
        "polygon": {
            "positions": {"cartographicDegrees": coordinate_list},
            "material": {
                "solidColor": {"color": {"rgba": color_to_rgba(color, alpha=0.33)}}
            },
        },
    }

    if properties:
        czml_dict["properties"] = json.dumps(properties)

    return czml_dict


class CesiumJavaScriptElementFactory(CesiumElementFactory):
    def create_sphere(
        self,
        sphere_name: str,
        position: SpatialPosition,
        cesium_uniq_identifier: str,
        color: str = "BLACK",
        radius: float = 30000.0,
        description: str = "",
        properties=None,
    ) -> str:
        """
        Create a sphere on the cesium render.

        :param sphere_name: Name of the sphere.
        :param position: Position of the sphere.
        :param cesium_uniq_identifier: Unique identifier for the sphere.
        :param color: Color of the sphere. Default is BLACK.
        :param radius: Radius of the sphere. Default is 30000.
        :param description: Description of the sphere in HTML. Default is empty.
        :param properties: Additional properties of the sphere.
        :return:
        """
        return (
            "\n"
            + "    viewer.entities.add({\n"
            + f'      name: "Topology object: {sphere_name}",\n'
            + f'      id: "{cesium_uniq_identifier}",\n'
            + f"      position: Cesium.Cartesian3.fromDegrees({position.longitude},{position.latitude}, {position.altitude}),\n"
            + f'      description: "{description}",\n'
            + f"      properties: {json.dumps(properties) if properties is not None else str(dict())},\n"
            + "      ellipsoid: {\n"
            + f"        radii: new Cesium.Cartesian3({radius}, {radius},{radius}),\n"
            + f"        material: Cesium.Color.{color}.withAlpha(0.75),\n"
            + "         outline: true,\n"
            + f"        outlineColor: Cesium.Color.{color},\n"
            + "         },\n"
            + "    });\n"
            + "    "
        )

    def create_line(
        self,
        position_a: SpatialPosition,
        position_b: SpatialPosition,
        cesium_uniq_identifier: str,
        a_name: str = "A",
        b_name: str = "B",
        width: float = 1.0,
        color: str = "GREEN",
        description: str = "",
        on_ground: bool = False,
        properties=None,
    ):
        """
        Create a line on the cesium render.
        :param on_ground:
        :param width:
        :param position_a: Starting position of the line.
        :param position_b: Ending position of the line.
        :param cesium_uniq_identifier: Unique identifier for the line.
        :param a_name: Name of the first line.
        :param b_name: Name of the second line.
        :param color: Color of the line.
        :param description: Description of the line.
        :param properties: Additional properties of the sphere.
        :return:
        """

        arc_type = "GEODESIC" if on_ground else "NONE"
        link = (
            "\n"
            + "       viewer.entities.add({\n"
            + f'        name: "Link from {a_name} to {b_name}",\n'
            + f'        id: "{cesium_uniq_identifier}",\n'
            + f'        description: "{description}",\n'
            + f"        properties: {json.dumps(properties)  if properties is not None else str(dict())},\n"
            + "         polyline: {\n"
            + "         positions: Cesium.Cartesian3.fromDegreesArrayHeights([\n"
            + f"              {position_a.longitude},\n"
            + f"              {position_a.latitude},\n"
            + f"              {position_a.altitude},\n"
            + f"              {position_b.longitude},\n"
            + f"              {position_b.latitude},\n"
            + f"              {position_b.altitude},\n"
            + "            ]),\n"
            + "          width: 1,\n"
            + f"          arcType: Cesium.ArcType.{arc_type},\n"
            + f"         material: {get_color_js(color)},\n"
            + "          },\n"
            + "       });\n"
        )

        return link

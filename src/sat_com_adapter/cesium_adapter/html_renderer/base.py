def get_base_html():
    return "\n"
    '                <html lang="en">\n'
    "                <head>\n"
    '                <meta charset="utf-8">\n'
    '                <script src="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Cesium.js"></script>\n'
    '                <link href="https://cesium.com/downloads/cesiumjs/releases/1.110/Build/Cesium/Widgets/widgets.css" rel="stylesheet">\n'
    "\n"
    '                <script src="/output_lab/cesium_project/display_two_points.js"></script>\n'
    "            <title>Cesium Viewer</title>\n"
    "            </head>\n"
    "            <body>\n"
    '            <div id="cesiumContainer" style="width: 100%; height:100%"></div>\n'
    "            <script>\n"
    "\n"
    '            Cesium.Ion.defaultAccessToken = "{cesium_token}";\n'
    "\n"
    '            const viewer = new Cesium.Viewer("cesiumContainer",\n'
    "                                             {\n"
    "                                                 skyBox: false,\n"
    "                                                 skyAtmosphere: false,\n"
    "                                                 baseLayerPicker: true,\n"
    "                                                 geocoder: false,\n"
    "                                                 homeButton: false,\n"
    "                                                 infoBox: false,\n"
    "                                                 sceneModePicker: false,\n"
    "                                                 navigationHelpButton: false,\n"
    "                                                 shouldAnimate: true,\n"
    "                                                 contextOptions: {\n"
    "                                                     webgl: {\n"
    "                                                         alpha: true\n"
    "                                                     }\n"
    "                                                 }\n"
    "                                             });\n"
    "            var scene = viewer.scene;\n"
    "            scene.backgroundColor = Cesium.Color.WHITESMOKE;\n"
    "\n"
    "            {get_elements}\n"
    "\n"
    "        </script>\n"
    "\n"
    "        </body>\n"
    "        "

# CesiumProperty Configuration Documentation

## Overview

`CesiumProperty` defines rendering and visualization settings for satellites, shells, ground objects, and links in the Cesium viewer.
It is a Pydantic model, so it can be configured using JSON.

---

## Top-Level Fields

| Field                          | Type          | Default | Description                                            |
| ------------------------------ | ------------- | ------- | ------------------------------------------------------ |
| `shell_to_display`             | list[str]     | `[]`    | List of shell identifiers to render. Empty = show all. |
| `display_ground_objects`       | bool          | `true`  | Toggle ground object rendering.                        |
| `display_ground_links`         | bool          | `true`  | Toggle links between ground objects.                   |
| `display_satellite`            | bool          | `true`  | Toggle satellite rendering.                            |
| `display_inter_satellite_link` | bool          | `true`  | Toggle satellite-to-satellite links.                   |
| `link_flow_width`              | float         | `1`     | Width of flow overlay lines.                           |
| `cesium_token`                 | string | null | `null`  | Cesium access token.                                   |
| `background_color`             | string | null | `null`  | Scene background color.                                |

---

## Renderer Defaults

### Ground Object Renderer — `cesium_renderer_ground_object_property`

| Field                      | Type       | Default     | Description             |
| -------------------------- | ---------- | ----------- | ----------------------- |
| `ground_object_color`      | str        | `ORCHID`    | Color of ground objects |
| `ground_object_size`       | float      | `5000`      | Size of ground objects  |
| `ground_object_link_color` | str        | `FIREBRICK` | Link color              |
| `ground_object_link_width` | float      | `1`         | Link width              |
| `ground_object_model_path` | str | null | `null`      | Optional 3D model path  |

---

### Shell Renderer — `cesium_renderer_shell_property`

| Field                                 | Type       | Default          | Description                    |
| ------------------------------------- | ---------- | ---------------- | ------------------------------ |
| `ascending_satellite_color`           | str        | `LIGHTSTEELBLUE` | Color of ascending satellites  |
| `descending_satellite_color`          | str        | `KHAKI`          | Color of descending satellites |
| `satellites_size`                     | float      | `30000`          | Satellite size                 |
| `adjacent_inter_satellite_link_color` | str        | `PERU`           | Adjacent ISL color             |
| `orbital_inter_satellite_link_color`  | str        | `YELLOWGREEN`    | Orbital ISL color              |
| `inter_satellite_link_width`          | float      | `1`              | ISL width                      |
| `link_flow_width`                     | float      | `1`              | Flow overlay width             |
| `route_link_color`                    | str        | `DARKRED`        | Route link color               |
| `route_link_size`                     | float      | `2`              | Route link width               |
| `satellite_model_path`                | str | null | `null`           | Optional satellite 3D model    |

---

## Custom Overrides

### Shell Customization — `shell_custom_properties`

Overrides renderer properties for specific shells.

```
ShellCustomProperty
- shell_identifier: str
- cesium_property: CesiumRendererShellProperty
```

---

### Ground Domain Customization — `ground_object_domain_custom_properties`

Overrides ground object renderer per domain.

```
GroundObjectDomainCustomProperty
- ground_object_domain: str
- cesium_property: CesiumRendererGroundObjectProperty
```

---

### Static Ground Connectivity Defaults — `cesium_static_ground_property_connectivity`

| Field                                       | Type  | Default | Description |
| ------------------------------------------- | ----- | ------- | ----------- |
| `ground_object_to_ground_object_link_color` | str   | `RED`   | Link color  |
| `ground_object_to_ground_object_link_width` | float | `1`     | Link width  |

---

### Custom Connectivity Overrides — `cesium_static_custom_ground_connectivity_properties`

Base type:

```
CesiumRendererCustomStaticGroundObjectConnectivity
- cesium_static_ground_object_connectivity_property
```

Specializations:

**Domain-to-Domain**

```
CesiumRendererDomainToDomainGroundObjectConnectivity
- domain_a: str
- domain_b: str
```

**Type-to-Type**

```
CesiumRendererGroundObjectTypeToTypeRendererCustomProperty
- type_a: str
- type_b: str
```

---

# JSON Configuration Reference

## Minimal Example

```json
{
  "shell_to_display": [],
  "display_ground_objects": true,
  "display_ground_links": true,
  "display_satellite": true,
  "display_inter_satellite_link": true
}
```

---

## Full Example

```json
{
  "shell_to_display": ["shellA", "shellB"],
  "display_ground_objects": true,
  "display_ground_links": true,
  "display_satellite": true,
  "display_inter_satellite_link": true,
  "link_flow_width": 2,
  "cesium_token": "YOUR_TOKEN",

  "cesium_renderer_ground_object_property": {
    "ground_object_color": "ORCHID",
    "ground_object_size": 5000,
    "ground_object_link_color": "FIREBRICK",
    "ground_object_link_width": 1,
    "ground_object_model_path": null
  },

  "cesium_renderer_shell_property": {
    "ascending_satellite_color": "LIGHTSTEELBLUE",
    "descending_satellite_color": "KHAKI",
    "satellites_size": 30000,
    "adjacent_inter_satellite_link_color": "PERU",
    "orbital_inter_satellite_link_color": "YELLOWGREEN",
    "inter_satellite_link_width": 1,
    "link_flow_width": 1,
    "route_link_color": "DARKRED",
    "route_link_size": 2,
    "satellite_model_path": null
  },

  "shell_custom_properties": [
    {
      "shell_identifier": "shellA",
      "cesium_property": {
        "ascending_satellite_color": "BLUE",
        "descending_satellite_color": "GREEN",
        "satellites_size": 35000,
        "adjacent_inter_satellite_link_color": "WHITE",
        "orbital_inter_satellite_link_color": "GRAY",
        "inter_satellite_link_width": 2,
        "link_flow_width": 1,
        "route_link_color": "RED",
        "route_link_size": 3,
        "satellite_model_path": null
      }
    }
  ],

  "ground_object_domain_custom_properties": [
    {
      "ground_object_domain": "military",
      "cesium_property": {
        "ground_object_color": "BLACK",
        "ground_object_size": 7000,
        "ground_object_link_color": "GRAY",
        "ground_object_link_width": 2,
        "ground_object_model_path": null
      }
    }
  ],

  "cesium_static_ground_property_connectivity": {
    "ground_object_to_ground_object_link_color": "RED",
    "ground_object_to_ground_object_link_width": 1
  },

  "cesium_static_custom_ground_connectivity_properties": [
    {
      "cesium_static_ground_object_connectivity_property": {
        "ground_object_to_ground_object_link_color": "BLUE",
        "ground_object_to_ground_object_link_width": 3
      }
    }
  ],

  "background_color": "BLACK"
}
```

---

## Cesium Color
All color fields accept any valid Cesium color string, including named colors (e.g., "RED", "BLUE") and RGBA arrays (e.g., `[255, 0, 0, 255]` for opaque red).
Cesium Color docs [here](../CESIUM_COLOR.md).

## Notes

* All color values must be valid Cesium-supported color strings.
* Any omitted field automatically falls back to its default.
* Custom property lists override defaults selectively rather than replacing them globally.

# Supported Color Definitions

## Overview

Colors used in Cesium configuration fields must be provided as **uppercase color names** from the supported list below.

The rendering engine converts a color name into an **RGBA array**:

```
[R, G, B, A]
```

Where:

* **R, G, B** range from `0–255`
* **A (alpha)** is calculated as:

```
alpha * 255
```

Default alpha = `1.0` → fully opaque.

---

## Function Behavior

```
color_to_rgba(color: str=None, alpha: float=1.0, force_color=None) -> list
```

### Parameters

| Name          | Type  | Description                       |
| ------------- | ----- | --------------------------------- |
| `color`       | str   | Name of supported color           |
| `alpha`       | float | Opacity multiplier (0–1)          |
| `force_color` | list  | If provided, overrides everything |

### Priority Logic

1. If `force_color` is provided → return it directly
2. Else → lookup `color` name
3. Apply alpha scaling

---

## Example Conversions

| Input                                    | Output               |
| ---------------------------------------- | -------------------- |
| `color_to_rgba("RED")` →                 | `[255, 0, 0, 255]`   |
| `color_to_rgba("BLUE", 0.5)` →           | `[0, 0, 255, 127.5]` |
| `color_to_rgba(force_color=[1,2,3,4])` → | `[1,2,3,4]`          |

---

## Supported Color Names

The following names are valid values for any color field:

```
ALICEBLUE
ANTIQUEWHITE
AQUA
AQUAMARINE
AZURE
BEIGE
BISQUE
BLACK
BLANCHEDALMOND
BLUE
BLUEVIOLET
BROWN
BURLYWOOD
CADETBLUE
CHARTREUSE
CHOCOLATE
CORAL
CORNFLOWERBLUE
CORNSILK
CRIMSON
CYAN
DARKBLUE
DARKCYAN
DARKGOLDENROD
DARKGRAY
DARKGREEN
DARKKHAKI
DARKMAGENTA
DARKOLIVEGREEN
DARKORANGE
DARKORCHID
DARKRED
DARKSALMON
DARKSEAGREEN
DARKSLATEBLUE
DARKSLATEGRAY
DARKTURQUOISE
DARKVIOLET
DEEPPINK
DEEPSKYBLUE
DIMGRAY
DODGERBLUE
FIREBRICK
FLORALWHITE
FORESTGREEN
FUCHSIA
GAINSBORO
GHOSTWHITE
GOLD
GOLDENROD
GRAY
GREEN
GREENYELLOW
HONEYDEW
HOTPINK
INDIANRED
INDIGO
IVORY
KHAKI
LAVENDER
LAVENDAR_BLUSH
LAWNGREEN
LEMONCHIFFON
LIGHTBLUE
LIGHTCORAL
LIGHTCYAN
LIGHTGOLDENRODYELLOW
LIGHTGRAY
LIGHTGREEN
LIGHTPINK
LIGHTSEAGREEN
LIGHTSKYBLUE
LIGHTSLATEGRAY
LIGHTSTEELBLUE
LIGHTYELLOW
LIME
LIMEGREEN
LINEN
MAGENTA
MAROON
MEDIUMAQUAMARINE
MEDIUMBLUE
MEDIUMORCHID
MEDIUMPURPLE
MEDIUMSEAGREEN
MEDIUMSLATEBLUE
MEDIUMSPRINGGREEN
MEDIUMTURQUOISE
MEDIUMVIOLETRED
MIDNIGHTBLUE
MINTCREAM
MISTYROSE
MOCCASIN
NAVAJOWHITE
NAVY
OLDLACE
OLIVE
OLIVEDRAB
ORANGE
ORANGERED
ORCHID
PALEGOLDENROD
PALEGREEN
PALETURQUOISE
PALEVIOLETRED
PAPAYAWHIP
PEACHPUFF
PERU
PINK
PLUM
POWDERBLUE
PURPLE
RED
ROSYBROWN
ROYALBLUE
SADDLEBROWN
SALMON
SANDYBROWN
SEAGREEN
SEASHELL
SIENNA
SILVER
SKYBLUE
SLATEBLUE
SLATEGRAY
SNOW
SPRINGGREEN
STEELBLUE
TAN
TEAL
THISTLE
TOMATO
TURQUOISE
VIOLET
WHEAT
WHITE
WHITESMOKE
YELLOW
YELLOWGREEN
```

---

## Important Notes

* Color names are **case sensitive** — must be uppercase.
* Unsupported names will cause lookup failure.
* `force_color` should only be used when you already have RGBA values.
* Alpha values may be fractional after scaling (e.g. `127.5`).

---

## Recommended Usage

✔ Use named colors for configs
✔ Use `alpha` for transparency control
✔ Use `force_color` only for dynamic rendering pipelines

---

If you want, I can also generate:

* a visual color preview chart
* a JSON schema validator for color fields
* or automatic validation logic for Pydantic

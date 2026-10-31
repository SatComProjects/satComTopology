"""
Benchmark of the optical inter-satellite link (OISL) advanced model on reference
constellations: bootstrap time (load_simulation) then tick time, both broken
down by stage, for each constellation and for both optical inter-satellite link
models: basic (the default) first, then advanced.

- docs/performance/ (versioned): README.md and the two plots (bootstrap.png,
  ticks.png). The page keeps the history of every run.
- dist/performance/ (not versioned): gnuplot scripts, data files and the raw
  results of every run (results_<date>-<time>.json).

Usage (from the repository root):

    .venv/bin/python tests/performance_scripts/benchmark_constellations.py
    .venv/bin/python tests/performance_scripts/benchmark_constellations.py --ticks 10 --scenarios starlink_g2 oneweb

Each scenario runs in its own Python process, so no scenario benefits from the
caches or imports of another one.

Constellation parameters come from the LEO-NET 2026 paper (Table
"Constellation Orbital Parameters and OISL Configurations"); the plane layouts,
not given in the paper, follow the public filings matching its satellite counts.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import math
import os
import platform
import re
import resource
import shutil
import statistics
import subprocess
import sys
import time
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GROUND_STATIONS_FILE = REPO / "tests/performance_scripts/100_ground_stations.txt"
DEFAULT_OUTPUT_DIR = REPO / "docs/performance"  # versioned: page + images
DEFAULT_WORK_DIR = (
    REPO / "dist/performance"
)  # not versioned: gnuplot, data, raw results

START_DATE = "2026-01-01 00:00:00"
END_DATE = "2026-01-02 00:00:00"

SCENARIOS = {
    "starlink_g2": "Starlink G2",
    "starlink_g7": "Starlink G7",
    "oneweb": "OneWeb",
    "starlink_g2_sso": "Starlink G2 + SSO",
}

# Bootstrap stages printed by BaseConfigurationManager.load_simulation, grouped
# into the categories shared with the tick stages.
BOOTSTRAP_STAGES = {
    "__load_satellite_configuration": "satellites",
    "__load_satellite_to_ground_link_configuration": "ground_links",
    "__load_ground_object_configuration": "ground_links",
    "__load_inter_satellite_addressing_plans_configuration": "isl",
    "__load_inter_satellite_links_configuration": "isl",
}

# Tick stages: SimulationManager default update protocol.
TICK_STAGES = {
    "update_satellites": "satellites",
    "update_ground_stations": "satellites",
    "update_user_terminal": "satellites",
    "update_ground_station_links": "ground_links",
    "update_user_terminal_links": "ground_links",
    "update_inter_satellite_links": "isl",
}

CATEGORIES = ["satellites", "ground_links", "isl", "other"]
CATEGORY_LABELS = {
    "satellites": "Satellites",
    "ground_links": "Ground links",
    "isl": "Inter-satellite links",
    "other": "Other",
}


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _mean_motion_rev_per_day(altitude_km: float) -> float:
    """Circular orbit mean motion, WGS72 constants (the SGP4 gravity model)."""
    from sat_com_model.constants import MU_KM3_S2, RE_KM

    n_rad_s = math.sqrt(MU_KM3_S2 / (RE_KM + altitude_km) ** 3)
    return n_rad_s * 86400.0 / (2.0 * math.pi)


def _terminal(azimuth, elevation, descriptor, possibilities=None, **terminal_kwargs):
    from sat_com_builder.models import (
        OpticalTerminalInstallationProperty,
        OpticalTerminalProperty,
    )

    return OpticalTerminalInstallationProperty(
        azimuth_angle_configuration=azimuth,
        elevation_angle_configuration=elevation,
        descriptor=descriptor,
        orientation_possibilities=possibilities or [descriptor],
        optical_terminal_property=OpticalTerminalProperty(**terminal_kwargs),
    )


def _four_isl_terminals():
    from sat_com_builder.models import InterSatelliteLinkOrientationProperty as O

    return [
        _terminal(0.0, -180, O.INTRA_PLANE_FORWARD),
        _terminal(-180.0, -180, O.INTRA_PLANE_BACKWARD),
        _terminal(90.0, -180, O.INTER_PLANE_LEFT),
        _terminal(-90.0, -180, O.INTER_PLANE_RIGHT),
    ]


def _three_isl_terminals():
    """Forward, backward and one adjacent terminal steering left or right."""
    from sat_com_builder.models import InterSatelliteLinkOrientationProperty as O

    return [
        _terminal(0.0, -180, O.INTRA_PLANE_FORWARD),
        _terminal(-180.0, -180, O.INTRA_PLANE_BACKWARD),
        _terminal(
            0.0,
            -180,
            O.INTER_PLANE_RIGHT,
            [O.INTER_PLANE_RIGHT, O.INTER_PLANE_LEFT],
            max_azimuth_degrees=180,
        ),
    ]


def _inter_shell_terminal():
    """The "+1" terminal of the paper, range extended to 10,000 km."""
    from sat_com_builder.models import InterSatelliteLinkOrientationProperty as O

    return _terminal(0.0, 0, O.INTER_SHELL_FORWARD, maximum_range_distance_km=10_000)


def _walker_shell(
    identifier,
    shell_type,
    planes,
    per_plane,
    inclination,
    altitude_km,
    addressing_plan,
    terminals,
):
    from sat_com_builder.models import (
        OrbitalConnectivityProperty,
        SatelliteProperty,
        WalkerShellProperty,
    )
    from sat_com_constellation.models import WalkerConstellationProperty

    return WalkerShellProperty(
        type=shell_type,
        constellation_property=WalkerConstellationProperty(
            identifier=identifier,
            amount_of_orbit_plane=planes,
            amount_of_satellite_per_orbit_plane=per_plane,
            inclination=inclination,
            mean_revolution_per_day=_mean_motion_rev_per_day(altitude_km),
            phase_difference_between_satellites=True,
        ),
        orbital_connectivity_property=OrbitalConnectivityProperty(
            adjacent_inter_satellite_shifting=0
        ),
        static_addressing_plan=addressing_plan,
        satellite_property=SatelliteProperty(
            optical_inter_satellite_link_installations=terminals
        ),
    )


def build_simulation_property(scenario: str, optical_link_model: str = "advanced"):
    from sat_com_builder.models import (
        AddressingPlanType,
        DawnDuskSunSynchronousOrbitShellProperty,
        GroundConnectivityProperty,
        GroundObjectProperty,
        InterSatelliteLinkOrientationProperty as O,
        OrbitalConnectivityProperty,
        SatelliteProperty,
        SimulationProperty,
        WalkerShellType,
    )
    from sat_com_connectivity.inter_satellite_link_connectivity.strategies import (
        InterShellSSOPriorityConnectivity,
        IntraShellStaticConnectivity,
    )
    from sat_com_constellation.models import (
        DawnDuskSunSynchronousOrbitConstellationProperty,
    )

    walker_shells, sso_shells = [], []
    strategy = IntraShellStaticConnectivity.type

    if scenario == "starlink_g2":
        walker_shells.append(
            _walker_shell(
                "Starlink G2",
                WalkerShellType.DELTA,
                36,
                20,
                70.0,
                570,
                AddressingPlanType.FULL_MESH_WALKER_DELTA,
                _four_isl_terminals(),
            )
        )
    elif scenario == "starlink_g7":
        walker_shells.append(
            _walker_shell(
                "Starlink G7",
                WalkerShellType.DELTA,
                28,
                120,
                53.0,
                530,
                AddressingPlanType.CHECKERBOARD_WALKER_DELTA,
                _three_isl_terminals(),
            )
        )
    elif scenario == "oneweb":
        walker_shells.append(
            _walker_shell(
                "OneWeb",
                WalkerShellType.STAR,
                12,
                49,
                87.9,
                1200,
                AddressingPlanType.FULL_MESH_WALKER_STAR,
                _four_isl_terminals(),
            )
        )
    elif scenario == "starlink_g2_sso":
        walker_shells.append(
            _walker_shell(
                "Starlink G2",
                WalkerShellType.DELTA,
                36,
                20,
                70.0,
                570,
                AddressingPlanType.FULL_MESH_WALKER_DELTA,
                _four_isl_terminals() + [_inter_shell_terminal()],
            )
        )
        sso_shells.append(
            DawnDuskSunSynchronousOrbitShellProperty(
                constellation_property=DawnDuskSunSynchronousOrbitConstellationProperty(
                    identifier="SSO Datacenter",
                    altitude_in_km=650,
                    amount_of_satellite=81,
                ),
                orbital_connectivity_property=OrbitalConnectivityProperty(),
                satellite_property=SatelliteProperty(
                    optical_inter_satellite_link_installations=[
                        _terminal(0.0, -180, O.INTRA_PLANE_FORWARD),
                        _terminal(-180.0, -180, O.INTRA_PLANE_BACKWARD),
                        _inter_shell_terminal(),
                    ]
                ),
            )
        )
        strategy = InterShellSSOPriorityConnectivity.type
    else:
        raise ValueError(f"Unknown scenario {scenario!r}, known: {list(SCENARIOS)}")

    return SimulationProperty(
        simulation_name=SCENARIOS[scenario],
        optical_inter_satellite_link_model=optical_link_model,
        start_date=START_DATE,
        end_date=END_DATE,
        walker_shells=walker_shells,
        dawn_dusk_sso_shells=sso_shells,
        inter_satellite_link_connection_strategy=strategy,
        ground_objects_properties=[
            GroundObjectProperty(
                identifier="Benchmark Ground Stations",
                data_file=GROUND_STATIONS_FILE.as_posix(),
                type="ground_station",
                connectivity_properties=GroundConnectivityProperty(
                    elevation_above_horizon=20,
                    ground_to_space_connections_strategy="everything-visible",
                ),
            )
        ],
    )


# ---------------------------------------------------------------------------
# Measurement (child process)
# ---------------------------------------------------------------------------

_STAGE_LINE = re.compile(r"^(\S.*?)\s+\|\s+([0-9.]+) s$")


def _categorise(
    stages: dict[str, float], mapping: dict[str, str], total: float
) -> dict:
    categories = {c: 0.0 for c in CATEGORIES}
    for name, seconds in stages.items():
        categories[mapping.get(name, "other")] += seconds
    # Whatever the stages did not cover (event loop, bookkeeping) is "other".
    categories["other"] += max(0.0, total - sum(stages.values()))
    return categories


def run_scenario(
    scenario: str, ticks: int, tick_seconds: float, optical_link_model: str
) -> dict:
    warnings.filterwarnings("ignore")
    from sat_com_builder.configuration_manager import BaseConfigurationManager

    simulation_property = build_simulation_property(scenario, optical_link_model)

    captured = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(captured):
        simulation_manager = BaseConfigurationManager(
            simulation_property=simulation_property
        ).load_simulation()
    bootstrap_total = time.perf_counter() - t0

    bootstrap_stages = {}
    for line in captured.getvalue().splitlines():
        match = _STAGE_LINE.match(line.strip())
        if match:
            bootstrap_stages[match.group(1)] = float(match.group(2))

    counts_after_bootstrap = _counts(simulation_manager)

    # Time every function of the update protocol.
    tick_stage_times: dict[str, float] = {}

    def timed(function):
        def wrapper():
            start = time.perf_counter()
            function()
            tick_stage_times[function.__name__] = time.perf_counter() - start

        wrapper.__name__ = function.__name__
        return wrapper

    simulation_manager.set_callable_protocol(
        [timed(f) for f in simulation_manager.get_default_update_protocol()]
    )

    tick_results = []
    for _ in range(ticks):
        tick_stage_times.clear()
        start = time.perf_counter()
        simulation_manager.time_manager.tick(seconds=tick_seconds)
        total = time.perf_counter() - start
        tick_results.append(
            {
                "total": total,
                "stages": dict(tick_stage_times),
                "categories": _categorise(tick_stage_times, TICK_STAGES, total),
            }
        )

    return {
        "scenario": scenario,
        "optical_link_model": optical_link_model,
        "label": SCENARIOS[scenario],
        "ticks": ticks,
        "tick_seconds": tick_seconds,
        "bootstrap": {
            "total": bootstrap_total,
            "stages": bootstrap_stages,
            "categories": _categorise(
                bootstrap_stages, BOOTSTRAP_STAGES, bootstrap_total
            ),
        },
        "tick_results": tick_results,
        "counts_after_bootstrap": counts_after_bootstrap,
        "counts_after_ticks": _counts(simulation_manager),
        # Linux reports kilobytes
        "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }


def _counts(simulation_manager) -> dict:
    return {
        "satellites": len(simulation_manager.get_satellites()),
        "inter_satellite_links": len(simulation_manager.get_inter_satellites_links()),
        "ground_station_links": len(simulation_manager.get_ground_stations_links()),
        "ground_stations": len(simulation_manager.get_ground_stations()),
    }


# ---------------------------------------------------------------------------
# Summary, data files and gnuplot (working files go to dist/, images to docs/)
# ---------------------------------------------------------------------------

# Basic first: the default model, the one most simulations use.
OPTICAL_LINK_MODELS = ["basic", "advanced"]

SECTION_TITLES = {
    "basic": "Performance Using Optical Links Basic Model",
    "advanced": "Performance Using Optical Links Advanced Model",
}

SECTION_INTRODUCTIONS = {
    "basic": (
        "`optical_inter_satellite_link_model: basic`, the default, used by most "
        "simulations. Links follow the addressing plans: terminals are only "
        "connection slots, no optical metric is computed and links are never "
        "dropped for geometry. Only the straight-line distance is computed. In "
        "Starlink G2 + SSO, the inter-shell links are still computed by the "
        "inter-shell strategy, which needs the optical metrics: only the "
        "intra-shell links are basic.\n"
    ),
    "advanced": (
        "`optical_inter_satellite_link_model: advanced`, optional: enable it only "
        "when the simulation needs the optical terminal constraints. Every optical "
        "inter-satellite link is checked against its terminals configuration "
        "(elevation, azimuth, range, angular velocity, line of sight) and carries "
        "its optical constraints. Links can be dropped when the geometry breaks "
        "them.\n"
    ),
}

COLORS = {
    "satellites": "#4C72B0",
    "ground_links": "#55A868",
    "isl": "#C44E52",
    "other": "#8C8C8C",
}


def summarise(result: dict) -> dict:
    """Bootstrap and mean tick of one scenario, by category."""
    ticks = result["tick_results"]
    totals = [t["total"] for t in ticks]
    return {
        "bootstrap": result["bootstrap"]["categories"]
        | {"total": result["bootstrap"]["total"]},
        "tick": {
            c: statistics.mean(t["categories"][c] for t in ticks) for c in CATEGORIES
        }
        | {"total": statistics.mean(totals), "min": min(totals), "max": max(totals)},
    }


def write_data_files(results: list[dict], work_dir: Path, model: str) -> None:
    for kind in ("bootstrap", "tick"):
        extra = " min max" if kind == "tick" else ""
        lines = ["# scenario " + " ".join(CATEGORIES) + " total" + extra + "\n"]
        for result in results:
            values = summarise(result)[kind]
            columns = CATEGORIES + ["total"] + (["min", "max"] if extra else [])
            cells = " ".join(f"{values[c]:.6f}" for c in columns)
            lines.append(f"\"{result['label']}\" {cells}\n")
        (work_dir / f"{kind}_{model}.dat").write_text("".join(lines))


def _gnuplot_script(
    datafile: str, image: Path, title: str, with_range: bool, bars: int
) -> str:
    stacks = []
    for i, category in enumerate(CATEGORIES):
        xtic = ":xtic(1)" if i == 0 else ""
        stacks.append(
            f'"{datafile}" using {i + 2}{xtic} title "{CATEGORY_LABELS[category]}" '
            f'lc rgb "{COLORS[category]}"'
        )
    total = len(CATEGORIES) + 2
    if with_range:
        # Whisker from the fastest to the slowest tick, label above it.
        stacks.append(
            f'"{datafile}" using ($0):{total}:{total + 1}:{total + 2} with yerrorbars '
            f'lc rgb "#222222" lw 1.4 pt 7 ps 0.6 title "Min / max tick"'
        )
        label_y = f"${total + 2}"
    else:
        label_y = f"${total}"
    stacks.append(
        f'"{datafile}" using ($0):({label_y}):(sprintf("%.2f s", ${total})) '
        f'with labels offset 0,1 font "Sans Bold,12" tc rgb "#222222" notitle'
    )
    plots = ", \\\n     ".join(stacks)
    return f"""# Generated by benchmark_constellations.py
set terminal pngcairo size 1200,700 enhanced font "Sans,13" linewidth 1.2
set output "{image}"
set title "{title}" font "Sans Bold,16" tc rgb "#222222"
set style data histograms
set style histogram rowstacked
set style fill solid 0.92 border rgb "#FFFFFF"
set boxwidth 0.6
set border 3 lc rgb "#555555"
set tics nomirror tc rgb "#333333"
set grid ytics lc rgb "#DDDDDD" lt 1
set key top left horizontal maxrows 2 reverse Left samplen 1.2 width 2 tc rgb "#333333"
set ylabel "Time (s)" tc rgb "#333333"
set yrange [0:*]
set xrange [-0.6:{bars - 0.4}]
set offsets 0, 0, graph 0.25, 0
plot {plots}
"""


def write_and_run_gnuplot(
    results: list[dict], work_dir: Path, output_dir: Path, model: str
) -> list[str]:
    gnuplot = shutil.which("gnuplot")
    if gnuplot is None:
        print("gnuplot not found: data files written, plots skipped.")
        return []

    ticks, tick_seconds = results[0]["ticks"], results[0]["tick_seconds"]
    plots = {
        f"bootstrap_{model}.png": (
            f"bootstrap_{model}.dat",
            f"Bootstrap time (first step), {model} optical link model",
            False,
        ),
        f"ticks_{model}.png": (
            f"tick_{model}.dat",
            f"Mean tick time over {ticks} ticks of {tick_seconds:g} s, "
            f"{model} optical link model",
            True,
        ),
    }
    for image, (datafile, title, with_range) in plots.items():
        script = work_dir / (Path(image).stem + ".gp")
        script.write_text(
            _gnuplot_script(
                datafile, output_dir / image, title, with_range, len(results)
            )
        )
        subprocess.run([gnuplot, script.name], cwd=work_dir, check=True)
    return list(plots)


# ---------------------------------------------------------------------------
# Documentation page and history
# ---------------------------------------------------------------------------

HISTORY_BEGIN = "<!-- benchmark-history (generated, one JSON object per run)"
HISTORY_END = "end-of-benchmark-history -->"


def read_history(page: Path) -> list[dict]:
    """Runs recorded in the hidden block of the previous page, oldest first."""
    if not page.exists():
        return []
    text = page.read_text()
    if HISTORY_BEGIN not in text or HISTORY_END not in text:
        return []
    block = text.split(HISTORY_BEGIN, 1)[1].split(HISTORY_END, 1)[0]
    runs = [json.loads(line) for line in block.splitlines() if line.strip()]
    for run in runs:
        # Runs recorded before the basic model existed were advanced only.
        if "results_by_model" not in run:
            run["results_by_model"] = {"advanced": run.pop("results")}
    return runs


def history_entry(results_by_model: dict[str, list[dict]], run_date: str) -> dict:
    first = next(iter(results_by_model.values()))[0]
    return {
        "date": run_date,
        "commit": _git_commit(),
        "ticks": first["ticks"],
        "tick_seconds": first["tick_seconds"],
        "cpu": _cpu_name(),
        "results_by_model": {
            model: {
                r["label"]: {
                    "bootstrap": round(summarise(r)["bootstrap"]["total"], 4),
                    "tick": round(summarise(r)["tick"]["total"], 4),
                }
                for r in results
            }
            for model, results in results_by_model.items()
        },
    }


def _fmt(seconds: float) -> str:
    return f"{seconds:.2f} s"


def _model_section(model: str, results: list[dict], images: list[str]) -> list[str]:
    lines = [f"## {SECTION_TITLES[model]}\n", "\n", SECTION_INTRODUCTIONS[model], "\n"]
    for image, alt in (
        (f"bootstrap_{model}.png", "Bootstrap time by stage"),
        (f"ticks_{model}.png", "Mean tick time by stage"),
    ):
        if image in images:
            lines += [f"![{alt}, {model} model]({image})\n", "\n"]

    lines += [
        "| Scenario | Satellites | ISLs | Ground links | Bootstrap | Mean tick | Min / max tick | Peak memory |\n",
        "|---|---|---|---|---|---|---|---|\n",
    ]
    for r in results:
        s = summarise(r)
        c = r["counts_after_bootstrap"]
        lines.append(
            f"| {r['label']} | {c['satellites']:,} | {c['inter_satellite_links']:,} | "
            f"{c['ground_station_links']:,} | {_fmt(s['bootstrap']['total'])} | "
            f"{_fmt(s['tick']['total'])} | {_fmt(s['tick']['min'])} / {_fmt(s['tick']['max'])} | "
            f"{r['peak_memory_mb']:,.0f} MB |\n"
        )

    lines += [
        "\n",
        "Where the time goes:\n",
        "\n",
        "| Scenario | Phase | Satellites | Ground links | Inter-satellite links | Other |\n",
        "|---|---|---|---|---|---|\n",
    ]
    for r in results:
        s = summarise(r)
        for phase, values in (("bootstrap", s["bootstrap"]), ("mean tick", s["tick"])):
            total = sum(values[c] for c in CATEGORIES) or 1.0
            cells = " | ".join(
                f"{_fmt(values[c])} ({100 * values[c] / total:.0f}%)"
                for c in CATEGORIES
            )
            lines.append(f"| {r['label']} | {phase} | {cells} |\n")
    lines.append("\n")
    return lines


def _history_table(model: str, history: list[dict]) -> list[str]:
    runs = [run for run in history if model in run["results_by_model"]]
    if not runs:
        return []
    labels = list(
        dict.fromkeys(label for run in runs for label in run["results_by_model"][model])
    )
    lines = [
        f"### {model.capitalize()} model\n",
        "\n",
        "| Date | Commit | Ticks | " + " | ".join(labels) + " |\n",
        "|---|---|---|" + "---|" * len(labels) + "\n",
    ]
    for run in reversed(runs):
        cells = []
        for label in labels:
            value = run["results_by_model"][model].get(label)
            cells.append(
                f"{_fmt(value['bootstrap'])} / {_fmt(value['tick'])}" if value else "–"
            )
        lines.append(
            f"| {run['date']} | `{run['commit']}` | {run['ticks']} × {run['tick_seconds']:g} s | "
            + " | ".join(cells)
            + " |\n"
        )
    lines.append("\n")
    return lines


def write_markdown(
    results_by_model: dict[str, list[dict]],
    output_dir: Path,
    images: list[str],
    history: list[dict],
) -> Path:
    first = next(iter(results_by_model.values()))[0]
    ticks, tick_seconds = first["ticks"], first["tick_seconds"]

    lines = [
        "# SatComTopology Performance\n",
        "\n",
        "Bootstrap time (`BaseConfigurationManager.load_simulation`) and tick time on "
        "reference constellations, broken down by stage, for both optical "
        "inter-satellite link models:\n",
        "\n",
        *(
            f"- [{SECTION_TITLES[m]}](#{SECTION_TITLES[m].lower().replace(' ', '-')})\n"
            for m in OPTICAL_LINK_MODELS
            if m in results_by_model
        ),
        "\n",
        "_This page is generated by "
        "[`tests/performance_scripts/benchmark_constellations.py`](../../tests/performance_scripts/benchmark_constellations.py). "
        "Do not edit it by hand: rerun the script. Each run adds a line to the history "
        "below. Working files (gnuplot scripts, data, raw results) go to "
        "`dist/performance/`._\n",
        "\n",
        "```bash\n",
        ".venv/bin/python tests/performance_scripts/benchmark_constellations.py\n",
        "```\n",
        "\n",
        "## Scenarios\n",
        "\n",
        "Parameters from the LEO-NET 2026 paper (constellation table). The plane layouts, "
        "not given in the paper, follow the public filings matching its satellite counts.\n",
        "\n",
        "| Scenario | Shells | ISL layout | ISL strategy |\n",
        "|---|---|---|---|\n",
        "| Starlink G2 | Walker Delta 36 × 20 = 720 sat., 570 km, 70° | 4 ISL, full mesh | intra-shell static |\n",
        "| Starlink G7 | Walker Delta 28 × 120 = 3,360 sat., 530 km, 53° | 3 ISL, checkerboard | intra-shell static |\n",
        "| OneWeb | Walker Star 12 × 49 = 588 sat., 1,200 km, 87.9° | 4 ISL, full mesh (Walker Star) | intra-shell static |\n",
        "| Starlink G2 + SSO | Starlink G2 + dawn-dusk SSO 81 sat., 650 km | G2: 4 + 1 ISL, SSO: 2 + 1 ISL (+1 = inter-shell, 10,000 km range) | inter-shell SSO priority |\n",
        "\n",
        f"Every scenario has the same 100 ground stations (`everything-visible`, 20° minimum "
        f"elevation). Each scenario runs {ticks} ticks of {tick_seconds:g} s, starting "
        f"{START_DATE}, in its own Python process.\n",
        "\n",
        "Stages:\n",
        "- **Satellites**: bootstrap = constellation generation (TLEs, satellite objects); "
        "tick = position update of satellites and ground objects.\n",
        "- **Ground links**: bootstrap = ground objects loading and first ground links; "
        "tick = ground station and user terminal link updates.\n",
        "- **Inter-satellite links**: bootstrap = addressing plans, terminal selection "
        "and first ISL computation; tick = ISL update.\n",
        "- **Other**: everything else (simulation objects, time manager, event bookkeeping).\n",
        "\n",
    ]
    for model in OPTICAL_LINK_MODELS:
        if model in results_by_model:
            lines += _model_section(model, results_by_model[model], images)

    lines += [
        "## History\n",
        "\n",
        "Bootstrap / mean tick, most recent run first. Compare runs made on the same machine.\n",
        "\n",
    ]
    for model in OPTICAL_LINK_MODELS:
        lines += _history_table(model, history)

    lines += [
        "## Machine (latest run)\n",
        "\n",
        f"- CPU: {_cpu_name()} ({os.cpu_count()} logical cores, the simulation uses one)\n",
        f"- Python {platform.python_version()} on {platform.system()} {platform.release()}\n",
        f"- Commit: `{_git_commit()}`\n",
        "\n",
        HISTORY_BEGIN + "\n",
        *(json.dumps(run, ensure_ascii=False) + "\n" for run in history),
        HISTORY_END + "\n",
    ]
    page = output_dir / "README.md"
    page.write_text("".join(lines))
    return page


def _cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _git_commit() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return commit + (" (with uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--tick-seconds", type=float, default=60.0)
    parser.add_argument(
        "--scenarios", nargs="+", choices=list(SCENARIOS), default=list(SCENARIOS)
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=OPTICAL_LINK_MODELS,
        default=OPTICAL_LINK_MODELS,
        help="optical inter-satellite link models to benchmark (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="page and images (default: docs/performance)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK_DIR,
        help="gnuplot scripts, data files and raw results (default: dist/performance)",
    )
    parser.add_argument("--run-one", choices=list(SCENARIOS), help=argparse.SUPPRESS)
    parser.add_argument("--model", choices=OPTICAL_LINK_MODELS, help=argparse.SUPPRESS)
    parser.add_argument("--json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.run_one:  # child process
        result = run_scenario(args.run_one, args.ticks, args.tick_seconds, args.model)
        args.json.write_text(json.dumps(result))
        return

    output_dir = args.output_dir.resolve()
    work_dir = args.work_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO), str(REPO / "src"), env.get("PYTHONPATH", "")]
    )

    run_started = datetime.datetime.now()
    results_by_model: dict[str, list[dict]] = {}
    for model in [m for m in OPTICAL_LINK_MODELS if m in args.models]:
        for scenario in args.scenarios:
            name = f"{SCENARIOS[scenario]} ({model})"
            print(f"[benchmark] {name}: running {args.ticks} ticks ...", flush=True)
            json_path = work_dir / f".result_{scenario}_{model}.json"
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--run-one",
                    scenario,
                    "--model",
                    model,
                    "--ticks",
                    str(args.ticks),
                    "--tick-seconds",
                    str(args.tick_seconds),
                    "--json",
                    str(json_path),
                ],
                env=env,
                check=True,
            )
            result = json.loads(json_path.read_text())
            json_path.unlink()
            s = summarise(result)
            print(
                f"[benchmark] {name}: bootstrap {s['bootstrap']['total']:.2f} s, "
                f"mean tick {s['tick']['total']:.2f} s",
                flush=True,
            )
            results_by_model.setdefault(model, []).append(result)

    # Raw results of every run are kept locally (dist/ is not versioned).
    stamp = run_started.strftime("%Y%m%d-%H%M%S")
    (work_dir / f"results_{stamp}.json").write_text(
        json.dumps(results_by_model, indent=2)
    )
    images = []
    for model, results in results_by_model.items():
        write_data_files(results, work_dir, model)
        images += write_and_run_gnuplot(results, work_dir, output_dir, model)

    page = output_dir / "README.md"
    history = read_history(page) + [
        history_entry(results_by_model, run_started.strftime("%Y-%m-%d %H:%M"))
    ]
    write_markdown(results_by_model, output_dir, images, history)
    print(f"[benchmark] page written: {page}")
    print(f"[benchmark] working files: {work_dir}")


if __name__ == "__main__":
    main()

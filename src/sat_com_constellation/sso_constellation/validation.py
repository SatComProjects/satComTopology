"""
evaluate_sso.py — Validation of generate_sso_dawn_dusk() vs real satellites.

HOW TO USE
----------
1. Get TLEs from CelesTrak:
   https://celestrak.org/NORAD/elements/gp.php?CATNR=<NORAD_ID>

2. Paste line1/line2 for each satellite in REFERENCE_SATELLITES below.

3. Run:  python evaluate_sso.py
"""

import math
from datetime import timezone

from astropy.time import Time
from sgp4.api import Satrec, WGS72

from sat_com_constellation.sso_constellation.sso_propagation import (
    get_sun_ra_deg_high_precision,
    generate_sso_dawn_dusk,
)

# ---------------------------------------------------------------------------
# Reference satellites  (LTAN ~ 18:00 ascending = dusk terminator)
# CelesTrak: https://celestrak.org/cgi-bin/TLE.pl?CATNR=<NORAD_ID>
# ---------------------------------------------------------------------------

REFERENCE_SATELLITES = [
    {
        "name": "Sentinel-1A",
        "norad_id": 39634,
        "nominal_ltan_h": 18.0,
        "note": "C-band SAR, LTAN=18:00, dawn-dusk, 12-day repeat, 693 km",
        "line1": "1 39634U 14016A   26061.19037525 -.00000119  00000+0 -15529-4 0  9992",
        "line2": "2 39634  98.1816  70.2689 0001353  83.8666 276.2688 14.59199004634410",
    },
    {
        "name": "RADARSAT-2",
        "norad_id": 32382,
        "nominal_ltan_h": 18.0,
        "note": "C-band SAR, LTAN=18:00 +/-15 min, 24-day repeat, 798 km",
        "line1": "1 32382U 07061A   26061.19227182  .00000237  00000+0  10887-3 0  9997",
        "line2": "2 32382  98.5814  69.6391 0001189  84.5263 275.6055 14.29981545950660",
    },
    {
        "name": "PROBA-2",
        "norad_id": 36037,
        "nominal_ltan_h": 6.0,
        "note": "Solar observation, dawn-dusk, ~820 km",
        "line1": "1 36037U 09059B   26061.01688457  .00000349  00000+0  91830-4 0  9996",
        "line2": "2 36037  98.2426 245.8574 0012061 249.8795 110.1105 14.54784448865941",
    },
    {
        "name": "Hinode (Solar-B)",
        "norad_id": 29479,
        "nominal_ltan_h": 18.0,
        "note": "Solar observatory, near-continuous Sun view, ~680 km",
        "line1": "1 29479U 06041A   26061.00812252  .00000801  00000+0  14662-3 0  9997",
        "line2": "2 29479  98.0629  78.7141 0016102 267.9375  91.9986 14.68458877 39141",
    },
]

# ---------------------------------------------------------------------------
# Pass/fail thresholds
# ---------------------------------------------------------------------------
THRESHOLD_INC_DEG = 0.010  # degrees   — inclination
THRESHOLD_RAAN_DEG = 0.500  # degrees   — real sats have ~0.1-0.3 deg s/k noise
THRESHOLD_LTAN_H = 0.100  # hours     — 6 minutes of terminator offset
THRESHOLD_PREC_DPD = 0.001  # deg/day   — nodal precession rate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(l1, l2):
    return Satrec.twoline2rv(l1, l2, WGS72)


def _epoch(sat):
    jd = sat.jdsatepoch + sat.jdsatepochF
    return Time(jd, format="jd", scale="utc").to_datetime(timezone.utc)


def _elem(sat):
    mu, Re = 398600.4418, 6378.137
    n = sat.no / 60.0
    a = (mu / n**2) ** (1 / 3)
    return {
        "inc_deg": math.degrees(sat.inclo),
        "raan_deg": math.degrees(sat.nodeo) % 360.0,
        "ecc": sat.ecco,
        "alt_km": a - Re,
    }


def _nodal_rate(inc_deg, alt_km, e=0.0):
    Re, mu, J2 = 6378.137, 398600.4418, 1.08262668e-3
    a = Re + alt_km
    n = math.sqrt(mu / a**3)
    rate = (
        -1.5 * J2 * (Re / (a * (1 - e**2))) ** 2 * n * math.cos(math.radians(inc_deg))
    )
    return math.degrees(rate) * 86400  # deg/day


def _back_ltan(raan_deg, epoch_utc):
    t = Time(epoch_utc.replace(tzinfo=None), scale="utc")
    sun_ra = get_sun_ra_deg_high_precision(t)
    return ((raan_deg - sun_ra) / 15.0 + 12.0) % 24.0


def _adiff(a, b, p=360.0):
    d = abs(a - b) % p
    return min(d, p - d)


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def evaluate(ref):
    r = {"name": ref["name"], "norad": ref["norad_id"], "skipped": False}

    if not ref["line1"] or not ref["line2"]:
        r.update(skipped=True, reason="TLE not provided — fill in line1/line2")
        return r

    real = _parse(ref["line1"], ref["line2"])
    epoch = _epoch(real)
    re = _elem(real)

    r["epoch"] = epoch.strftime("%Y-%m-%d %H:%M UTC")
    r["real_alt"] = round(re["alt_km"], 1)
    r["real_inc"] = round(re["inc_deg"], 4)
    r["real_raan"] = round(re["raan_deg"], 4)
    r["real_ltan"] = round(_back_ltan(re["raan_deg"], epoch), 4)
    r["real_prec"] = round(_nodal_rate(re["inc_deg"], re["alt_km"]), 6)

    tles = generate_sso_dawn_dusk(
        constellation_name=ref["name"],
        number_of_satellites=1,
        altitude_km=re["alt_km"],
        epoch=epoch,
        eccentricity=re["ecc"] or 0.00001,
        ltan_hours=ref["nominal_ltan_h"],
    )
    se = _elem(_parse(tles[0].line1, tles[0].line2))

    r["syn_inc"] = round(se["inc_deg"], 4)
    r["syn_raan"] = round(se["raan_deg"], 4)
    r["syn_ltan"] = round(_back_ltan(se["raan_deg"], epoch), 4)
    r["syn_prec"] = round(_nodal_rate(se["inc_deg"], re["alt_km"]), 6)

    r["d_inc"] = round(abs(re["inc_deg"] - se["inc_deg"]), 4)
    r["d_raan"] = round(_adiff(re["raan_deg"], se["raan_deg"]), 4)
    r["d_ltan"] = round(_adiff(r["real_ltan"], r["syn_ltan"], p=24.0), 4)
    r["d_prec"] = round(abs(r["real_prec"] - r["syn_prec"]), 6)

    r["ok_inc"] = r["d_inc"] < THRESHOLD_INC_DEG
    r["ok_raan"] = r["d_raan"] < THRESHOLD_RAAN_DEG
    r["ok_ltan"] = r["d_ltan"] < THRESHOLD_LTAN_H
    r["ok_prec"] = r["d_prec"] < THRESHOLD_PREC_DPD
    r["ok"] = all([r["ok_inc"], r["ok_raan"], r["ok_ltan"], r["ok_prec"]])
    return r


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

W = 65
T = lambda ok: "+" if ok else "x"


def print_result(r):
    print("\n" + "-" * W)
    if r["skipped"]:
        print(f"  {r['name']} (NORAD {r['norad']})  =>  SKIPPED\n  {r['reason']}")
        return

    print(f"  {r['name']} (NORAD {r['norad']})  =>  {'PASS' if r['ok'] else 'FAIL'}")
    print(f"  Epoch: {r['epoch']}   Alt: {r['real_alt']} km\n")
    print(
        f"  {'Metric':<20} {'Real':>9}  {'Generated':>9}  {'Delta':>9}  {'Thresh':>9}  {'':>4}"
    )
    print(f"  {'-'*20}  {'-'*9}  {'-'*9}  {'-'*9}  {'-'*9}  {'-'*4}")
    for label, rk, sk, dk, thr, ok_key in [
        (
            "Inclination (deg)",
            "real_inc",
            "syn_inc",
            "d_inc",
            THRESHOLD_INC_DEG,
            "ok_inc",
        ),
        (
            "RAAN (deg)",
            "real_raan",
            "syn_raan",
            "d_raan",
            THRESHOLD_RAAN_DEG,
            "ok_raan",
        ),
        ("LTAN (h)", "real_ltan", "syn_ltan", "d_ltan", THRESHOLD_LTAN_H, "ok_ltan"),
        (
            "Prec (deg/day)",
            "real_prec",
            "syn_prec",
            "d_prec",
            THRESHOLD_PREC_DPD,
            "ok_prec",
        ),
    ]:
        print(
            f"  {label:<20} {r[rk]:>9.4f}  {r[sk]:>9.4f}  "
            f"{r[dk]:>9.4f}  {thr:>9.4f}  [{T(r[ok_key])}]"
        )


def print_summary(results):
    tested = [r for r in results if not r["skipped"]]
    skipped = [r for r in results if r["skipped"]]
    print("\n" + "=" * W)
    print("  GLOBAL SUMMARY")
    print("=" * W)

    if not tested:
        print("  No satellites tested. Fill in TLE data in REFERENCE_SATELLITES.")
        return

    n_pass = sum(1 for r in tested if r["ok"])
    print(
        f"  Tested: {len(tested)}   Skipped: {len(skipped)}   Passed: {n_pass}/{len(tested)}\n"
    )

    for label, key, thr, unit in [
        ("Inclination", "d_inc", THRESHOLD_INC_DEG, "deg    "),
        ("RAAN", "d_raan", THRESHOLD_RAAN_DEG, "deg    "),
        ("LTAN", "d_ltan", THRESHOLD_LTAN_H, "h      "),
        ("Precession", "d_prec", THRESHOLD_PREC_DPD, "deg/day"),
    ]:
        vals = [r[key] for r in tested]
        n_fail = sum(1 for v in vals if v >= thr)
        print(
            f"  {label:<14}  mean={sum(vals)/len(vals):.4f} {unit}  "
            f"max={max(vals):.4f} {unit}  failures={n_fail}/{len(tested)}"
        )

    print(
        """
  HOW TO INTERPRET
  ----------------------------------------------------------------
  Inclination  delta < 0.01 deg
    PASS -> J2+J4 formula matches the real operational orbit
    FAIL -> Wrong constants (J2, Re, mu) or tropical year value

  RAAN         delta < 0.50 deg
    PASS -> Sun RA formula places the node on the terminator
    FAIL -> Sun RA error or sign convention mismatch
    NOTE -> Real sats have +/-0.1-0.3 deg station-keeping noise

  LTAN         delta < 0.10 h  (~6 minutes)
    PASS -> Terminator alignment correct at TLE epoch
    FAIL -> If RAAN passes but LTAN fails -> Sun RA offset bug

  Precession   delta < 0.001 deg/day
    PASS -> Inclination will maintain SSO over years
    FAIL -> Small inclination error propagates as LTAN drift

  KNOWN EXCEPTIONS
    Swarm-A/C : NOT strict SSO — expect LTAN delta > 0.10 h
                Use them only to verify inclination and precession.
    Station-keeping noise: RAAN delta 0.1-0.3 deg is normal.
"""
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * W)
    print("  SSO Dawn-Dusk — Evaluation Against Real Satellites")
    print("=" * W)

    results = []
    for ref in REFERENCE_SATELLITES:
        print(f"  {ref['name']} (NORAD {ref['norad_id']}) ...", end=" ", flush=True)
        try:
            r = evaluate(ref)
            results.append(r)
            print("skipped" if r["skipped"] else ("PASS" if r["ok"] else "FAIL"))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(
                {
                    "name": ref["name"],
                    "norad": ref["norad_id"],
                    "skipped": True,
                    "reason": str(e),
                }
            )

    for r in results:
        print_result(r)

    print_summary(results)

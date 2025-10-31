from datetime import datetime, timezone
import math
import curses


# ----------------------------
# 1) UTC → JD(UT) conversion
# ----------------------------
def _jd_ut_from_utc(dt):
    """
    UTC tz-aware datetime → Julian Date(UT)
    - The JD for 1970-01-01 00:00:00 UTC (Unix epoch) is 2440587.5
    - dt.timestamp(): seconds after epoch
    - 1 day = 86400 seconds
    """
    return 2440587.5 + dt.timestamp() / 86400.0


# ----------------------------
# 2) JD(UT) → JD(TT)
# ----------------------------
def _tt_minus_utc_seconds():
    """
    TT - UTC (seconds)
    - Based on current standards (2025) since 2017-01-01: TAI-UTC = 37 s → TT-UTC = 32.184 + 37 = 69.184 s
    - For higher accuracy, this should be updated using the IERS leap second table.
    """
    return 69.184


def _jd_tt_from_utc(dt):
    """
    JD(TT) = JD(UT) + (TT-UTC)/86400
    """
    # NOTE: The dt argument in _tt_minus_utc_seconds is currently ignored but kept for potential future use.
    return _jd_ut_from_utc(dt) + _tt_minus_utc_seconds() / 86400.0


# ----------------------------
# 3) math helper
# ----------------------------
def _mod24(h):
    """Wraps the time value to the 0-24 range (handles negative/excess values)."""
    return h % 24.0


def _days_since_j2000_tt(jd_tt):
    """
    Days elapsed Δt (TT) since J2000(TT) = JD 2451545.0
    - Many astronomical equations are developed based on the J2000 epoch.
    """
    return jd_tt - 2451545.0


# ----------------------------
# 4) Mars Orbit/Solar Position Terms (Mars24 Equations B-1 to B-5)
# ----------------------------
def _mars_mean_anomaly(dtj):
    """B-1: Mars Mean Anomaly M (radians)"""
    return math.radians(19.3871 + 0.52402073 * dtj)


def _fiction_mean_sun(dtj):
    """B-2: Fictitious Mean Sun (αFMS) (radians)"""
    return math.radians(270.3871 + 0.524038496 * dtj)


def _pbs_term(dtj):
    """
    B-3: Perturbers Correction Term PBS (degrees)
    - The sum of small periodic terms due to perturbations from other planets.
    """
    A = [0.0071, 0.0057, 0.0039, 0.0037, 0.0021, 0.0020, 0.0018]
    tau = [2.2353, 2.7543, 1.1177, 15.7866, 2.1354, 2.4694, 32.8493]
    phi = [49.409, 168.173, 191.837, 21.736, 15.704, 95.528, 49.095]
    s = 0.0
    for Ai, ti, ph in zip(A, tau, phi):
        s += Ai * math.cos(math.radians((0.985626 * dtj) / ti + ph))
    return s


def _equation_of_center(M, dtj, pbs_deg):
    """B-4: Equation of Center (degrees)"""
    return (
        (10.691 + 3.0e-7 * dtj) * math.sin(M)
        + 0.623 * math.sin(2 * M)
        + 0.050 * math.sin(3 * M)
        + 0.005 * math.sin(4 * M)
        + 0.0005 * math.sin(5 * M)
        + pbs_deg
    )


def _areocentric_solar_longitude(alpha_fms_rad, eq_center_deg):
    """B-5: Mars Seasonal Angle Ls (degrees)"""
    return math.degrees(alpha_fms_rad) + eq_center_deg


# ----------------------------
# 5) Equation of Time (EOT) and MTC Calculation
# ----------------------------
def _equation_of_time_h(Ls_deg, eq_center_deg):
    """
    C-1: EOT (hours)
    - The difference between Mean Solar Time and True Solar Time (Mars time zone correction)
    """
    Ls = math.radians(Ls_deg)
    eot_deg = (
        2.861 * math.sin(2 * Ls)
        - 0.071 * math.sin(4 * Ls)
        + 0.002 * math.sin(6 * Ls)
        - eq_center_deg
    )
    return eot_deg / 15.0  # hours


def _mst_hours_from_jdtt(jd_tt):
    """
    C-2: MST (a.k.a MTC) in hours
    - Mean Solar Time based on the 0° longitude (Airy-0 meridian).
    """
    return _mod24(24.0 * (((jd_tt - 2451549.5) / 1.0274912517) + 44796.0 - 0.0009626))


# ----------------------------
# 6) Final: LTST Calculation Function
# ----------------------------
def ltst_from_utc_lon(utc_dt: datetime, lon_east_deg: float) -> float:
    """
    Inputs:
      - utc_dt: tz-aware UTC datetime (e.g., datetime.now(timezone.utc))
      - lon_east_deg: East Longitude (+) (degrees East)
    Output:
      - LTST (Local True Solar Time in hours, float in 0-24 range)
    """
    jd_tt = _jd_tt_from_utc(utc_dt)
    dtj = _days_since_j2000_tt(jd_tt)
    M = _mars_mean_anomaly(dtj)
    aF = _fiction_mean_sun(dtj)
    pbs = _pbs_term(dtj)
    ec = _equation_of_center(M, dtj, pbs)
    Ls = _areocentric_solar_longitude(aF, ec)
    eot_h = _equation_of_time_h(Ls, ec)
    mst_h = _mst_hours_from_jdtt(jd_tt)
    # Local Mean Solar Time (LMST) = MST + Longitude / 15 (since 360 deg / 24 hrs = 15 deg/hr)
    lmst_h = _mod24(mst_h + lon_east_deg / 15.0)
    # Local True Solar Time (LTST) = LMST + EOT
    ltst_h = _mod24(lmst_h + eot_h)
    return ltst_h


# ----------------------------
# 7) local locations(5)
# ----------------------------
SITES = [
    ("Meridiani Planum", 6.1),
    ("Gale Crater", 137.4),
    ("Jezero Crater", 77.5),
    ("Elysium Planitia", 135.9),
    ("Olympus Mons", 226.2),
]


# ----------------------------
# 8) function for timing format
# ----------------------------
def _hhmmss(h: float) -> str:
    """Formats a float hour value (0-24) into HH:MM:SS string."""
    h = h % 24.0
    hh = int(h)
    mmf = (h - hh) * 60
    mm = int(mmf)
    ss = int(round((mmf - mm) * 60))
    if ss == 60:
        ss = 0
        mm += 1
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


# ----------------------------
# 9) real time (curses used)
# ----------------------------
def draw(stdscr):
    # Hide cursor
    curses.curs_set(0)
    # Non-blocking input mode
    stdscr.nodelay(True)
    # Set screen refresh timeout to 1000ms (1 second)
    stdscr.timeout(1000)

    while True:
        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q")):
            break

        utc_now = datetime.now(timezone.utc)
        # Clear screen
        stdscr.erase()

        y = 0
        stdscr.addstr(y, 0, "==== Real-time Mars Local True Solar Time (LTST) ====")
        y += 1
        stdscr.addstr(y, 0, f"UTC Time: {utc_now:%Y-%m-%d %H:%M:%S}")
        y += 2
        stdscr.addstr(y, 0, f"{'Site':20s} {'LTST':>8s}")
        y += 1
        stdscr.addstr(y, 0, "-" * 32)
        y += 1

        for name, lon in SITES:
            h = ltst_from_utc_lon(utc_now, lon)
            stdscr.addstr(y, 0, f"{name:20s} {_hhmmss(h):>8s}")
            y += 1

        stdscr.addstr(y + 1, 0, "⏳ Updating every second... (press 'q' to quit)")
        stdscr.refresh()


def main():
    curses.wrapper(draw)


if __name__ == "__main__":
    main()

from datetime import datetime, timezone, timedelta
import math

# --- CORE ASTRONOMICAL CONSTANTS ---
# Standard Earth Day in seconds
EARTH_DAY_SECONDS = 86400.0
# Mean Sol length in Earth seconds
SOL_SECONDS = 88775.24409
# Earth days per Sol conversion factor
EARTH_DAYS_PER_SOL = 1.02749125
# Julian Date (JD) of the J2000 Epoch (January 1, 2000, 12:00:00 UTC)
JD_J2000 = 2451549.5

# MSD offset at J2000 Epoch (used for official MSD calculation)
MSD_OFFSET = 44796.0 - 0.0009626

# --- EQUATION OF TIME (EOT) PARAMETERS for high accuracy ---
# Mean Anomaly (M) and Orbital Eccentricity (e) constants for Mars' orbit around the Sun.
M_2000 = 18.60260  # Mean anomaly at J2000 (degrees)
M_RATE = 0.5240209536  # Mean anomaly rate (degrees per Earth day)
E_ORBITAL = 0.09340  # Orbital eccentricity
L_S_OFFSET = 251.01  # Solar Longitude (Ls) at perihelion (degrees)


def get_mars_eot_correction(msd: float) -> float:
    """
    Calculates the Equation of Time (EOT) correction for Mars.
    This corrects Local Mean Solar Time (LMST) to Local True Solar Time (LTST).

    Args:
        msd: The calculated Mars Sol Date.

    Returns:
        The EOT correction in Earth seconds (which is also Mars seconds / 1.02749).
    """
    # 1. Calculate Days since J2000 based on MSD (MSD 44796.0 is roughly J2000)
    mars_days_since_J2000 = (msd - 44796.0) * EARTH_DAYS_PER_SOL

    # 2. Calculate the Mean Anomaly (M) and True Anomaly (v)
    # The M term is how far Mars is from its closest approach to the sun (perihelion)
    M = (M_2000 + M_RATE * mars_days_since_J2000) % 360.0
    M_rad = math.radians(M)

    # Convert Mean Anomaly (M) to Solar Longitude (Ls) (simplified for EOT)
    # This involves a two-term approximation of the Equation of the Center
    M_center_rad = math.radians(M)
    e = E_ORBITAL
    v_minus_M_rad = 2 * e * math.sin(M_center_rad) + 1.25 * e**2 * math.sin(
        2 * M_center_rad
    )

    # Calculate True Solar Time Offset (Equation of Time)
    # This formula is highly simplified but captures the largest correction term
    eot_seconds = 150 * math.sin(M_rad) + 12.8 * math.sin(2 * M_rad)

    # Scale by the ratio of the Sol length to account for the faster Mars "second"
    # This provides the EOT in terms of Mars clock minutes
    return eot_seconds * 60.0


def utc_to_mars_ltst(earth_dt: datetime, longitude_e: float, latitude: float) -> dict:
    """
    Converts Earth UTC time to Mars Sol Date (MSD) and Local True Solar Time (LTST)
    for a specified location on Mars.

    Args:
        earth_dt: A datetime object (must be in UTC).
        longitude_e: Mars Longitude in degrees East (0 to 360).
        latitude: Mars Latitude in degrees.

    Returns:
        A dictionary containing MSD, Sol, and formatted Mars Time.
    """

    # 1. Ensure the input is UTC
    if earth_dt.tzinfo is None or earth_dt.tzinfo.utcoffset(earth_dt) is None:
        earth_dt = earth_dt.replace(tzinfo=timezone.utc)
    elif earth_dt.tzinfo != timezone.utc:
        earth_dt = earth_dt.astimezone(timezone.utc)

    # 2. Calculate Julian Date (JD)
    j2000_epoch = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    earth_days_since_j2000 = (
        earth_dt - j2000_epoch
    ).total_seconds() / EARTH_DAY_SECONDS
    julian_date = JD_J2000 + earth_days_since_j2000

    # 3. Calculate Mars Sol Date (MSD)
    msd = ((julian_date - JD_J2000) / EARTH_DAYS_PER_SOL) + MSD_OFFSET
    sol_number = math.floor(msd)

    # 4. Calculate Local Mean Solar Time (LMST)
    # LMST Fraction at the Prime Meridian (the time of day from 0.0 to 1.0)
    cmt_fraction = msd % 1.0

    # Convert prime meridian fraction to Mars seconds
    lmst_seconds_at_prime_meridian = cmt_fraction * SOL_SECONDS

    # 5. Apply Longitude Correction (shifts the time zone)
    # Longitude is the 'time zone' difference. 360 degrees = 1 Sol (24 Mars-hours).
    # The shift is (Longitude / 360) * SOL_SECONDS
    longitude_seconds_shift = (longitude_e / 360.0) * SOL_SECONDS

    # Calculate Local Mean Solar Time (LMST) in Mars seconds
    lmst_seconds = (
        lmst_seconds_at_prime_meridian + longitude_seconds_shift
    ) % SOL_SECONDS

    # 6. Apply Equation of Time (EOT) Correction
    # EOT converts the 'Mean' clock time to the 'True' sun-dial time (LTST).
    eot_seconds_correction = get_mars_eot_correction(msd) * 60.0 * EARTH_DAYS_PER_SOL

    # Calculate Local True Solar Time (LTST)
    ltst_seconds = (lmst_seconds + eot_seconds_correction) % SOL_SECONDS

    # 7. Convert Final LTST Seconds to H:M:S (Mars Clock Format)
    hours = int(ltst_seconds // 3600)
    minutes = int((ltst_seconds % 3600) // 60)
    seconds = int(ltst_seconds % 60)

    mars_time_string = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return {
        "Earth_UTC_Time": earth_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "Mars_Sol_Date_MSD": f"{msd:.5f}",
        "Current_Sol_Number": sol_number,
        "Local_True_Solar_Time (LTST)": mars_time_string,
        "Location_Notes": f"Longitude: {longitude_e}° E, Latitude: {latitude}° N",
    }


# --- Example Usage ---

# Current time (Friday, October 24, 2025 at 6:10:25 PM MDT, converted to UTC)
current_utc_time = datetime(2025, 10, 25, 0, 10, 25, tzinfo=timezone.utc)

# 1. Location A: Valles Marineris (a canyon system)
# Longitude 286.0° E, Latitude -10.0° S
location_a = utc_to_mars_ltst(current_utc_time, longitude_e=286.0, latitude=-10.0)
print("--- Location A (Valles Marineris) ---")
for key, value in location_a.items():
    print(f"{key}: {value}")

print("\n")

# 2. Location B: Gale Crater (Curiosity rover landing site)
# Longitude 137.4° E, Latitude -4.5° S
location_b = utc_to_mars_ltst(current_utc_time, longitude_e=137.4, latitude=-4.5)
print("--- Location B (Gale Crater) ---")
for key, value in location_b.items():
    print(f"{key}: {value}")

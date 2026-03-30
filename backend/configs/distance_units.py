from enum import Enum


KM_PER_MILE = 1.60934
STORAGE_KM_PRECISION = 2
DISPLAY_PRECISION = 1


class DistanceUnit(str, Enum):
    KM = "km"
    MI = "mi"


def miles_to_km(miles: float, precision: int = STORAGE_KM_PRECISION) -> float:
    return round(float(miles) * KM_PER_MILE, precision)


def km_to_miles(km: float, precision: int = DISPLAY_PRECISION) -> float:
    return round(float(km) / KM_PER_MILE, precision)


def normalize_km_for_storage(km: float) -> float:
    return round(float(km), STORAGE_KM_PRECISION)


def format_distance(value: float, unit: DistanceUnit = DistanceUnit.KM, precision: int = DISPLAY_PRECISION) -> str:
    rounded = round(float(value), precision)
    return f"{rounded} {unit.value}"

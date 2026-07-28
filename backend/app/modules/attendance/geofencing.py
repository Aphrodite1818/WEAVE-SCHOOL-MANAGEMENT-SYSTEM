"""Pure geofence evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from app.modules.attendance.attendance_enums import GeofenceDecision


EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True, slots=True)
class GeofenceCircle:
    latitude: Decimal
    longitude: Decimal
    radius_m: int


@dataclass(frozen=True, slots=True)
class LocationPoint:
    latitude: Decimal
    longitude: Decimal
    accuracy_m: int


@dataclass(frozen=True, slots=True)
class GeofenceEvaluationResult:
    decision: GeofenceDecision
    distance_m: int | None
    accuracy_m: int | None
    tolerance_m: int
    reason: str | None

    @property
    def allowed(self) -> bool:
        return self.decision == GeofenceDecision.INSIDE


def _valid_coordinate(latitude: Decimal, longitude: Decimal) -> bool:
    return Decimal("-90") <= latitude <= Decimal("90") and Decimal("-180") <= longitude <= Decimal("180")


def haversine_distance_m(
    *,
    source_latitude: Decimal,
    source_longitude: Decimal,
    target_latitude: Decimal,
    target_longitude: Decimal,
) -> int:
    """Return the approximate distance between two coordinates in metres."""

    lat1 = radians(float(source_latitude))
    lon1 = radians(float(source_longitude))
    lat2 = radians(float(target_latitude))
    lon2 = radians(float(target_longitude))

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    arc = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return round(2 * EARTH_RADIUS_M * asin(sqrt(arc)))


def evaluate_geofence(
    *,
    geofence: GeofenceCircle | None,
    location: LocationPoint | None,
    max_accuracy_m: int,
    tolerance_m: int = 0,
) -> GeofenceEvaluationResult:
    """Evaluate one location sample against one server-owned geofence."""

    safe_tolerance = max(0, int(tolerance_m))

    if geofence is None:
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.UNAVAILABLE,
            distance_m=None,
            accuracy_m=None if location is None else location.accuracy_m,
            tolerance_m=safe_tolerance,
            reason="No active geofence is configured.",
        )
    if location is None:
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.UNAVAILABLE,
            distance_m=None,
            accuracy_m=None,
            tolerance_m=safe_tolerance,
            reason="No location sample was provided.",
        )
    if not _valid_coordinate(location.latitude, location.longitude):
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.INVALID,
            distance_m=None,
            accuracy_m=location.accuracy_m,
            tolerance_m=safe_tolerance,
            reason="The provided coordinates are outside valid latitude/longitude ranges.",
        )
    if location.accuracy_m <= 0:
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.INVALID,
            distance_m=None,
            accuracy_m=location.accuracy_m,
            tolerance_m=safe_tolerance,
            reason="Location accuracy must be greater than zero metres.",
        )
    if location.accuracy_m > max_accuracy_m:
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.INACCURATE,
            distance_m=None,
            accuracy_m=location.accuracy_m,
            tolerance_m=safe_tolerance,
            reason="Location accuracy is too low for attendance verification.",
        )

    distance = haversine_distance_m(
        source_latitude=geofence.latitude,
        source_longitude=geofence.longitude,
        target_latitude=location.latitude,
        target_longitude=location.longitude,
    )
    if distance <= geofence.radius_m + safe_tolerance:
        return GeofenceEvaluationResult(
            decision=GeofenceDecision.INSIDE,
            distance_m=distance,
            accuracy_m=location.accuracy_m,
            tolerance_m=safe_tolerance,
            reason=None,
        )
    return GeofenceEvaluationResult(
        decision=GeofenceDecision.OUTSIDE,
        distance_m=distance,
        accuracy_m=location.accuracy_m,
        tolerance_m=safe_tolerance,
        reason="Location is outside the configured school geofence.",
    )

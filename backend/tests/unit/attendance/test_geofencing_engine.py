from decimal import Decimal

from app.modules.attendance.attendance_enums import GeofenceDecision
from app.modules.attendance.geofencing import (
    GeofenceCircle,
    LocationPoint,
    evaluate_geofence,
    haversine_distance_m,
)


def test_haversine_distance_returns_zero_for_same_coordinate() -> None:
    distance = haversine_distance_m(
        source_latitude=Decimal("6.524379"),
        source_longitude=Decimal("3.379206"),
        target_latitude=Decimal("6.524379"),
        target_longitude=Decimal("3.379206"),
    )

    assert distance == 0


def test_evaluate_geofence_allows_inside_location() -> None:
    result = evaluate_geofence(
        geofence=GeofenceCircle(
            latitude=Decimal("6.524379"),
            longitude=Decimal("3.379206"),
            radius_m=150,
        ),
        location=LocationPoint(
            latitude=Decimal("6.524400"),
            longitude=Decimal("3.379250"),
            accuracy_m=20,
        ),
        max_accuracy_m=100,
        tolerance_m=10,
    )

    assert result.decision == GeofenceDecision.INSIDE
    assert result.allowed is True
    assert result.distance_m is not None


def test_evaluate_geofence_blocks_outside_location() -> None:
    result = evaluate_geofence(
        geofence=GeofenceCircle(
            latitude=Decimal("6.524379"),
            longitude=Decimal("3.379206"),
            radius_m=50,
        ),
        location=LocationPoint(
            latitude=Decimal("6.530000"),
            longitude=Decimal("3.390000"),
            accuracy_m=20,
        ),
        max_accuracy_m=100,
        tolerance_m=0,
    )

    assert result.decision == GeofenceDecision.OUTSIDE
    assert result.allowed is False
    assert result.distance_m is not None


def test_evaluate_geofence_rejects_low_accuracy_sample() -> None:
    result = evaluate_geofence(
        geofence=GeofenceCircle(
            latitude=Decimal("6.524379"),
            longitude=Decimal("3.379206"),
            radius_m=150,
        ),
        location=LocationPoint(
            latitude=Decimal("6.524400"),
            longitude=Decimal("3.379250"),
            accuracy_m=250,
        ),
        max_accuracy_m=100,
        tolerance_m=10,
    )

    assert result.decision == GeofenceDecision.INACCURATE
    assert result.distance_m is None


def test_evaluate_geofence_reports_missing_geofence_as_unavailable() -> None:
    result = evaluate_geofence(
        geofence=None,
        location=LocationPoint(
            latitude=Decimal("6.524400"),
            longitude=Decimal("3.379250"),
            accuracy_m=20,
        ),
        max_accuracy_m=100,
    )

    assert result.decision == GeofenceDecision.UNAVAILABLE


def test_evaluate_geofence_rejects_invalid_accuracy() -> None:
    result = evaluate_geofence(
        geofence=GeofenceCircle(
            latitude=Decimal("6.524379"),
            longitude=Decimal("3.379206"),
            radius_m=150,
        ),
        location=LocationPoint(
            latitude=Decimal("6.524400"),
            longitude=Decimal("3.379250"),
            accuracy_m=0,
        ),
        max_accuracy_m=100,
    )

    assert result.decision == GeofenceDecision.INVALID

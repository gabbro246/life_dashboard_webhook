"""Import date-stamped webhook data as hidden Home Assistant statistics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time
from hashlib import sha256
import logging
from statistics import fmean
from typing import Any

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .parser import (
    NUTRITION_FIELDS,
    POINT_MAPPINGS,
    _accumulated,
    _duration_seconds,
    _measurement,
    resolve_app_name,
)
from .sensor_definitions import HEALTH_SENSOR_DEFINITIONS

_LOGGER = logging.getLogger(__name__)

_DAILY_TOTALS: tuple[tuple[str, str, str, str], ...] = (
    ("steps", "steps_daily", "Steps per day", "steps"),
    ("distance_meters", "distance_daily", "Distance per day", "m"),
    ("active_calories", "active_calories_daily", "Active calories per day", "kcal"),
    ("total_calories", "total_calories_daily", "Total calories per day", "kcal"),
)
_ACCUMULATED_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("steps", "count", "steps_latest_interval"),
    ("distance", "meters", "distance_latest_interval"),
    ("active_calories", "calories", "active_calories_latest_interval"),
    ("total_calories", "calories", "total_calories_latest_interval"),
)
_DEFINITIONS = {definition.key: definition for definition in HEALTH_SENSOR_DEFINITIONS}


@dataclass(frozen=True, slots=True)
class _HistoryPoint:
    """One numeric observation that belongs in an external statistic."""

    key: str
    name: str
    unit: str | None
    start: datetime
    value: float


def _number(value: Any) -> float | None:
    """Return a real numeric value, excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO timestamp or date in Home Assistant's configured timezone."""
    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value) == 10:
            parsed = datetime.combine(
                datetime.fromisoformat(value).date(), time.min, dt_util.DEFAULT_TIME_ZONE
            )
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    except ValueError:
        return None
    return parsed.astimezone(UTC)


def _record_start(record: dict[str, Any]) -> datetime | None:
    """Get the timestamp that best represents an observation or aggregate bucket."""
    for key in (
        "bucket_start",
        "start_time",
        "time",
        "session_end_time",
        "end_time",
        "bucket_end",
    ):
        if start := _parse_time(record.get(key)):
            return start
    return _parse_time(record.get("date"))


def _hour_start(value: datetime) -> datetime:
    """Round an external statistic to Home Assistant's hourly storage resolution."""
    return value.replace(minute=0, second=0, microsecond=0)


def _records(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return valid records from one webhook collection."""
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def _health_point(
    key: str, start: datetime | None, value: Any, device_name: str
) -> _HistoryPoint | None:
    """Build a history point from an existing numeric Health sensor definition."""
    definition = _DEFINITIONS.get(key)
    numeric_value = _number(value)
    if definition is None or start is None or numeric_value is None:
        return None
    return _HistoryPoint(
        key=f"health_{key}",
        name=f"{device_name} Health {definition.name}",
        unit=definition.unit,
        start=_hour_start(start),
        value=numeric_value,
    )


def _add_health_record_points(
    points: list[_HistoryPoint],
    payload: dict[str, Any],
    payload_key: str,
    field: str,
    sensor_key: str,
    device_name: str,
    *,
    accumulated: bool = False,
) -> None:
    """Add every dated record for one numeric health data type."""
    for record in _records(payload, payload_key):
        value = _accumulated(record, field) if accumulated else _measurement(record, field)
        if point := _health_point(sensor_key, _record_start(record), value, device_name):
            points.append(point)


def _health_history(payload: dict[str, Any], device_name: str) -> list[_HistoryPoint]:
    """Return daily totals and timestamped numeric Health Connect observations."""
    points: list[_HistoryPoint] = []

    for day in _records(payload, "daily_totals"):
        start = _parse_time(day.get("date"))
        for field, key, name, unit in _DAILY_TOTALS:
            value = _number(day.get(field))
            if start is not None and value is not None:
                points.append(
                    _HistoryPoint(
                        key=f"health_{key}",
                        name=f"{device_name} Health {name}",
                        unit=unit,
                        start=_hour_start(start),
                        value=value,
                    )
                )

    for payload_key, field, sensor_key in _ACCUMULATED_MAPPINGS:
        _add_health_record_points(
            points,
            payload,
            payload_key,
            field,
            sensor_key,
            device_name,
            accumulated=True,
        )
    for payload_key, field, sensor_key in POINT_MAPPINGS:
        _add_health_record_points(
            points, payload, payload_key, field, sensor_key, device_name
        )

    for record in _records(payload, "skin_temperature"):
        start = _record_start(record)
        for key, value in (
            ("skin_temperature_delta", _measurement(record, "delta_celsius")),
            ("skin_temperature_baseline", record.get("baseline_celsius")),
        ):
            if point := _health_point(key, start, value, device_name):
                points.append(point)

    for record in _records(payload, "blood_pressure"):
        start = _record_start(record)
        for key, value in (
            ("blood_pressure_systolic", record.get("systolic")),
            ("blood_pressure_diastolic", record.get("diastolic")),
        ):
            if point := _health_point(key, start, value, device_name):
                points.append(point)

    for record in _records(payload, "sleep"):
        start = _record_start(record)
        if point := _health_point(
            "sleep_duration", start, _duration_seconds(record), device_name
        ):
            points.append(point)
        stage_totals: dict[str, float] = defaultdict(float)
        for stage in _records(record, "stages"):
            duration = _number(_duration_seconds(stage))
            if duration is not None:
                stage_totals[str(stage.get("stage", "unknown"))] += duration
        for stage_name, duration in stage_totals.items():
            if point := _health_point(
                f"sleep_stage_{stage_name}", start, duration, device_name
            ):
                points.append(point)

    for payload_key, sensor_key, field in (
        ("exercise", "exercise_duration", "duration_seconds"),
        ("hydration", "hydration", "liters"),
        ("mindfulness", "mindfulness_duration", "duration_seconds"),
        ("menstruation_period", "menstruation_period_duration", "duration_seconds"),
    ):
        for record in _records(payload, payload_key):
            value = _duration_seconds(record) if field == "duration_seconds" else record.get(field)
            if point := _health_point(sensor_key, _record_start(record), value, device_name):
                points.append(point)

    for record in _records(payload, "nutrition"):
        start = _record_start(record)
        for field in NUTRITION_FIELDS:
            if point := _health_point(
                f"nutrition_{field}", start, record.get(field), device_name
            ):
                points.append(point)

    return points


def _screen_history(payload: dict[str, Any], device_name: str) -> list[_HistoryPoint]:
    """Return one dated screen-time point for each reported day and app."""
    points: list[_HistoryPoint] = []
    for day in _records(payload, "screen_time"):
        start = _parse_time(day.get("date"))
        total = _number(day.get("total_screen_time_minutes"))
        if start is None:
            continue
        start = _hour_start(start)
        if total is not None:
            points.append(
                _HistoryPoint(
                    key="screen_time_daily",
                    name=f"{device_name} Screen Time per day",
                    unit="min",
                    start=start,
                    value=total,
                )
            )
        for app in _records(day, "apps"):
            package = app.get("package")
            minutes = _number(app.get("minutes"))
            if not isinstance(package, str) or not package or minutes is None:
                continue
            app_name = resolve_app_name(
                package, app.get("name") if isinstance(app.get("name"), str) else None
            )
            points.append(
                _HistoryPoint(
                    key=f"screen_app_{sha256(package.encode()).hexdigest()[:16]}",
                    name=f"{device_name} Screen Time {app_name} ({package}) per day",
                    unit="min",
                    start=start,
                    value=minutes,
                )
            )
    return points


def _import_points(hass: HomeAssistant, entry_id: str, points: list[_HistoryPoint]) -> None:
    """Batch points into hourly measurement statistics and queue them in Recorder."""
    grouped: dict[str, list[_HistoryPoint]] = defaultdict(list)
    for point in points:
        grouped[point.key].append(point)

    for key, series in grouped.items():
        first = series[0]
        values_by_hour: dict[datetime, list[float]] = defaultdict(list)
        for point in series:
            values_by_hour[point.start].append(point.value)
        statistics = [
            StatisticData(
                start=start,
                mean=fmean(values),
                min=min(values),
                max=max(values),
            )
            for start, values in sorted(values_by_hour.items())
        ]
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_mean=True,
            has_sum=False,
            name=first.name,
            source=DOMAIN,
            statistic_id=f"{DOMAIN}:{entry_id}_{key}",
            unit_class=None,
            unit_of_measurement=first.unit,
        )
        async_add_external_statistics(hass, metadata, statistics)


async def async_import_history(
    hass: HomeAssistant,
    entry_id: str,
    payload: dict[str, Any],
    device_name: str = "Life Dashboard",
) -> None:
    """Import webhook observations without adding entities to the device page."""
    source = payload.get("source")
    if source in {"health_connect", "healthkit_ios"}:
        points = _health_history(payload, device_name)
    elif source == "screen_time":
        points = _screen_history(payload, device_name)
    else:
        return

    if not points:
        return
    try:
        _import_points(hass, entry_id, points)
    except Exception:
        # History must not make the primary webhook ingestion fail or be retried.
        _LOGGER.exception("Unable to import Life Dashboard detailed history")


"""Pure payload parsing for Life Dashboard Companion webhooks.

This module intentionally has no Home Assistant imports so its normalization logic can
be tested independently.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

SensorState = dict[str, Any]
StateUpdates = dict[str, SensorState]

# Avoid creating an entity for every package Android reports. An app becomes a
# known app after it exceeds this amount on any reported day; once known, the
# runtime keeps it so its entity can continue to report quieter or zero-use days.
SCREEN_APP_DISCOVERY_THRESHOLD_MINUTES = 10


def _state(value: Any, **attributes: Any) -> SensorState:
    """Build a normalized sensor state."""
    return {
        "value": value,
        "attributes": {key: val for key, val in attributes.items() if val is not None},
    }


def _timestamp_value(value: Any) -> float:
    """Convert an ISO timestamp into a sortable value."""
    if not isinstance(value, str):
        return float("-inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def _record_time(record: dict[str, Any]) -> float:
    """Return the most useful timestamp in a webhook record."""
    for key in (
        "time",
        "session_end_time",
        "end_time",
        "bucket_end",
        "start_time",
        "bucket_start",
    ):
        if key in record:
            return _timestamp_value(record.get(key))
    return float("-inf")


def _latest(records: Any) -> dict[str, Any] | None:
    """Return the newest mapping in an array."""
    if not isinstance(records, list):
        return None
    candidates = [item for item in records if isinstance(item, dict)]
    if not candidates:
        return None
    return max(candidates, key=_record_time)


def _record_attrs(record: dict[str, Any]) -> dict[str, Any]:
    """Return compact metadata useful in Home Assistant without storing raw payloads."""
    keys = (
        "time",
        "start_time",
        "end_time",
        "session_end_time",
        "source",
        "uuid",
        "bucket_start",
        "bucket_end",
        "sample_count",
        "min",
        "max",
        "sources",
        "name",
        "meal_type",
        "type",
        "title",
    )
    return {key: record[key] for key in keys if key in record and record[key] is not None}


def _duration_seconds(record: dict[str, Any]) -> float | int | None:
    """Return a record duration, calculating it from timestamps when needed."""
    if isinstance(record.get("duration_seconds"), (int, float)):
        return record["duration_seconds"]
    start = record.get("start_time")
    end = record.get("end_time")
    if isinstance(start, str) and isinstance(end, str):
        try:
            delta = datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(
                start.replace("Z", "+00:00")
            )
            return max(delta.total_seconds(), 0)
        except ValueError:
            return None
    return None


def _measurement(record: dict[str, Any], field: str) -> Any:
    """Read a raw measurement or an aggregate bucket average."""
    if "bucket_start" in record:
        return record.get("avg")
    return record.get(field)


def _accumulated(record: dict[str, Any], field: str) -> Any:
    """Read a raw accumulated quantity or an aggregate bucket total."""
    if "bucket_start" in record:
        return record.get("total")
    return record.get(field)


POINT_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("weight", "kilograms", "weight"),
    ("height", "meters", "height"),
    ("body_temperature", "celsius", "body_temperature"),
    ("basal_body_temperature", "celsius", "basal_body_temperature"),
    ("body_fat", "percentage", "body_fat"),
    ("lean_body_mass", "kilograms", "lean_body_mass"),
    ("bone_mass", "kilograms", "bone_mass"),
    ("body_water_mass", "kilograms", "body_water_mass"),
    ("heart_rate", "bpm", "heart_rate"),
    ("resting_heart_rate", "bpm", "resting_heart_rate"),
    ("heart_rate_variability", "heart_rate_variability_millis", "heart_rate_variability"),
    ("blood_glucose", "mmol_per_liter", "blood_glucose"),
    ("oxygen_saturation", "percentage", "oxygen_saturation"),
    ("respiratory_rate", "rate", "respiratory_rate"),
    ("basal_metabolic_rate", "kilocalories_per_day", "basal_metabolic_rate"),
    ("vo2_max", "vo2_ml_per_min_per_kg", "vo2_max"),
)

NUTRITION_FIELDS: tuple[str, ...] = (
    "calories",
    "protein_grams",
    "carbs_grams",
    "fat_grams",
    "energy_from_fat_kcal",
    "dietary_fibre_g",
    "sugars_g",
    "saturated_fat_g",
    "monounsaturated_fat_g",
    "polyunsaturated_fat_g",
    "unsaturated_fat_g",
    "trans_fat_g",
    "cholesterol_mg",
    "sodium_mg",
    "potassium_mg",
    "calcium_mg",
    "chloride_mg",
    "chromium_mcg",
    "copper_mg",
    "iodine_mcg",
    "iron_mg",
    "magnesium_mg",
    "manganese_mg",
    "molybdenum_mcg",
    "phosphorus_mg",
    "selenium_mcg",
    "zinc_mg",
    "vitamin_a_mcg",
    "vitamin_b6_mg",
    "vitamin_b12_mcg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_e_mg",
    "vitamin_k_mcg",
    "thiamin_mg",
    "riboflavin_mg",
    "niacin_mg",
    "pantothenic_acid_mg",
    "biotin_mcg",
    "folate_mcg",
    "folic_acid_mcg",
    "caffeine_mg",
)


def normalize_health(payload: dict[str, Any]) -> StateUpdates:
    """Normalize a Health Connect or HealthKit payload into scalar HA states."""
    updates: StateUpdates = {}
    payload_timestamp = payload.get("timestamp")
    app_version = payload.get("app_version")

    if payload_timestamp:
        updates["health_last_sync"] = _state(payload_timestamp, app_version=app_version)
    if app_version:
        updates["health_app_version"] = _state(app_version)

    daily_totals = payload.get("daily_totals")
    if isinstance(daily_totals, list) and daily_totals:
        daily = max(
            (item for item in daily_totals if isinstance(item, dict)),
            key=lambda item: str(item.get("date", "")),
            default=None,
        )
        if daily:
            date = daily.get("date")
            for field, key in (
                ("steps", "steps_today"),
                ("distance_meters", "distance_today"),
                ("active_calories", "active_calories_today"),
                ("total_calories", "total_calories_today"),
            ):
                if field in daily:
                    updates[key] = _state(daily.get(field), date=date, source="daily_totals")

    # Expose the latest raw/bucket interval as well, so accumulated metrics still have
    # useful entities when daily_totals is disabled in the Android app.
    for payload_key, field, sensor_key in (
        ("steps", "count", "steps_latest_interval"),
        ("distance", "meters", "distance_latest_interval"),
        ("active_calories", "calories", "active_calories_latest_interval"),
        ("total_calories", "calories", "total_calories_latest_interval"),
    ):
        record = _latest(payload.get(payload_key))
        if record:
            updates[sensor_key] = _state(_accumulated(record, field), **_record_attrs(record))

    for payload_key, field, sensor_key in POINT_MAPPINGS:
        record = _latest(payload.get(payload_key))
        if record:
            updates[sensor_key] = _state(_measurement(record, field), **_record_attrs(record))

    skin = _latest(payload.get("skin_temperature"))
    if skin:
        updates["skin_temperature_delta"] = _state(
            _measurement(skin, "delta_celsius"), **_record_attrs(skin)
        )
        updates["skin_temperature_baseline"] = _state(
            None if "bucket_start" in skin else skin.get("baseline_celsius"),
            **_record_attrs(skin),
        )

    blood_pressure = _latest(payload.get("blood_pressure"))
    if blood_pressure:
        attrs = _record_attrs(blood_pressure)
        updates["blood_pressure_systolic"] = _state(blood_pressure.get("systolic"), **attrs)
        updates["blood_pressure_diastolic"] = _state(blood_pressure.get("diastolic"), **attrs)

    sleep = _latest(payload.get("sleep"))
    if sleep:
        attrs = _record_attrs(sleep)
        updates["sleep_duration"] = _state(sleep.get("duration_seconds"), **attrs)
        updates["sleep_session_end"] = _state(sleep.get("session_end_time"), **attrs)
        stage_totals: dict[str, float] = defaultdict(float)
        for stage in sleep.get("stages", []) if isinstance(sleep.get("stages"), list) else []:
            if not isinstance(stage, dict):
                continue
            stage_name = str(stage.get("stage", "unknown"))
            duration = _duration_seconds(stage)
            if isinstance(duration, (int, float)):
                stage_totals[stage_name] += float(duration)
        for stage_name in (
            "unknown",
            "awake",
            "sleeping",
            "out_of_bed",
            "light",
            "deep",
            "rem",
            "awake_in_bed",
        ):
            updates[f"sleep_stage_{stage_name}"] = _state(stage_totals.get(stage_name, 0), **attrs)

    exercise = _latest(payload.get("exercise"))
    if exercise:
        attrs = _record_attrs(exercise)
        updates["exercise_type"] = _state(exercise.get("type"), **attrs)
        updates["exercise_duration"] = _state(_duration_seconds(exercise), **attrs)
        updates["exercise_start"] = _state(exercise.get("start_time"), **attrs)
        updates["exercise_end"] = _state(exercise.get("end_time"), **attrs)

    hydration = _latest(payload.get("hydration"))
    if hydration:
        attrs = _record_attrs(hydration)
        updates["hydration"] = _state(hydration.get("liters"), **attrs)
        updates["hydration_time"] = _state(
            hydration.get("end_time") or hydration.get("start_time"), **attrs
        )

    nutrition = _latest(payload.get("nutrition"))
    if nutrition:
        attrs = _record_attrs(nutrition)
        meal_label = nutrition.get("name") or nutrition.get("meal_type") or "meal"
        updates["nutrition_meal"] = _state(meal_label, **attrs)
        updates["nutrition_meal_type"] = _state(nutrition.get("meal_type"), **attrs)
        updates["nutrition_time"] = _state(
            nutrition.get("end_time") or nutrition.get("start_time"), **attrs
        )
        for field in NUTRITION_FIELDS:
            updates[f"nutrition_{field}"] = _state(nutrition.get(field), **attrs)

    mindfulness = _latest(payload.get("mindfulness"))
    if mindfulness:
        attrs = _record_attrs(mindfulness)
        updates["mindfulness_title"] = _state(mindfulness.get("title") or "Mindfulness", **attrs)
        updates["mindfulness_duration"] = _state(_duration_seconds(mindfulness), **attrs)
        updates["mindfulness_start"] = _state(mindfulness.get("start_time"), **attrs)
        updates["mindfulness_end"] = _state(mindfulness.get("end_time"), **attrs)

    period = _latest(payload.get("menstruation_period"))
    if period:
        attrs = _record_attrs(period)
        updates["menstruation_period_start"] = _state(period.get("start_time"), **attrs)
        updates["menstruation_period_end"] = _state(period.get("end_time"), **attrs)
        updates["menstruation_period_duration"] = _state(_duration_seconds(period), **attrs)

    flow = _latest(payload.get("menstruation_flow"))
    if flow:
        attrs = _record_attrs(flow)
        updates["menstruation_flow"] = _state(flow.get("flow"), **attrs)
        updates["menstruation_flow_time"] = _state(flow.get("time"), **attrs)

    bleeding = _latest(payload.get("intermenstrual_bleeding"))
    if bleeding:
        updates["intermenstrual_bleeding_time"] = _state(
            bleeding.get("time"), **_record_attrs(bleeding)
        )

    ovulation = _latest(payload.get("ovulation_test"))
    if ovulation:
        attrs = _record_attrs(ovulation)
        updates["ovulation_test"] = _state(ovulation.get("result"), **attrs)
        updates["ovulation_test_time"] = _state(ovulation.get("time"), **attrs)

    mucus = _latest(payload.get("cervical_mucus"))
    if mucus:
        attrs = _record_attrs(mucus)
        updates["cervical_mucus_appearance"] = _state(mucus.get("appearance"), **attrs)
        updates["cervical_mucus_sensation"] = _state(mucus.get("sensation"), **attrs)
        updates["cervical_mucus_time"] = _state(mucus.get("time"), **attrs)

    sexual = _latest(payload.get("sexual_activity"))
    if sexual:
        attrs = _record_attrs(sexual)
        updates["sexual_activity"] = _state(sexual.get("protection_used"), **attrs)
        updates["sexual_activity_time"] = _state(sexual.get("time"), **attrs)

    return updates


def normalize_screen_time(payload: dict[str, Any]) -> tuple[StateUpdates, dict[str, str]]:
    """Normalize a screen-time payload and return any discovered app packages."""
    updates: StateUpdates = {}
    discovered_apps: dict[str, str] = {}
    payload_timestamp = payload.get("timestamp")
    app_version = payload.get("app_version")
    device = payload.get("device")

    if payload_timestamp:
        updates["screen_last_sync"] = _state(
            payload_timestamp, app_version=app_version, reported_device=device
        )
    if app_version:
        updates["screen_app_version"] = _state(app_version, reported_device=device)

    days = [
        day
        for day in payload.get("screen_time", [])
        if isinstance(day, dict) and isinstance(day.get("date"), str)
    ]
    if not days:
        return updates, discovered_apps

    days.sort(key=lambda item: item["date"])
    latest_day = days[-1]
    previous_day = days[-2] if len(days) > 1 else None

    updates["screen_time_today"] = _state(
        latest_day.get("total_screen_time_minutes"),
        date=latest_day.get("date"),
        reported_device=device,
        daily_totals={
            day["date"]: day.get("total_screen_time_minutes") for day in days[-7:]
        },
    )
    if previous_day:
        updates["screen_time_yesterday"] = _state(
            previous_day.get("total_screen_time_minutes"),
            date=previous_day.get("date"),
            reported_device=device,
        )

    seven_day_total = sum(
        day.get("total_screen_time_minutes", 0)
        for day in days[-7:]
        if isinstance(day.get("total_screen_time_minutes"), (int, float))
    )
    updates["screen_time_7d"] = _state(
        seven_day_total,
        start_date=days[-7:][0].get("date"),
        end_date=latest_day.get("date"),
        reported_device=device,
    )

    current_apps: dict[str, dict[str, Any]] = {}
    seven_day_by_package: dict[str, float] = defaultdict(float)
    last_used_by_package: dict[str, str] = {}
    app_name_by_package: dict[str, str] = {}

    for day in days[-7:]:
        apps = day.get("apps", [])
        if not isinstance(apps, list):
            continue
        for app in apps:
            if not isinstance(app, dict):
                continue
            package = app.get("package")
            if not isinstance(package, str) or not package:
                continue
            name = app.get("name") if isinstance(app.get("name"), str) else package
            app_name_by_package[package] = name
            minutes = app.get("minutes")
            if isinstance(minutes, (int, float)):
                seven_day_by_package[package] += float(minutes)
                if minutes > SCREEN_APP_DISCOVERY_THRESHOLD_MINUTES:
                    discovered_apps[package] = name
            last_used = app.get("last_used")
            if isinstance(last_used, str) and (
                package not in last_used_by_package
                or _timestamp_value(last_used) > _timestamp_value(last_used_by_package[package])
            ):
                last_used_by_package[package] = last_used

    latest_apps = latest_day.get("apps", [])
    if isinstance(latest_apps, list):
        for app in latest_apps:
            if not isinstance(app, dict):
                continue
            package = app.get("package")
            if isinstance(package, str) and package:
                current_apps[package] = app

    top_app: dict[str, Any] | None = None
    if current_apps:
        top_app = max(
            current_apps.values(),
            key=lambda item: item.get("minutes", 0)
            if isinstance(item.get("minutes"), (int, float))
            else 0,
        )
    if top_app:
        updates["screen_top_app"] = _state(
            top_app.get("name") or top_app.get("package"),
            package=top_app.get("package"),
            minutes=top_app.get("minutes"),
            last_used=top_app.get("last_used"),
            date=latest_day.get("date"),
        )

    # Build states for every reported package, including already-known apps that
    # no longer meet the discovery threshold. The runtime decides which new app
    # entities to create, while existing ones can still update to zero minutes.
    for package, name in app_name_by_package.items():
        app = current_apps.get(package, {})
        minutes = app.get("minutes", 0)
        if not isinstance(minutes, (int, float)):
            minutes = 0
        updates[f"screen_app::{package}"] = _state(
            minutes,
            package=package,
            app_name=name,
            date=latest_day.get("date"),
            last_used=app.get("last_used") or last_used_by_package.get(package),
            seven_day_minutes=round(seven_day_by_package.get(package, 0), 2),
        )

    return updates, discovered_apps

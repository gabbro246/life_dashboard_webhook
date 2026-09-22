"""Sensor definitions for Life Dashboard Webhook."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import EntityCategory

from .const import DEVICE_HEALTH, DEVICE_SCREEN_TIME
from .parser import NUTRITION_FIELDS


@dataclass(frozen=True, slots=True)
class SensorDefinition:
    """Describe a Life Dashboard sensor."""

    key: str
    name: str
    device_group: str
    unit: str | None = None
    icon: str | None = None
    state_class: SensorStateClass | None = None
    timestamp: bool = False
    entity_category: EntityCategory | None = None
    suggested_display_precision: int | None = None
    enabled_default: bool | None = None


def _health(
    key: str,
    name: str,
    unit: str | None = None,
    icon: str | None = None,
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    *,
    timestamp: bool = False,
    entity_category: EntityCategory | None = None,
    precision: int | None = None,
) -> SensorDefinition:
    return SensorDefinition(
        key,
        name,
        DEVICE_HEALTH,
        unit,
        icon,
        state_class,
        timestamp,
        entity_category,
        precision,
    )


def _screen(
    key: str,
    name: str,
    unit: str | None = None,
    icon: str | None = None,
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    *,
    timestamp: bool = False,
    entity_category: EntityCategory | None = None,
    enabled_default: bool | None = None,
) -> SensorDefinition:
    return SensorDefinition(
        key,
        name,
        DEVICE_SCREEN_TIME,
        unit,
        icon,
        state_class,
        timestamp,
        entity_category,
        None,
        enabled_default,
    )


HEALTH_SENSOR_DEFINITIONS: list[SensorDefinition] = [
    _health("steps_today", "Steps today", "steps", "mdi:walk", SensorStateClass.TOTAL),
    _health("steps_latest_interval", "Steps latest interval", "steps", "mdi:walk", SensorStateClass.TOTAL),
    _health("distance_today", "Distance today", "m", "mdi:map-marker-distance", SensorStateClass.TOTAL, precision=1),
    _health("distance_latest_interval", "Distance latest interval", "m", "mdi:map-marker-distance", SensorStateClass.TOTAL, precision=1),
    _health("active_calories_today", "Active calories today", "kcal", "mdi:fire", SensorStateClass.TOTAL, precision=1),
    _health("active_calories_latest_interval", "Active calories latest interval", "kcal", "mdi:fire", SensorStateClass.TOTAL, precision=1),
    _health("total_calories_today", "Total calories today", "kcal", "mdi:fire", SensorStateClass.TOTAL, precision=1),
    _health("total_calories_latest_interval", "Total calories latest interval", "kcal", "mdi:fire", SensorStateClass.TOTAL, precision=1),
    _health("weight", "Weight", "kg", "mdi:weight-kilogram", precision=2),
    _health("height", "Height", "m", "mdi:human-male-height", precision=3),
    _health("body_temperature", "Body temperature", "°C", "mdi:thermometer", precision=2),
    _health("skin_temperature_delta", "Skin temperature delta", "°C", "mdi:thermometer-lines", precision=2),
    _health("skin_temperature_baseline", "Skin temperature baseline", "°C", "mdi:thermometer-lines", precision=2),
    _health("basal_body_temperature", "Basal body temperature", "°C", "mdi:thermometer", precision=2),
    _health("body_fat", "Body fat", "%", "mdi:percent", precision=1),
    _health("lean_body_mass", "Lean body mass", "kg", "mdi:weight-kilogram", precision=2),
    _health("bone_mass", "Bone mass", "kg", "mdi:bone", precision=2),
    _health("body_water_mass", "Body water mass", "kg", "mdi:water", precision=2),
    _health("heart_rate", "Heart rate", "bpm", "mdi:heart-pulse", precision=1),
    _health("resting_heart_rate", "Resting heart rate", "bpm", "mdi:heart-outline", precision=1),
    _health("heart_rate_variability", "Heart rate variability", "ms", "mdi:heart-cog", precision=2),
    _health("blood_pressure_systolic", "Blood pressure systolic", "mmHg", "mdi:gauge", precision=1),
    _health("blood_pressure_diastolic", "Blood pressure diastolic", "mmHg", "mdi:gauge", precision=1),
    _health("blood_glucose", "Blood glucose", "mmol/L", "mdi:water-percent", precision=2),
    _health("oxygen_saturation", "Oxygen saturation", "%", "mdi:percent", precision=1),
    _health("respiratory_rate", "Respiratory rate", "breaths/min", "mdi:lungs", precision=1),
    _health("basal_metabolic_rate", "Basal metabolic rate", "kcal/d", "mdi:fire", precision=1),
    _health("vo2_max", "VO2 max", "mL/min/kg", "mdi:run-fast", precision=1),
    _health("sleep_duration", "Sleep duration", "s", "mdi:sleep", precision=0),
    _health("sleep_session_end", "Sleep session end", None, "mdi:sleep", None, timestamp=True),
    _health("sleep_stage_unknown", "Sleep unknown stage", "s", "mdi:sleep", precision=0),
    _health("sleep_stage_awake", "Sleep awake", "s", "mdi:eye", precision=0),
    _health("sleep_stage_sleeping", "Sleep generic", "s", "mdi:sleep", precision=0),
    _health("sleep_stage_out_of_bed", "Sleep out of bed", "s", "mdi:bed-empty", precision=0),
    _health("sleep_stage_light", "Sleep light", "s", "mdi:weather-night", precision=0),
    _health("sleep_stage_deep", "Sleep deep", "s", "mdi:weather-night", precision=0),
    _health("sleep_stage_rem", "Sleep REM", "s", "mdi:brain", precision=0),
    _health("sleep_stage_awake_in_bed", "Sleep awake in bed", "s", "mdi:bed-clock", precision=0),
    _health("exercise_type", "Latest exercise", None, "mdi:run", None),
    _health("exercise_duration", "Latest exercise duration", "s", "mdi:timer", precision=0),
    _health("exercise_start", "Latest exercise start", None, "mdi:clock-start", None, timestamp=True),
    _health("exercise_end", "Latest exercise end", None, "mdi:clock-end", None, timestamp=True),
    _health("hydration", "Latest hydration", "L", "mdi:cup-water", precision=3),
    _health("hydration_time", "Latest hydration time", None, "mdi:clock-outline", None, timestamp=True),
    _health("nutrition_meal", "Latest meal", None, "mdi:food", None),
    _health("nutrition_meal_type", "Latest meal type", None, "mdi:food-variant", None),
    _health("nutrition_time", "Latest meal time", None, "mdi:clock-outline", None, timestamp=True),
    _health("mindfulness_title", "Latest mindfulness session", None, "mdi:meditation", None),
    _health("mindfulness_duration", "Latest mindfulness duration", "s", "mdi:timer", precision=0),
    _health("mindfulness_start", "Latest mindfulness start", None, "mdi:clock-start", None, timestamp=True),
    _health("mindfulness_end", "Latest mindfulness end", None, "mdi:clock-end", None, timestamp=True),
    _health("menstruation_period_start", "Latest menstruation period start", None, "mdi:calendar-start", None, timestamp=True),
    _health("menstruation_period_end", "Latest menstruation period end", None, "mdi:calendar-end", None, timestamp=True),
    _health("menstruation_period_duration", "Latest menstruation period duration", "s", "mdi:calendar-range", precision=0),
    _health("menstruation_flow", "Latest menstruation flow", None, "mdi:water", None),
    _health("menstruation_flow_time", "Latest menstruation flow time", None, "mdi:clock-outline", None, timestamp=True),
    _health("intermenstrual_bleeding_time", "Latest intermenstrual bleeding", None, "mdi:calendar-alert", None, timestamp=True),
    _health("ovulation_test", "Latest ovulation test", None, "mdi:test-tube", None),
    _health("ovulation_test_time", "Latest ovulation test time", None, "mdi:clock-outline", None, timestamp=True),
    _health("cervical_mucus_appearance", "Latest cervical mucus appearance", None, "mdi:water-outline", None),
    _health("cervical_mucus_sensation", "Latest cervical mucus sensation", None, "mdi:water-outline", None),
    _health("cervical_mucus_time", "Latest cervical mucus time", None, "mdi:clock-outline", None, timestamp=True),
    _health("sexual_activity", "Latest sexual activity", None, "mdi:heart", None),
    _health("sexual_activity_time", "Latest sexual activity time", None, "mdi:clock-outline", None, timestamp=True),
    _health(
        "health_last_sync",
        "Last webhook sync",
        None,
        "mdi:webhook",
        None,
        timestamp=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _health(
        "health_app_version",
        "App version",
        None,
        "mdi:application-cog",
        None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

NUTRITION_LABELS: dict[str, str] = {
    "calories": "Calories",
    "protein_grams": "Protein",
    "carbs_grams": "Carbohydrates",
    "fat_grams": "Fat",
    "energy_from_fat_kcal": "Energy from fat",
    "dietary_fibre_g": "Dietary fibre",
    "sugars_g": "Sugars",
    "saturated_fat_g": "Saturated fat",
    "monounsaturated_fat_g": "Monounsaturated fat",
    "polyunsaturated_fat_g": "Polyunsaturated fat",
    "unsaturated_fat_g": "Unsaturated fat",
    "trans_fat_g": "Trans fat",
    "cholesterol_mg": "Cholesterol",
    "sodium_mg": "Sodium",
    "potassium_mg": "Potassium",
    "calcium_mg": "Calcium",
    "chloride_mg": "Chloride",
    "chromium_mcg": "Chromium",
    "copper_mg": "Copper",
    "iodine_mcg": "Iodine",
    "iron_mg": "Iron",
    "magnesium_mg": "Magnesium",
    "manganese_mg": "Manganese",
    "molybdenum_mcg": "Molybdenum",
    "phosphorus_mg": "Phosphorus",
    "selenium_mcg": "Selenium",
    "zinc_mg": "Zinc",
    "vitamin_a_mcg": "Vitamin A",
    "vitamin_b6_mg": "Vitamin B6",
    "vitamin_b12_mcg": "Vitamin B12",
    "vitamin_c_mg": "Vitamin C",
    "vitamin_d_mcg": "Vitamin D",
    "vitamin_e_mg": "Vitamin E",
    "vitamin_k_mcg": "Vitamin K",
    "thiamin_mg": "Thiamin",
    "riboflavin_mg": "Riboflavin",
    "niacin_mg": "Niacin",
    "pantothenic_acid_mg": "Pantothenic acid",
    "biotin_mcg": "Biotin",
    "folate_mcg": "Folate",
    "folic_acid_mcg": "Folic acid",
    "caffeine_mg": "Caffeine",
}

for field in NUTRITION_FIELDS:
    if field.endswith("_grams") or field.endswith("_g"):
        unit = "g"
    elif field.endswith("_mg"):
        unit = "mg"
    elif field.endswith("_mcg"):
        unit = "µg"
    elif field.endswith("_kcal") or field == "calories":
        unit = "kcal"
    else:
        unit = None
    HEALTH_SENSOR_DEFINITIONS.append(
        _health(
            f"nutrition_{field}",
            f"Latest meal {NUTRITION_LABELS.get(field, field.replace('_', ' '))}",
            unit,
            "mdi:nutrition",
            SensorStateClass.MEASUREMENT,
            precision=2,
        )
    )

SCREEN_SENSOR_DEFINITIONS: list[SensorDefinition] = [
    _screen(
        "screen_time_today",
        "Screen time today",
        "min",
        "mdi:calendar-today",
        SensorStateClass.TOTAL,
        enabled_default=True,
    ),
    _screen(
        "screen_time_yesterday",
        "Screen time yesterday",
        "min",
        "mdi:calendar-arrow-left",
        SensorStateClass.TOTAL,
        enabled_default=True,
    ),
    _screen(
        "screen_time_7d",
        "Screen time last 7 days",
        "min",
        "mdi:calendar-week",
        SensorStateClass.TOTAL,
        enabled_default=True,
    ),
    _screen(
        "screen_top_app",
        "Most used app today",
        None,
        "mdi:timer-alert-outline",
        None,
        enabled_default=True,
    ),
    _screen(
        "screen_last_sync",
        "Last webhook sync",
        None,
        "mdi:webhook",
        None,
        timestamp=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=True,
    ),
    _screen(
        "screen_app_version",
        "App version",
        None,
        "mdi:application-cog",
        None,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
]

STATIC_SENSOR_DEFINITIONS = HEALTH_SENSOR_DEFINITIONS + SCREEN_SENSOR_DEFINITIONS

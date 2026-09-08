PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_id       INTEGER PRIMARY KEY,
    full_date     DATE NOT NULL UNIQUE,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month         INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name    TEXT NOT NULL,
    week          INTEGER NOT NULL,
    day_of_week   TEXT NOT NULL,
    is_weekend    INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

DROP TABLE IF EXISTS dim_car_model;
CREATE TABLE dim_car_model (
    model_id                     INTEGER PRIMARY KEY,
    model_name                   TEXT NOT NULL UNIQUE,
    segment                      TEXT NOT NULL,
    engine_type                  TEXT NOT NULL,
    transmission_type            TEXT NOT NULL,
    drivetrain                   TEXT NOT NULL,
    base_price                   REAL NOT NULL CHECK (base_price > 0),
    standard_labor_hours         REAL NOT NULL CHECK (standard_labor_hours > 0),
    standard_cycle_time_minutes  REAL NOT NULL CHECK (standard_cycle_time_minutes > 0)
);

DROP TABLE IF EXISTS dim_trim_level;
CREATE TABLE dim_trim_level (
    trim_id        INTEGER PRIMARY KEY,
    model_id       INTEGER NOT NULL REFERENCES dim_car_model(model_id),
    trim_name      TEXT NOT NULL,
    price_premium  REAL NOT NULL CHECK (price_premium >= 0),
    UNIQUE (model_id, trim_name)
);

DROP TABLE IF EXISTS dim_color;
CREATE TABLE dim_color (
    color_id       INTEGER PRIMARY KEY,
    color_name     TEXT NOT NULL UNIQUE,
    color_type     TEXT NOT NULL CHECK (color_type IN ('Solid', 'Metallic', 'Pearl')),
    price_premium  REAL NOT NULL CHECK (price_premium >= 0)
);

DROP TABLE IF EXISTS dim_upholstery;
CREATE TABLE dim_upholstery (
    upholstery_id  INTEGER PRIMARY KEY,
    material       TEXT NOT NULL,
    color          TEXT NOT NULL,
    price_premium  REAL NOT NULL CHECK (price_premium >= 0)
);

DROP TABLE IF EXISTS dim_supplier;
CREATE TABLE dim_supplier (
    supplier_id           INTEGER PRIMARY KEY,
    supplier_name         TEXT NOT NULL UNIQUE,
    country               TEXT NOT NULL,
    reliability_score     REAL NOT NULL CHECK (reliability_score BETWEEN 0 AND 100),
    avg_lead_time_days    INTEGER NOT NULL CHECK (avg_lead_time_days > 0),
    contract_start_date   DATE NOT NULL
);

DROP TABLE IF EXISTS dim_part;
CREATE TABLE dim_part (
    part_id               INTEGER PRIMARY KEY,
    part_name             TEXT NOT NULL,
    part_category         TEXT NOT NULL,
    primary_supplier_id   INTEGER NOT NULL REFERENCES dim_supplier(supplier_id),
    unit_cost             REAL NOT NULL CHECK (unit_cost > 0),
    complexity_score      INTEGER NOT NULL CHECK (complexity_score BETWEEN 1 AND 10)
);

DROP TABLE IF EXISTS dim_workstation;
CREATE TABLE dim_workstation (
    station_id                    INTEGER PRIMARY KEY,
    station_name                  TEXT NOT NULL UNIQUE,
    station_sequence_order        INTEGER NOT NULL UNIQUE,
    station_type                  TEXT NOT NULL,
    standard_cycle_time_minutes   REAL NOT NULL CHECK (standard_cycle_time_minutes > 0),
    max_capacity_per_shift        INTEGER NOT NULL CHECK (max_capacity_per_shift > 0)
);

DROP TABLE IF EXISTS dim_worker;
CREATE TABLE dim_worker (
    worker_id            INTEGER PRIMARY KEY,
    worker_name          TEXT NOT NULL,
    skill_level          TEXT NOT NULL CHECK (skill_level IN ('Junior', 'Mid', 'Senior')),
    hire_date            DATE NOT NULL,
    default_station_id   INTEGER NOT NULL REFERENCES dim_workstation(station_id),
    hourly_wage          REAL NOT NULL CHECK (hourly_wage > 0)
);

DROP TABLE IF EXISTS dim_shift;
CREATE TABLE dim_shift (
    shift_id     INTEGER PRIMARY KEY,
    shift_name   TEXT NOT NULL UNIQUE,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL
);

DROP TABLE IF EXISTS bridge_model_trim_bom;
CREATE TABLE bridge_model_trim_bom (
    bom_id              INTEGER PRIMARY KEY,
    model_id            INTEGER NOT NULL REFERENCES dim_car_model(model_id),
    trim_id             INTEGER NOT NULL REFERENCES dim_trim_level(trim_id),
    part_id             INTEGER NOT NULL REFERENCES dim_part(part_id),
    quantity_required   INTEGER NOT NULL CHECK (quantity_required > 0),
    UNIQUE (trim_id, part_id)
);

DROP TABLE IF EXISTS fact_production_order;
CREATE TABLE fact_production_order (
    order_id            INTEGER PRIMARY KEY,
    model_id            INTEGER NOT NULL REFERENCES dim_car_model(model_id),
    trim_id             INTEGER NOT NULL REFERENCES dim_trim_level(trim_id),
    color_id            INTEGER NOT NULL REFERENCES dim_color(color_id),
    upholstery_id       INTEGER NOT NULL REFERENCES dim_upholstery(upholstery_id),
    order_date_id       INTEGER NOT NULL REFERENCES dim_date(date_id),
    planned_quantity    INTEGER NOT NULL CHECK (planned_quantity > 0),
    priority_level      TEXT NOT NULL CHECK (priority_level IN ('Low', 'Medium', 'High'))
);

DROP TABLE IF EXISTS fact_production_unit;
CREATE TABLE fact_production_unit (
    unit_id                            TEXT PRIMARY KEY,
    order_id                           INTEGER NOT NULL REFERENCES fact_production_order(order_id),
    model_id                           INTEGER NOT NULL REFERENCES dim_car_model(model_id),
    trim_id                            INTEGER NOT NULL REFERENCES dim_trim_level(trim_id),
    color_id                           INTEGER NOT NULL REFERENCES dim_color(color_id),
    upholstery_id                      INTEGER NOT NULL REFERENCES dim_upholstery(upholstery_id),
    production_start_date_id           INTEGER NOT NULL REFERENCES dim_date(date_id),
    production_end_date_id             INTEGER NOT NULL REFERENCES dim_date(date_id),
    shift_id                           INTEGER NOT NULL REFERENCES dim_shift(shift_id),
    total_actual_labor_hours           REAL NOT NULL CHECK (total_actual_labor_hours >= 0),
    total_actual_cycle_time_minutes    REAL NOT NULL CHECK (total_actual_cycle_time_minutes >= 0),
    total_material_cost                REAL NOT NULL CHECK (total_material_cost >= 0),
    total_labor_cost                   REAL NOT NULL CHECK (total_labor_cost >= 0),
    total_rework_cost                  REAL NOT NULL CHECK (total_rework_cost >= 0),
    total_cost                         REAL NOT NULL CHECK (total_cost >= 0),
    final_qc_status                    TEXT NOT NULL CHECK (final_qc_status IN ('Pass', 'Rework', 'Fail'))
);

DROP TABLE IF EXISTS fact_station_operation;
CREATE TABLE fact_station_operation (
    operation_id                    INTEGER PRIMARY KEY,
    unit_id                         TEXT NOT NULL REFERENCES fact_production_unit(unit_id),
    station_id                      INTEGER NOT NULL REFERENCES dim_workstation(station_id),
    worker_id                       INTEGER NOT NULL REFERENCES dim_worker(worker_id),
    shift_id                        INTEGER NOT NULL REFERENCES dim_shift(shift_id),
    date_id                         INTEGER NOT NULL REFERENCES dim_date(date_id),
    actual_cycle_time_minutes       REAL NOT NULL CHECK (actual_cycle_time_minutes >= 0),
    standard_cycle_time_minutes     REAL NOT NULL CHECK (standard_cycle_time_minutes > 0),
    downtime_minutes                REAL NOT NULL DEFAULT 0 CHECK (downtime_minutes >= 0),
    downtime_reason                 TEXT CHECK (downtime_reason IN ('Machine Failure', 'Material Shortage', 'Changeover') OR downtime_reason IS NULL)
);

DROP TABLE IF EXISTS fact_defect;
CREATE TABLE fact_defect (
    defect_id             INTEGER PRIMARY KEY,
    operation_id          INTEGER NOT NULL REFERENCES fact_station_operation(operation_id),
    unit_id               TEXT NOT NULL REFERENCES fact_production_unit(unit_id),
    part_id               INTEGER REFERENCES dim_part(part_id),
    station_id            INTEGER NOT NULL REFERENCES dim_workstation(station_id),
    defect_type           TEXT NOT NULL CHECK (defect_type IN ('dimensional', 'cosmetic', 'assembly', 'electrical', 'functional')),
    severity              TEXT NOT NULL CHECK (severity IN ('minor', 'major', 'critical')),
    detected_date_id      INTEGER NOT NULL REFERENCES dim_date(date_id),
    resolution            TEXT NOT NULL CHECK (resolution IN ('rework', 'scrap', 'accepted_with_deviation')),
    rework_cost           REAL NOT NULL CHECK (rework_cost >= 0),
    rework_time_minutes   REAL NOT NULL CHECK (rework_time_minutes >= 0)
);

DROP TABLE IF EXISTS fact_material_usage;
CREATE TABLE fact_material_usage (
    usage_id           INTEGER PRIMARY KEY,
    unit_id            TEXT NOT NULL REFERENCES fact_production_unit(unit_id),
    part_id            INTEGER NOT NULL REFERENCES dim_part(part_id),
    supplier_id        INTEGER NOT NULL REFERENCES dim_supplier(supplier_id),
    quantity_used      INTEGER NOT NULL CHECK (quantity_used > 0),
    unit_cost_at_time  REAL NOT NULL CHECK (unit_cost_at_time > 0),
    total_cost         REAL NOT NULL CHECK (total_cost > 0)
);
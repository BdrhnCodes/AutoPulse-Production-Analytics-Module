DROP VIEW IF EXISTS vw_unit_summary;
CREATE VIEW vw_unit_summary AS
SELECT
    u.unit_id,
    m.model_name,
    m.segment,
    m.engine_type,
    t.trim_name,
    c.color_name,
    c.color_type,
    up.material   AS upholstery_material,
    up.color      AS upholstery_color,
    sh.shift_name,
    d_start.full_date   AS production_start_date,
    d_start.year        AS start_year,
    d_start.quarter     AS start_quarter,
    d_start.month       AS start_month,
    d_start.month_name  AS start_month_name,
    d_end.full_date     AS production_end_date,
    u.total_actual_labor_hours,
    u.total_actual_cycle_time_minutes,
    u.total_material_cost,
    u.total_labor_cost,
    u.total_rework_cost,
    u.total_cost,
    u.final_qc_status
FROM fact_production_unit u
JOIN dim_car_model  m        ON u.model_id = m.model_id
JOIN dim_trim_level t        ON u.trim_id = t.trim_id
JOIN dim_color      c        ON u.color_id = c.color_id
JOIN dim_upholstery up       ON u.upholstery_id = up.upholstery_id
JOIN dim_shift       sh      ON u.shift_id = sh.shift_id
JOIN dim_date        d_start ON u.production_start_date_id = d_start.date_id
JOIN dim_date        d_end   ON u.production_end_date_id = d_end.date_id;

DROP VIEW IF EXISTS vw_station_performance;
CREATE VIEW vw_station_performance AS
SELECT
    so.station_id,
    ws.station_name,
    ws.station_type,
    ws.station_sequence_order,
    d.full_date,
    d.year,
    d.month,
    d.month_name,
    d.is_weekend,
    COUNT(*)                                                          AS n_operations,
    ROUND(AVG(so.actual_cycle_time_minutes), 2)                        AS avg_actual_cycle_time,
    ROUND(AVG(so.standard_cycle_time_minutes), 2)                      AS avg_standard_cycle_time,
    ROUND(AVG(so.actual_cycle_time_minutes - so.standard_cycle_time_minutes), 2) AS avg_variance_minutes,
    ROUND(SUM(so.downtime_minutes), 1)                                 AS total_downtime_minutes,
    SUM(CASE WHEN so.downtime_minutes > 0 THEN 1 ELSE 0 END)           AS n_downtime_events
FROM fact_station_operation so
JOIN dim_workstation ws ON so.station_id = ws.station_id
JOIN dim_date d ON so.date_id = d.date_id
GROUP BY so.station_id, ws.station_name, ws.station_type, ws.station_sequence_order,
         d.full_date, d.year, d.month, d.month_name, d.is_weekend;

DROP VIEW IF EXISTS vw_defect_pareto;
CREATE VIEW vw_defect_pareto AS
SELECT
    fd.defect_id,
    fd.detected_date_id,
    d.full_date        AS detected_date,
    d.year,
    d.month,
    d.month_name,
    p.part_name,
    p.part_category,
    s.supplier_name,
    s.reliability_score,
    ws.station_name,
    ws.station_type,
    fd.defect_type,
    fd.severity,
    fd.resolution,
    fd.rework_cost,
    fd.rework_time_minutes
FROM fact_defect fd
JOIN dim_workstation ws ON fd.station_id = ws.station_id
JOIN dim_date d ON fd.detected_date_id = d.date_id
LEFT JOIN dim_part p ON fd.part_id = p.part_id
LEFT JOIN dim_supplier s ON p.primary_supplier_id = s.supplier_id;

DROP VIEW IF EXISTS vw_cost_breakdown;
CREATE VIEW vw_cost_breakdown AS
SELECT
    m.model_name,
    m.segment,
    t.trim_name,
    c.color_name,
    d.year,
    d.month,
    d.month_name,
    COUNT(*)                                     AS n_units,
    ROUND(AVG(u.total_material_cost), 2)          AS avg_material_cost,
    ROUND(AVG(u.total_labor_cost), 2)             AS avg_labor_cost,
    ROUND(AVG(u.total_rework_cost), 2)            AS avg_rework_cost,
    ROUND(AVG(u.total_cost), 2)                   AS avg_total_cost,
    ROUND(SUM(u.total_cost), 2)                   AS sum_total_cost
FROM fact_production_unit u
JOIN dim_car_model  m ON u.model_id = m.model_id
JOIN dim_trim_level t ON u.trim_id = t.trim_id
JOIN dim_color      c ON u.color_id = c.color_id
JOIN dim_date       d ON u.production_start_date_id = d.date_id
GROUP BY m.model_name, m.segment, t.trim_name, c.color_name, d.year, d.month, d.month_name;

DROP VIEW IF EXISTS vw_oee_daily;
CREATE VIEW vw_oee_daily AS
WITH ops AS (
    SELECT
        station_id,
        date_id,
        COUNT(*)                             AS n_ops,
        SUM(standard_cycle_time_minutes)      AS sum_standard_minutes,
        SUM(actual_cycle_time_minutes)        AS sum_actual_minutes,
        SUM(downtime_minutes)                 AS sum_downtime_minutes
    FROM fact_station_operation
    GROUP BY station_id, date_id
),
defects AS (
    SELECT station_id, detected_date_id AS date_id, COUNT(*) AS n_defects
    FROM fact_defect
    GROUP BY station_id, detected_date_id
)
SELECT
    o.station_id,
    ws.station_name,
    ws.station_type,
    d.full_date,
    d.year,
    d.month,
    d.month_name,
    o.n_ops,
    COALESCE(def.n_defects, 0)                                                     AS n_defects,
    ROUND(o.sum_actual_minutes * 1.0 / (o.sum_actual_minutes + o.sum_downtime_minutes), 4) AS availability,
    ROUND(o.sum_standard_minutes * 1.0 / NULLIF(o.sum_actual_minutes, 0), 4)        AS performance,
    ROUND((o.n_ops - COALESCE(def.n_defects, 0)) * 1.0 / o.n_ops, 4)               AS quality,
    ROUND(
        (o.sum_actual_minutes * 1.0 / (o.sum_actual_minutes + o.sum_downtime_minutes)) *
        (o.sum_standard_minutes * 1.0 / NULLIF(o.sum_actual_minutes, 0)) *
        ((o.n_ops - COALESCE(def.n_defects, 0)) * 1.0 / o.n_ops)
    , 4) AS oee
FROM ops o
JOIN dim_workstation ws ON o.station_id = ws.station_id
JOIN dim_date d ON o.date_id = d.date_id
LEFT JOIN defects def ON o.station_id = def.station_id AND o.date_id = def.date_id;



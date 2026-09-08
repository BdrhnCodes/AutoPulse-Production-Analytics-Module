from db_utils import get_connection, query, save_analysis_output

def station_summary(conn):
    sql = """
        SELECT
            station_id, station_name, station_type, station_sequence_order,
            COUNT(*) AS n_days_observed,
            SUM(n_operations) AS total_operations,
            ROUND(SUM(avg_actual_cycle_time * n_operations) / SUM(n_operations), 2) AS avg_actual_cycle_time,
            ROUND(SUM(avg_standard_cycle_time * n_operations) / SUM(n_operations), 2) AS avg_standard_cycle_time,
            ROUND(SUM(total_downtime_minutes), 1) AS total_downtime_minutes,
            SUM(n_downtime_events) AS total_downtime_events
        FROM vw_station_performance
        GROUP BY station_id, station_name, station_type, station_sequence_order
        ORDER BY station_sequence_order;
    """
    df = query(sql, conn)
    df["variance_minutes"] = round(df["avg_actual_cycle_time"] - df["avg_standard_cycle_time"], 2)
    df["variance_pct"] = round(df["variance_minutes"] / df["avg_standard_cycle_time"] * 100, 1)
    df["is_bottleneck"] = df["variance_pct"] > df["variance_pct"].median() + df["variance_pct"].std()
    return df.sort_values("variance_pct", ascending=False)

def skill_summary(conn):
    sql = """
        SELECT
            w.skill_level,
            so.station_type,
            COUNT(*) AS n_operations,
            ROUND(AVG(so.actual_cycle_time_minutes), 2) AS avg_actual_cycle_time,
            ROUND(AVG(so.standard_cycle_time_minutes), 2) AS avg_standard_cycle_time,
            ROUND(AVG(so.actual_cycle_time_minutes - so.standard_cycle_time_minutes), 2) AS avg_variance_minutes
        FROM (
            SELECT fso.*, ws.station_type
            FROM fact_station_operation fso
            JOIN dim_workstation ws ON fso.station_id = ws.station_id
        ) so
        JOIN dim_worker w ON so.worker_id = w.worker_id
        GROUP BY w.skill_level, so.station_type
        ORDER BY so.station_type, w.skill_level;
    """
    return query(sql, conn)

def main():
    conn = get_connection()

    print("Computing per-station labor time summary ...")
    station_df = station_summary(conn)
    path1 = save_analysis_output(station_df, "labor_time_station_summary")
    print(f"  -> {path1}")

    print("\nTop 5 bottleneck stations (highest positive variance %):")
    print(station_df.head(5)[["station_name", "avg_actual_cycle_time", "avg_standard_cycle_time",
                               "variance_pct", "total_downtime_events"]].to_string(index=False))

    print("\nComputing cycle-time variance by worker skill level ...")
    skill_df = skill_summary(conn)
    path2 = save_analysis_output(skill_df, "labor_time_skill_summary")
    print(f"  -> {path2}")

    conn.close()
    return station_df, skill_df


if __name__ == "__main__":
    main()
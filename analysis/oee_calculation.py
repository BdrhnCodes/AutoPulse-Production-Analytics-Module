from db_utils import get_connection, query, save_analysis_output

def station_monthly(conn):
    sql = """
        SELECT
            station_id, station_name, station_type, year, month, month_name,
            SUM(n_ops) AS n_ops,
            SUM(n_defects) AS n_defects,
            ROUND(AVG(availability), 4) AS avg_availability,
            ROUND(AVG(performance), 4) AS avg_performance,
            ROUND(AVG(quality), 4) AS avg_quality,
            ROUND(AVG(oee), 4) AS avg_oee
        FROM vw_oee_daily
        GROUP BY station_id, station_name, station_type, year, month, month_name
        ORDER BY station_id, year, month;
    """
    return query(sql, conn)

def line_monthly(conn):
    sql = """
        SELECT
            year, month, month_name,
            ROUND(AVG(availability), 4) AS avg_availability,
            ROUND(AVG(performance), 4) AS avg_performance,
            ROUND(AVG(quality), 4) AS avg_quality,
            ROUND(AVG(oee), 4) AS avg_oee
        FROM vw_oee_daily
        GROUP BY year, month, month_name
        ORDER BY year, month;
    """
    return query(sql, conn)

def worst_stations(conn):
    sql = """
        SELECT station_name, station_type,
               ROUND(AVG(oee), 4) AS avg_oee,
               ROUND(AVG(availability), 4) AS avg_availability,
               ROUND(AVG(performance), 4) AS avg_performance,
               ROUND(AVG(quality), 4) AS avg_quality
        FROM vw_oee_daily
        GROUP BY station_name, station_type
        ORDER BY avg_oee ASC
        LIMIT 5;
    """
    return query(sql, conn)

def main():
    conn = get_connection()

    print("Station x month OEE ...")
    df1 = station_monthly(conn)
    path1 = save_analysis_output(df1, "oee_station_monthly")
    print(f"  -> {path1}  ({len(df1)} rows)")

    print("\nOverall line OEE trend (first + last 3 months) ...")
    df2 = line_monthly(conn)
    path2 = save_analysis_output(df2, "oee_line_monthly")
    print(df2.head(3).to_string(index=False))
    print("...")
    print(df2.tail(3).to_string(index=False))
    print(f"  -> {path2}")

    print("\nWorst 5 stations by average OEE (World Class benchmark = 0.85):")
    df3 = worst_stations(conn)
    print(df3.to_string(index=False))

    conn.close()
    return df1, df2, df3


if __name__ == "__main__":
    main()
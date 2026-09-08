from db_utils import get_connection, query, save_analysis_output


def pareto_by_part(conn):
    sql = """
        SELECT part_name, part_category, COUNT(*) AS n_defects,
               ROUND(SUM(rework_cost), 2) AS total_rework_cost
        FROM vw_defect_pareto
        WHERE part_name IS NOT NULL
        GROUP BY part_name, part_category
        ORDER BY n_defects DESC;
    """
    df = query(sql, conn)
    df["cum_defects"] = df["n_defects"].cumsum()
    df["cum_pct"] = round(df["cum_defects"] / df["n_defects"].sum() * 100, 1)
    df["is_top_80pct_contributor"] = df["cum_pct"] <= 80
    return df

def trend_monthly(conn):
    sql = """
        SELECT year, month, month_name, COUNT(*) AS n_defects,
               ROUND(SUM(rework_cost), 2) AS total_rework_cost
        FROM vw_defect_pareto
        GROUP BY year, month, month_name
        ORDER BY year, month;
    """
    defects_df = query(sql, conn)

    units_sql = """
        SELECT d.year, d.month, COUNT(*) AS n_operations
        FROM fact_station_operation so
        JOIN dim_date d ON so.date_id = d.date_id
        GROUP BY d.year, d.month;
    """
    ops_by_month = query(units_sql, conn)

    merged = defects_df.merge(ops_by_month, on=["year", "month"], how="left")
    merged["defect_rate_pct"] = round(merged["n_defects"] / merged["n_operations"] * 100, 3)
    return merged

def rate_by_supplier(conn):
    part_installs_sql = """
        SELECT part_id, COUNT(*) AS n_installations
        FROM fact_material_usage
        GROUP BY part_id;
    """
    installs = query(part_installs_sql, conn)

    part_defects_sql = """
        SELECT part_id, COUNT(*) AS n_defects
        FROM fact_defect
        WHERE part_id IS NOT NULL
        GROUP BY part_id;
    """
    part_defects = query(part_defects_sql, conn)

    eligible = part_defects.merge(installs, on="part_id", how="left")
    eligible["defect_rate_per_1000_installs"] = round(
        eligible["n_defects"] / eligible["n_installations"] * 1000, 2
    )

    part_info_sql = """
        SELECT p.part_id, p.part_name, p.part_category, p.complexity_score,
               s.supplier_name, s.reliability_score
        FROM dim_part p
        JOIN dim_supplier s ON p.primary_supplier_id = s.supplier_id;
    """
    part_info = query(part_info_sql, conn)

    result = eligible.merge(part_info, on="part_id", how="left")
    result = result[["part_name", "part_category", "supplier_name", "reliability_score",
                      "complexity_score", "n_installations", "n_defects", "defect_rate_per_1000_installs"]]
    result = result.sort_values("reliability_score")

    corr_reliability = result["reliability_score"].corr(result["defect_rate_per_1000_installs"])
    corr_complexity = result["complexity_score"].corr(result["defect_rate_per_1000_installs"])
    print(f"  Correlation (defect rate vs supplier reliability): {corr_reliability:.3f}  (expected: negative)")
    print(f"  Correlation (defect rate vs part complexity):      {corr_complexity:.3f}  (expected: positive)")

    return result

def main():
    conn = get_connection()

    print("Pareto analysis by part ...")
    df1 = pareto_by_part(conn)
    path1 = save_analysis_output(df1, "defect_pareto_by_part")
    n_top = df1["is_top_80pct_contributor"].sum()
    print(f"  {n_top} of {len(df1)} distinct parts account for ~80% of all part-tied defects")
    print(df1.head(8)[["part_name", "part_category", "n_defects", "cum_pct"]].to_string(index=False))
    print(f"  -> {path1}")

    print("\nMonthly defect rate trend (first + last 3 months) ...")
    df2 = trend_monthly(conn)
    path2 = save_analysis_output(df2, "defect_trend_monthly")
    print(df2[["year", "month_name", "n_defects", "defect_rate_pct"]].head(3).to_string(index=False))
    print("...")
    print(df2[["year", "month_name", "n_defects", "defect_rate_pct"]].tail(3).to_string(index=False))
    print(f"  -> {path2}")

    print("\nDefect rate by supplier reliability ...")
    df3 = rate_by_supplier(conn)
    path3 = save_analysis_output(df3, "defect_rate_by_supplier")
    print(df3.to_string(index=False))
    print(f"  -> {path3}")

    conn.close()
    return df1, df2, df3


if __name__ == "__main__":
    main()
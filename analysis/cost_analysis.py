from db_utils import get_connection, query, save_analysis_output

def cost_by_model_trim(conn):
    sql = """
        SELECT
            model_name, segment, trim_name,
            COUNT(*) AS n_units,
            ROUND(AVG(avg_material_cost), 2) AS avg_material_cost,
            ROUND(AVG(avg_labor_cost), 2)    AS avg_labor_cost,
            ROUND(AVG(avg_rework_cost), 2)   AS avg_rework_cost,
            ROUND(AVG(avg_total_cost), 2)    AS avg_total_cost
        FROM vw_cost_breakdown
        GROUP BY model_name, segment, trim_name
        ORDER BY model_name, avg_total_cost;
    """
    return query(sql, conn)

def monthly_trend(conn):
    sql = """
        SELECT
            year, month, month_name,
            SUM(n_units) AS n_units,
            ROUND(SUM(avg_material_cost * n_units) / SUM(n_units), 2) AS avg_material_cost,
            ROUND(SUM(avg_labor_cost * n_units) / SUM(n_units), 2)    AS avg_labor_cost,
            ROUND(SUM(avg_total_cost * n_units) / SUM(n_units), 2)    AS avg_total_cost,
            ROUND(SUM(sum_total_cost), 2) AS total_spend
        FROM vw_cost_breakdown
        GROUP BY year, month, month_name
        ORDER BY year, month;
    """
    return query(sql, conn)

def component_split(conn):
    sql = """
        SELECT
            ROUND(SUM(total_material_cost), 2) AS total_material_cost,
            ROUND(SUM(total_labor_cost), 2)    AS total_labor_cost,
            ROUND(SUM(total_rework_cost), 2)   AS total_rework_cost,
            ROUND(SUM(total_cost), 2)          AS total_cost
        FROM fact_production_unit;
    """
    df = query(sql, conn)
    for col in ["total_material_cost", "total_labor_cost", "total_rework_cost"]:
        df[col.replace("total_", "pct_")] = round(df[col] / df["total_cost"] * 100, 2)
    return df

def main():
    conn = get_connection()

    print("Cost by model x trim ...")
    df1 = cost_by_model_trim(conn)
    path1 = save_analysis_output(df1, "cost_by_model_trim")
    print(df1.to_string(index=False))
    print(f"  -> {path1}")

    print("\nMonthly cost trend (first + last 3 months) ...")
    df2 = monthly_trend(conn)
    path2 = save_analysis_output(df2, "cost_monthly_trend")
    print(df2.head(3).to_string(index=False))
    print("...")
    print(df2.tail(3).to_string(index=False))
    print(f"  -> {path2}")

    print("\nOverall cost component split ...")
    df3 = component_split(conn)
    path3 = save_analysis_output(df3, "cost_component_split")
    print(df3.to_string(index=False))
    print(f"  -> {path3}")

    conn.close()
    return df1, df2, df3


if __name__ == "__main__":
    main()
from tools.databricks_api import run_query

sql_o = """
select * from gold.gold
where kpi_name = 'Production'
and granularity = 'DAY'
and date = Date '2026-08-02'
and product_type = 'Inner Liner'
"""

sql = """
SELECT date, unit_of_measurement, actual_value
FROM gold.gold
WHERE lower(kpi_name) = 'production'
AND lower(product_type) = 'inner liner'
AND lower(granularity) = 'day'
AND date = Date '2026-04-13'
"""

print(run_query(sql))
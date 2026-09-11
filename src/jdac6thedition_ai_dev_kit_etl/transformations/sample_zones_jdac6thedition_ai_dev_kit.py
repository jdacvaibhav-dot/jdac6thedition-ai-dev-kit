from pyspark import pipelines as dp
from pyspark.sql.functions import col, sum


@dp.table
def sample_zones_jdac6thedition_ai_dev_kit():
    return (
        spark.read.table(f"sample_trips_jdac6thedition_ai_dev_kit")
        .groupBy(col("pickup_zip"))
        .agg(sum("fare_amount").alias("total_fare"))
    )

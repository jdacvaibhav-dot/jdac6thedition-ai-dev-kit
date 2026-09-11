from pyspark import pipelines as dp
from pyspark.sql.functions import col


@dp.table
def sample_trips_jdac6thedition_ai_dev_kit():
    return spark.read.table("samples.nyctaxi.trips")

from pyspark import pipelines as dp


@dp.table(name="booking_updates_bronze", private=True)
def booking_updates_bronze():
    return spark.readStream.table("samples.wanderbricks.booking_updates")

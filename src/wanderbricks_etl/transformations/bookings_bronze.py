from pyspark import pipelines as dp


@dp.table(name="bookings_bronze", private=True)
def bookings_bronze():
    return spark.readStream.table("samples.wanderbricks.bookings")

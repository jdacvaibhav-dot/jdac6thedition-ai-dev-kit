from pyspark import pipelines as dp


@dp.table(
    name="bookings_bronze",
    comment=(
        "Raw ingest of samples.wanderbricks.bookings. One row per booking holding only its "
        "CURRENT status; the opening state of each booking's status history."
    ),
)
def bookings_bronze():
    return spark.readStream.table("samples.wanderbricks.bookings")

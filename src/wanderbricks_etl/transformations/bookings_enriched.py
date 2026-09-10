from pyspark import pipelines as dp


@dp.temporary_view(name="bookings_enriched")
def bookings_enriched():
    bookings = spark.readStream.table("bookings_bronze")
    properties = spark.read.table("samples.wanderbricks.properties").select(
        "property_id", "destination_id"
    )
    destinations = spark.read.table("samples.wanderbricks.destinations").select(
        "destination_id", "destination"
    )

    return (
        bookings.join(properties, on="property_id", how="left")
        .join(destinations, on="destination_id", how="left")
        .drop("destination_id")
    )

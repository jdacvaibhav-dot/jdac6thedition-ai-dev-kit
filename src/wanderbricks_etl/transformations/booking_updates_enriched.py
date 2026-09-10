from pyspark import pipelines as dp


@dp.temporary_view(name="booking_updates_enriched")
def booking_updates_enriched():
    booking_updates = spark.readStream.table("booking_updates_bronze")
    properties = spark.read.table("samples.wanderbricks.properties").select(
        "property_id", "destination_id"
    )
    destinations = spark.read.table("samples.wanderbricks.destinations").select(
        "destination_id", "destination"
    )

    return (
        booking_updates.join(properties, on="property_id", how="left")
        .join(destinations, on="destination_id", how="left")
        .drop("destination_id")
    )

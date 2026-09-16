from pyspark import pipelines as dp


@dp.table(
    name="booking_updates_bronze",
    comment=(
        "Raw ingest of samples.wanderbricks.booking_updates, an append stream of booking "
        "change events. ~47 rows are known orphans whose booking_id is absent from "
        "bookings; they are deliberately retained. The cross-table orphan check cannot be "
        "expressed in a streaming read, so it is surfaced downstream in booking_status_gold."
    ),
)
@dp.expect("booking_id_present", "booking_id IS NOT NULL")
def booking_updates_bronze():
    return spark.readStream.table("samples.wanderbricks.booking_updates")

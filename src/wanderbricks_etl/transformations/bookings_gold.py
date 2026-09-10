from pyspark import pipelines as dp

dp.create_streaming_table(name="bookings_gold")

dp.create_auto_cdc_flow(
    target="bookings_gold",
    source="bookings_enriched",
    keys=["booking_id"],
    sequence_by="updated_at",
    stored_as_scd_type=2,
    name="bookings_initial_cdc",
)

dp.create_auto_cdc_flow(
    target="bookings_gold",
    source="booking_updates_enriched",
    keys=["booking_id"],
    sequence_by="updated_at",
    stored_as_scd_type=2,
    name="booking_updates_cdc",
)

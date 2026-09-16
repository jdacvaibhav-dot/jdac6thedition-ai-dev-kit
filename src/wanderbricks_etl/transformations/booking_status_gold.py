from pyspark import pipelines as dp
from pyspark.sql.functions import col, lag, row_number
from pyspark.sql.window import Window


@dp.materialized_view(
    name="booking_status_gold",
    comment=(
        "Wide, analyst-facing view of every booking status interval, enriched with "
        "property, destination and country attributes. One row per (booking_id, status "
        "interval); is_current_status marks the live row. Orphan bookings whose "
        "property_id does not resolve are retained via LEFT JOINs and flagged by the "
        "warn-only property_resolved expectation."
    ),
    cluster_by=["destination", "status"],
)
@dp.expect("property_resolved", "property_id IS NULL OR property_type IS NOT NULL")
def booking_status_gold():
    # __START_AT / __END_AT are structs of (event_ts, event_seq) because the SCD2 flow
    # sequences by a struct -- unpack them rather than treating them as timestamps.
    history = spark.read.table("booking_status_history").select(
        col("booking_id"),
        col("user_id"),
        col("property_id"),
        col("status"),
        col("__START_AT.event_ts").alias("status_start_ts"),
        col("__START_AT.event_seq").alias("status_start_seq"),
        col("__END_AT.event_ts").alias("status_end_ts"),
        col("__END_AT").isNull().alias("is_current_status"),
        col("check_in"),
        col("check_out"),
        col("guests_count"),
        col("total_amount"),
        col("booking_created_at"),
    )

    status_window = Window.partitionBy("booking_id").orderBy(
        col("status_start_ts"), col("status_start_seq")
    )

    history = history.select(
        "*",
        row_number().over(status_window).alias("status_sequence"),
        lag(col("status")).over(status_window).alias("previous_status"),
    )

    properties = spark.read.table("samples.wanderbricks.properties").select(
        col("property_id").alias("prop_property_id"),
        col("host_id"),
        col("destination_id"),
        col("title").alias("property_title"),
        col("property_type"),
    )

    destinations = spark.read.table("samples.wanderbricks.destinations").select(
        col("destination_id").alias("dest_destination_id"),
        col("destination"),
        col("country"),
        col("state_or_province"),
    )

    countries = spark.read.table("samples.wanderbricks.countries").select(
        col("country").alias("countries_country"),
        col("continent"),
    )

    enriched = (
        history.join(
            properties,
            history["property_id"] == properties["prop_property_id"],
            "left",
        )
        .join(
            destinations,
            col("destination_id") == col("dest_destination_id"),
            "left",
        )
        .join(
            countries,
            col("country") == col("countries_country"),
            "left",
        )
    )

    return enriched.select(
        col("booking_id"),
        col("user_id"),
        col("property_id"),
        col("status"),
        col("status_start_ts"),
        col("status_end_ts"),
        col("is_current_status"),
        col("status_sequence"),
        col("previous_status"),
        col("destination"),
        col("country"),
        col("continent"),
        col("state_or_province"),
        col("property_type"),
        col("property_title"),
        col("host_id"),
        col("check_in"),
        col("check_out"),
        col("guests_count"),
        col("total_amount"),
        col("booking_created_at"),
    )

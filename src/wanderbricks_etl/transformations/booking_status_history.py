from pyspark import pipelines as dp
from pyspark.sql.functions import col, lit, struct

# Common change-event shape shared by both sources. Column order and types must match
# exactly so the two append flows can fan into a single streaming table.


@dp.temporary_view(name="booking_change_events_from_bookings")
def booking_change_events_from_bookings():
    return spark.readStream.table("bookings_bronze").select(
        col("booking_id"),
        col("user_id"),
        col("property_id"),
        col("status"),
        col("check_in"),
        col("check_out"),
        col("guests_count"),
        col("total_amount"),
        col("created_at").alias("booking_created_at"),
        # status reflects the row as of bookings.updated_at, not created_at: 69,632/72,247
        # bookings have been mutated since creation, unmutated rows skew 93% terminal
        # (cancelled/completed), and mutated rows are only ever pending/confirmed -- so
        # stamping status at created_at would put terminal states earliest in history.
        col("updated_at").alias("event_ts"),
        lit(0).cast("bigint").alias("event_seq"),
        lit("booking").alias("event_source"),
    )


@dp.temporary_view(name="booking_change_events_from_updates")
def booking_change_events_from_updates():
    return spark.readStream.table("booking_updates_bronze").select(
        col("booking_id"),
        col("user_id"),
        col("property_id"),
        col("status"),
        col("check_in"),
        col("check_out"),
        col("guests_count"),
        col("total_amount"),
        col("created_at").alias("booking_created_at"),
        col("updated_at").alias("event_ts"),
        col("booking_update_id").cast("bigint").alias("event_seq"),
        lit("update").alias("event_source"),
    )


# Fan-in via append flows rather than a UNION: unioning streaming sources is the
# documented anti-pattern here.
dp.create_streaming_table(
    name="booking_change_feed",
    comment=(
        "Unified append-only feed of booking change events: each booking's opening state "
        "from bookings_bronze plus every subsequent change from booking_updates_bronze."
    ),
)


@dp.append_flow(target="booking_change_feed", name="change_feed_from_bookings")
def change_feed_from_bookings():
    return spark.readStream.table("booking_change_events_from_bookings")


@dp.append_flow(target="booking_change_feed", name="change_feed_from_updates")
def change_feed_from_updates():
    return spark.readStream.table("booking_change_events_from_updates")


dp.create_streaming_table(
    name="booking_status_history",
    comment=(
        "SCD Type 2 status history: one row per contiguous status interval per booking. "
        "Because sequence_by is a struct, the Lakeflow-managed __START_AT and __END_AT "
        "columns are STRUCTs of (event_ts, event_seq), not timestamps -- read them as "
        "__START_AT.event_ts / __END_AT.event_ts."
    ),
)

# The struct sequence makes the 486 known (booking_id, updated_at) collisions
# deterministic; track_history_column_list=["status"] means an update that changes only
# price or guest count overwrites in place instead of minting a spurious status row.
dp.create_auto_cdc_flow(
    target="booking_status_history",
    source="booking_change_feed",
    keys=["booking_id"],
    sequence_by=struct("event_ts", "event_seq"),
    stored_as_scd_type=2,
    track_history_column_list=["status"],
)

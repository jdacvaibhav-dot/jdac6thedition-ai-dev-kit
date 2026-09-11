from pyspark import pipelines as dp

BOOKINGS_GOLD_SCHEMA = """
    property_id BIGINT COMMENT 'Unique identifier of the booked property.',
    booking_id BIGINT COMMENT 'Unique identifier of the booking. SCD2 key: one or more rows per booking_id, one row per status period.',
    booking_update_id BIGINT COMMENT 'Unique identifier of the booking_updates_bronze row that produced this status period, if the row originated from a status update rather than the original booking.',
    check_in DATE COMMENT 'Guest check-in date for the stay.',
    check_out DATE COMMENT 'Guest check-out date for the stay.',
    created_at TIMESTAMP COMMENT 'Timestamp the booking was originally created.',
    guests_count INT COMMENT 'Number of guests on the booking.',
    status STRING COMMENT 'Booking status for this SCD2 period, e.g. pending, confirmed, completed, cancelled.',
    total_amount FLOAT COMMENT 'Total booking amount, in local currency, charged for the stay.',
    updated_at TIMESTAMP COMMENT 'Timestamp this status period was recorded (source of the CDC sequence_by ordering).',
    user_id BIGINT COMMENT 'Unique identifier of the guest who made the booking.',
    destination STRING COMMENT 'Travel destination of the booked property.',
    __START_AT TIMESTAMP COMMENT 'SCD Type 2: timestamp this row''s status became effective.',
    __END_AT TIMESTAMP COMMENT 'SCD Type 2: timestamp this row''s status stopped being current. NULL means this is the current row for the booking.'
"""

dp.create_streaming_table(
    name="bookings_gold",
    comment=(
        "SCD Type 2 gold table of Wanderbricks bookings. Each row is a status "
        "period for a booking, built by merging the baseline bookings snapshot "
        "with booking_updates status-change events via two Auto CDC flows. "
        "Filter WHERE __END_AT IS NULL for the current status of each booking; "
        "omit that filter to analyze status history over time."
    ),
    schema=BOOKINGS_GOLD_SCHEMA,
)

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

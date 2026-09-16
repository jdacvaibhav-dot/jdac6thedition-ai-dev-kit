# wanderbricks_etl

This folder defines all source code for the `wanderbricks_etl` pipeline, which rebuilds
every Wanderbricks booking's full status history as an SCD Type 2 table.

- `transformations/`: All dataset definitions and transformations (one dataset per file).

## Flow

**Bronze** — streaming ingest of the source tables, untouched:

- `bookings_bronze` — `samples.wanderbricks.bookings`. One row per booking, current status only.
- `booking_updates_bronze` — `samples.wanderbricks.booking_updates`, the append stream of
  changes. A warn-only `booking_id_present` expectation keeps every row, including the ~47
  known orphans whose `booking_id` is absent from `bookings`.

**Silver** — `booking_status_history.py`:

1. Two temporary views normalize each bronze table into one common change-event shape.
   The bookings row becomes the booking's opening event (`event_seq = 0`,
   `event_source = 'booking'`), stamped at `bookings.updated_at`; each update becomes a
   later event keyed by `booking_update_id`. For bookings with no updates, that
   opening-event timestamp is the source snapshot time, not necessarily when the
   booking actually entered that status.
2. `booking_change_feed` fans both views in via `@dp.append_flow` (append flows, not a
   `UNION` across streaming sources).
3. `booking_status_history` is the SCD Type 2 target, built by `dp.create_auto_cdc_flow`
   with `keys=["booking_id"]` and `track_history_column_list=["status"]` — so only a
   status change mints a new history row; a price or guest-count change overwrites in
   place.

**Gold** — `booking_status_gold`: a wide materialized view joining the history to
properties, destinations and countries (LEFT JOINs, so orphans survive), with
`status_sequence` and `previous_status` window columns. Its column list is a contract
consumed by the dashboard and Genie agent — do not rename, drop or add columns.

## The struct-sequence consequence

`sequence_by` is `struct("event_ts", "event_seq")`, not a bare timestamp, because 486
`(booking_id, updated_at)` collisions exist in the source and ordering by timestamp alone
is nondeterministic. Lakeflow types the managed `__START_AT` / `__END_AT` columns to match
`sequence_by`, so on `booking_status_history` they are **structs**, not timestamps. Read
them as `__START_AT.event_ts` and `__END_AT.event_ts` (as the gold layer does).

For syntax reference see https://docs.databricks.com/aws/en/dlt/dlt-python-ref.

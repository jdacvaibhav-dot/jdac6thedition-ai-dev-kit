# wanderbricks_etl

Lakeflow Declarative Pipeline producing `bookings_gold`: a CDC/SCD Type 2 booking
history table built from `samples.wanderbricks.bookings` and
`samples.wanderbricks.booking_updates`.

- `transformations/`: dataset definitions — one file per dataset.
  - `bookings_bronze.py` / `booking_updates_bronze.py`: raw streaming reads (Bronze),
    marked `private=True` — not published to Unity Catalog. `bookings_gold` is the
    only table this pipeline publishes.
  - `bookings_enriched.py` / `booking_updates_enriched.py`: stream-static joins adding
    `destination` (temporary views feeding Auto CDC).
  - `bookings_gold.py`: empty streaming table populated by two Auto CDC flows
    (SCD Type 2), one per source.

Run a single transformation from the CLI:
`databricks bundle run wanderbricks_gold_pipeline --refresh bookings_bronze -t dev`

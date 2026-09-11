import argparse
from databricks.sdk.runtime import spark
from jdac6thedition_ai_dev_kit import taxis


def main():
    parser = argparse.ArgumentParser(
        description="Databricks job with catalog and schema parameters",
    )
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()

    spark.sql(f"USE CATALOG `{args.catalog}`")
    spark.sql(f"USE SCHEMA `{args.schema}`")

    taxis.find_all_taxis().show(5)


if __name__ == "__main__":
    main()

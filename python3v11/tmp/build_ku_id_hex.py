#!/usr/bin/env python3

from influxdb import InfluxDBClient
import time
import argparse
import sys

# ============================================================
# ARGPARSE
# ============================================================

parser = argparse.ArgumentParser(
    description="KU DNA HEX verifier/builder"
)

parser.add_argument(
    "--verify",
    action="store_true",
    help="Verify existing ku_dna_hex values"
)

parser.add_argument(
    "--build",
    action="store_true",
    help="Build ku_dna_hex when missing"
)

parser.add_argument(
    "--from-time",
    default="10d",
    help="FROM time window (example: 30d)"
)

parser.add_argument(
    "--to-time",
    default="0d",
    help="TO time window (example: 2d)"
)

parser.add_argument(
    "--batch-size",
    type=int,
    default=1000,
    help="InfluxDB write batch size"
)

parser.add_argument(
    "--batch-delay",
    type=float,
    default=0.2,
    help="Delay between write batches"
)

args = parser.parse_args()

if not args.verify and not args.build:

    print(
        "ERROR: Must specify at least one mode:\n"
        "  --verify\n"
        "  --build"
    )

    sys.exit(1)

# ============================================================
# INFLUXDB SETUP
# ============================================================

host = "192.168.0.200"
port = 8086
username = "tiledb"
password = "T1le-db-word!"
database = "tiledb"

influxdb = InfluxDBClient(
    host=host,
    port=port,
    username=username,
    password=password,
    database=database,
    timeout=60
)

# ============================================================
# CONFIG
# ============================================================

measurement_name = "DB Status"

from_time = args.from_time
to_time = args.to_time

batch_size = args.batch_size
batch_delay = args.batch_delay

# ============================================================
# FIND TAG KEYS
# ============================================================

print("Fetching tag keys...")

tag_query = f'SHOW TAG KEYS FROM "{measurement_name}"'

tag_result = influxdb.query(tag_query)

tag_keys = []

for table in tag_result.raw.get("series", []):

    for row in table.get("values", []):

        tag_keys.append(row[0])

print(f"Found tag keys: {tag_keys}")

# ============================================================
# BUILD SELECT LIST
# ============================================================

select_fields = [
    "ku_dna_0",
    "ku_dna_1",
    "ku_dna_2",
    "ku_dna_hex"
]

select_fields.extend([f'"{x}"' for x in tag_keys])

select_string = ",\n    ".join(select_fields)

# ============================================================
# QUERY EXISTING DATA
# ============================================================

print("Querying DB Status entries...")

query = f"""
SELECT
    {select_string}
FROM "{measurement_name}"
WHERE time > now() - {from_time}
AND time < now() - {to_time}
"""

print(query)

result = influxdb.query(query)

points = list(result.get_points())

print(f"Found {len(points)} points")

# ============================================================
# PROCESS POINTS
# ============================================================

new_points = []

verify_ok = 0
verify_failed = 0
verify_missing = 0

build_count = 0

for idx, p in enumerate(points):

    try:

        # ----------------------------------------------------
        # VERIFY REQUIRED FIELDS
        # ----------------------------------------------------

        if (
            "ku_dna_0" not in p
            or "ku_dna_1" not in p
            or "ku_dna_2" not in p
        ):

            print(
                f"Point {idx} missing "
                f"ku_dna_0/1/2 fields"
            )

            continue

        if (
            p["ku_dna_0"] is None
            or p["ku_dna_1"] is None
            or p["ku_dna_2"] is None
        ):

            print(
                f"Point {idx} has NULL "
                f"ku_dna_0/1/2"
            )

            continue

        # ----------------------------------------------------
        # REBUILD KU DNA HEX
        # ----------------------------------------------------

        ku_dna_0 = int(p["ku_dna_0"])
        ku_dna_1 = int(p["ku_dna_1"])
        ku_dna_2 = int(p["ku_dna_2"])

        ku_dna = (
            (ku_dna_0 << 64)
            | (ku_dna_1 << 32)
            | ku_dna_2
        )

        ku_dna_hex_rebuilt = f"{ku_dna:024X}"

        existing_hex = p.get("ku_dna_hex", None)

        # ----------------------------------------------------
        # VERIFY MODE
        # ----------------------------------------------------

        if args.verify:

            if existing_hex in [None, ""]:

                print(
                    f"[MISSING] Point {idx}: "
                    f"ku_dna_hex missing "
                    f"(expected={ku_dna_hex_rebuilt})"
                )

                verify_missing += 1

            else:

                existing_hex = str(existing_hex).upper()

                if existing_hex == ku_dna_hex_rebuilt:

                    print(
                        f"[OK] Point {idx}: "
                        f"{existing_hex}"
                    )

                    verify_ok += 1

                else:

                    print(
                        f"[FAILED] Point {idx}: "
                        f"stored={existing_hex} "
                        f"rebuilt={ku_dna_hex_rebuilt}"
                    )

                    verify_failed += 1

        # ----------------------------------------------------
        # BUILD MODE
        # ----------------------------------------------------

        if args.build:

            if existing_hex not in [None, ""]:

                continue

            # --------------------------------------------
            # REBUILD TAGS
            # --------------------------------------------

            tags = {}

            for key, value in p.items():

                if key in tag_keys:

                    tags[key] = value

            # --------------------------------------------
            # CREATE PATCH POINT
            # --------------------------------------------

            new_points.append({

                "measurement": measurement_name,

                "time": p["time"],

                "tags": tags,

                "fields": {

                    "ku_dna_hex":
                        ku_dna_hex_rebuilt
                }
            })

            build_count += 1

    except Exception as e:

        print(
            f"Error processing point "
            f"{idx}: {e}"
        )

# ============================================================
# VERIFY SUMMARY
# ============================================================

if args.verify:

    print("\n================ VERIFY SUMMARY ================")

    print(f"OK       : {verify_ok}")
    print(f"FAILED   : {verify_failed}")
    print(f"MISSING  : {verify_missing}")

# ============================================================
# BUILD SUMMARY
# ============================================================

if args.build:

    print("\n================ BUILD SUMMARY =================")

    print(
        f"Prepared {len(new_points)} "
        f"points to update"
    )

# ============================================================
# WRITE PATCHES
# ============================================================

if args.build and len(new_points) > 0:

    for i in range(0, len(new_points), batch_size):

        batch = new_points[i:i + batch_size]

        success = False

        while not success:

            try:

                influxdb.write_points(batch)

                print(
                    f"Wrote batch "
                    f"{i} -> "
                    f"{i + len(batch)} "
                    f"of {len(new_points)}"
                )

                success = True

                time.sleep(batch_delay)

            except Exception as e:

                print(
                    f"Batch write failed: {e}"
                )

                print(
                    "Retrying in 5 seconds..."
                )

                time.sleep(5)

# ============================================================
# DONE
# ============================================================

print("\nDone.")
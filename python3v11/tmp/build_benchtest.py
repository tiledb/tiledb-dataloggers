#!/usr/bin/env python3

import argparse
import sys
import time
from datetime import timezone

import pymysql
from influxdb import InfluxDBClient

# ============================================================
# ARGPARSE
# ============================================================

parser = argparse.ArgumentParser(
    description="Build/verify Bench Test measurement in InfluxDB"
)

parser.add_argument(
    "--build",
    action="store_true",
    help="Build Bench Test entries in InfluxDB"
)

parser.add_argument(
    "--verify",
    action="store_true",
    help="Verify Bench Test entries in InfluxDB"
)

parser.add_argument(
    "--batch-size",
    type=int,
    default=1000,
    help="InfluxDB batch size"
)

parser.add_argument(
    "--batch-delay",
    type=float,
    default=0.2,
    help="Delay between batch writes"
)

args = parser.parse_args()

if not args.build and not args.verify:

    print(
        "ERROR: Must specify at least one mode:\n"
        "  --build\n"
        "  --verify"
    )

    sys.exit(1)

# ============================================================
# MARIADB CONFIG
# ============================================================

mariadb_host = "192.168.0.200"
mariadb_port = 3306
mariadb_user = "tiledb"
mariadb_password = "T1le-db-word!"
mariadb_database = "tiledb"
mariadb_table = "benchtest"

# ============================================================
# INFLUXDB CONFIG
# ============================================================

influx_host = "192.168.0.200"
influx_port = 8086
influx_username = "tiledb"
influx_password = "T1le-db-word!"
influx_database = "tiledb"

measurement_name = "Bench Test"
reference_measurement = "Link Status"

# ============================================================
# GLOBAL CONNECTIONS
# ============================================================

mariadb = None
influxdb = None

# ============================================================
# CONNECT TO MARIADB
# ============================================================

def connect_mariadb():

    global mariadb

    while True:

        try:

            print("Connecting to MariaDB...")

            mariadb = pymysql.connect(
                host=mariadb_host,
                port=mariadb_port,
                user=mariadb_user,
                password=mariadb_password,
                database=mariadb_database,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30
            )

            print("Connected to MariaDB")

            return

        except Exception as e:

            print(
                f"MariaDB connection failed: {e}"
            )

            print("Retrying in 5 seconds...")

            time.sleep(5)

# ============================================================
# CONNECT TO INFLUXDB
# ============================================================

def connect_influxdb():

    global influxdb

    while True:

        try:

            print("Connecting to InfluxDB...")

            influxdb = InfluxDBClient(
                host=influx_host,
                port=influx_port,
                username=influx_username,
                password=influx_password,
                database=influx_database,
                timeout=60
            )

            influxdb.ping()

            print("Connected to InfluxDB")

            return

        except Exception as e:

            print(
                f"InfluxDB connection failed: {e}"
            )

            print("Retrying in 5 seconds...")

            time.sleep(5)

# ============================================================
# SAFE MARIA QUERY
# ============================================================

def maria_query(query):

    global mariadb

    while True:

        try:

            mariadb.ping(reconnect=True)

            with mariadb.cursor() as cursor:

                cursor.execute(query)

                return cursor.fetchall()

        except Exception as e:

            print(
                f"MariaDB query failed: {e}"
            )

            print("Reconnecting MariaDB...")

            connect_mariadb()

            time.sleep(2)

# ============================================================
# SAFE INFLUX QUERY
# ============================================================

def influx_query(query):

    global influxdb

    while True:

        try:

            return influxdb.query(query)

        except Exception as e:

            print(
                f"InfluxDB query failed: {e}"
            )

            print("Reconnecting InfluxDB...")

            connect_influxdb()

            time.sleep(2)

# ============================================================
# SAFE INFLUX WRITE
# ============================================================

def influx_write(points):

    global influxdb

    while True:

        try:

            influxdb.write_points(points)

            return

        except Exception as e:

            print(
                f"InfluxDB write failed: {e}"
            )

            print("Reconnecting InfluxDB...")

            connect_influxdb()

            time.sleep(2)

# ============================================================
# CONNECT
# ============================================================

connect_mariadb()
connect_influxdb()

# ============================================================
# READ MARIA DB TABLE
# ============================================================

print("Reading MariaDB benchtest table...")

rows = maria_query(
    f"""
    SELECT
        id,
        test_start,
        test_stop,
        test_op,
        test_pass,
        db_slot1,
        db_slot2,
        db_slot3,
        db_slot4
    FROM {mariadb_table}
    """
)

print(f"Found {len(rows)} rows")

# ============================================================
# VERIFY MODE
# ============================================================

if args.verify:

    print("\n================ VERIFY MODE ================\n")

    verify_ok = 0
    verify_missing = 0

    for row in rows:

        row_id = row["id"]

        query = f'''
        SELECT COUNT("id")
        FROM "{measurement_name}"
        WHERE "id" = {row_id}
        '''

        result = influx_query(query)

        points = list(result.get_points())

        count = 0

        if len(points) > 0:

            point = points[0]

            if "count" in point:

                count = point["count"]

        if count > 0:

            print(
                f"[OK] id={row_id} "
                f"found ({count} points)"
            )

            verify_ok += 1

        else:

            print(
                f"[MISSING] id={row_id}"
            )

            verify_missing += 1

    print("\n================ VERIFY SUMMARY ================")

    print(f"OK       : {verify_ok}")
    print(f"MISSING  : {verify_missing}")

# ============================================================
# BUILD MODE
# ============================================================

if args.build:

    print("\n================ BUILD MODE ================\n")

    batch = []

    total_points = 0

    for row_idx, row in enumerate(rows):

        try:

            test_start = row["test_start"]
            test_stop = row["test_stop"]

            if test_start is None or test_stop is None:

                print(
                    f"Skipping id={row['id']} "
                    f"(missing start/stop)"
                )

                continue

            # ------------------------------------------------
            # CONVERT TO UTC ISO FORMAT
            # ------------------------------------------------

            start_str = (
                test_start
                .replace(tzinfo=timezone.utc)
                .isoformat()
            )

            stop_str = (
                test_stop
                .replace(tzinfo=timezone.utc)
                .isoformat()
            )

            # ------------------------------------------------
            # QUERY LINK STATUS TIMESTAMPS
            # ------------------------------------------------

            timestamp_query = f'''
            SELECT "frames"
            FROM "{reference_measurement}"
            WHERE time >= '{start_str}'
            AND time <= '{stop_str}'
            '''

            result = influx_query(timestamp_query)

            timestamps = set()

            for series in result.raw.get("series", []):

                columns = series.get("columns", [])

                if "time" not in columns:

                    continue

                time_idx = columns.index("time")

                for value_row in series.get("values", []):

                    timestamps.add(value_row[time_idx])

            timestamps = sorted(list(timestamps))

            print(
                f"id={row['id']} "
                f"found {len(timestamps)} timestamps"
            )

            # ------------------------------------------------
            # BUILD POINTS
            # ------------------------------------------------

            for ts in timestamps:

                point = {

                    "measurement": measurement_name,

                    "time": ts,

                    "fields": {

                        "id":
                            int(row["id"]),

                        "test_op":
                            str(row["test_op"])
                            if row["test_op"] is not None
                            else "",

                        "test_pass":
                            int(row["test_pass"])
                            if row["test_pass"] is not None
                            else 0,

                        "db_slot1":
                            int(row["db_slot1"])
                            if row["db_slot1"] is not None
                            else 0,

                        "db_slot2":
                            int(row["db_slot2"])
                            if row["db_slot2"] is not None
                            else 0,

                        "db_slot3":
                            int(row["db_slot3"])
                            if row["db_slot3"] is not None
                            else 0,

                        "db_slot4":
                            int(row["db_slot4"])
                            if row["db_slot4"] is not None
                            else 0
                    }
                }

                batch.append(point)

                total_points += 1

                # --------------------------------------------
                # WRITE BATCH
                # --------------------------------------------

                if len(batch) >= args.batch_size:

                    influx_write(batch)

                    print(
                        f"Wrote batch "
                        f"({len(batch)} points)"
                    )

                    batch = []

                    time.sleep(args.batch_delay)

        except Exception as e:

            print(
                f"Error processing row "
                f"{row_idx}: {e}"
            )

            time.sleep(2)

    # ========================================================
    # WRITE FINAL BATCH
    # ========================================================

    if len(batch) > 0:

        influx_write(batch)

        print(
            f"Wrote final batch "
            f"({len(batch)} points)"
        )

    print("\n================ BUILD SUMMARY ================")

    print(f"Total points written: {total_points}")

# ============================================================
# DONE
# ============================================================

print("\nDone.")
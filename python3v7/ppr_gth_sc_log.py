#!/usr/bin/env python3

import sys
import time
import random
import pymysql
from array import array
import argparse

# Tilecal libs
from db_lib import *
from db_ppr_ipbus import IPbus
from db_influx_lib import *

# ============================================================
# INFLUXDB SETUP
# ============================================================

# host = "piro-atlas-lab.fysik.su.se"

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
    database=database
)

# ============================================================
# MARIADB SETUP
# ============================================================

mariadb_host = "192.168.0.200"
mariadb_port = 3306
mariadb_user = "tiledb"
mariadb_password = "T1le-db-word!"
mariadb_database = "tiledb"

# ============================================================
# CONNECTION SETUP
# ============================================================

test_time_per_link = 3
total_cmd = 0
error_cmd = 0

parser = argparse.ArgumentParser(
    description="PPr monitoring script"
)

parser.add_argument(
    "--ppr-label",
    default="PprGTH",
    help="Label used for InfluxDB tags"
)

parser.add_argument(
    "--controlhub-ip",
    default="192.168.0.201",
    help="ControlHub IP address"
)

parser.add_argument(
    "--ppr-ip",
    default="192.168.0.2",
    help="PPr IP address"
)

parser.add_argument(
    "--benchtest",
    action="store_true",
    help="Enable MariaDB benchtest polling and InfluxDB Bench Test logging"
)

args = parser.parse_args()

ppr_label = args.ppr_label
controlhub_ipaddress = args.controlhub_ip
ppr_ipaddress = args.ppr_ip
benchtest_enabled = args.benchtest


# ============================================================
# CONNECTION FUNCTION
# ============================================================

def connect_ppr():

    reconnect_delay = 5

    while True:

        try:

            test0 = random.randint(0, 0xFFFF)

            ppr = IPbus(
                controlhub_ipaddress,
                ppr_ipaddress
            )

            ppr.RODConfigWrite(0, 0)
            ppr.RODConfigWrite(0, test0)

            test1 = ppr.ReadVal(0)

            if test1 == test0:

                print(
                    f"PPr Loopback reg test Passed! "
                    f"{hex(test0)} = {hex(test1)}"
                )

                print(
                    f"Connected to controlhub: "
                    f"{controlhub_ipaddress}, "
                    f"interfaced with PPr: "
                    f"{ppr_ipaddress}, "
                    f"FW version: "
                    f"{hex(ppr.ReadVal(1))}"
                )

                return ppr

            else:

                print(
                    "Warning! PPr Loopback reg test failed!"
                )

                print(
                    f"{hex(test0)} != {hex(test1)}"
                )

        except Exception as e:

            print(f"Connection failed: {e}")

        print(
            f"Retrying connection in "
            f"{reconnect_delay} seconds..."
        )

        time.sleep(reconnect_delay)

        reconnect_delay = min(
            reconnect_delay * 2,
            60
        )

# ============================================================
# CONNECT TO MARIADB
# ============================================================

def connect_mariadb():

    reconnect_delay = 5

    while True:

        try:

            mariadb = pymysql.connect(

                host=mariadb_host,
                port=mariadb_port,
                user=mariadb_user,
                password=mariadb_password,
                database=mariadb_database,

                cursorclass=pymysql.cursors.DictCursor,

                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                autocommit=True

            )

            print("Connected to MariaDB")

            return mariadb

        except Exception as e:

            print(
                f"MariaDB connection failed: {e}"
            )

        print(
            f"Retrying MariaDB connection in "
            f"{reconnect_delay} seconds..."
        )

        time.sleep(reconnect_delay)

        reconnect_delay = min(
            reconnect_delay * 2,
            60
        )

# ============================================================
# GET ACTIVE BENCH TESTS
# ============================================================

def get_active_bench_tests():

    global mariadb

    while True:

        try:

            mariadb.ping(reconnect=True)

            with mariadb.cursor() as cursor:

                cursor.execute("""

                    SELECT
                        id,
                        test_op,
                        test_pass,
                        db_slot1,
                        db_slot2,
                        db_slot3,
                        db_slot4
                    FROM benchtest
                    WHERE test_stop IS NULL

                """)

                return cursor.fetchall()

        except Exception as e:

            print(
                f"MariaDB query failed: {e}"
            )

            print(
                "Reconnecting MariaDB..."
            )

            try:

                mariadb = connect_mariadb()

            except Exception as reconnect_error:

                print(
                    f"MariaDB reconnect failed: "
                    f"{reconnect_error}"
                )

                time.sleep(5)

# ============================================================
# CONNECT
# ============================================================

ppr = connect_ppr()

if benchtest_enabled:
    mariadb = connect_mariadb()
else:
    mariadb = None

# ============================================================
# INIT VARIABLES
# ============================================================

nframesMD = [0.0] * 4

nCRCerrorsA0_MD = [0.0] * 4
nCRCerrorsA1_MD = [0.0] * 4
nCRCerrorsB0_MD = [0.0] * 4
nCRCerrorsB1_MD = [0.0] * 4

nCRCEffectiveErrorsA = [0.0] * 4
nCRCEffectiveErrorsB = [0.0] * 4

LatA = [0.0] * 4
LatB = [0.0] * 4

fractionA0 = [0.0] * 4
fractionA1 = [0.0] * 4
fractionB0 = [0.0] * 4
fractionB1 = [0.0] * 4

Nbits = [0.0] * 4

BERA0 = [0.0] * 4
BERA1 = [0.0] * 4
BERB0 = [0.0] * 4
BERB1 = [0.0] * 4

DownLinkStatusA = [False] * 4
DownLinkStatusB = [False] * 4

StatusA = [0] * 4
StatusA1 = [0] * 4
StatusB = [0] * 4
StatusB1 = [0] * 4

uplink_labels = [
    "A0",
    "A1",
    "B0",
    "B1"
]

firstMD = 0
nMD = 4
verbose = False

# ============================================================
# MAIN LOOP
# ============================================================

while True:

    try:

        all_points = []

        reconnect_needed = False

        for md in range(firstMD, firstMD + nMD):

            # ------------------------------------------------
            # STATUS READ
            # ------------------------------------------------

            StatusA[md] = ppr.ReadVal(
                0x10 + md * 2
            )

            StatusA1[md] = (
                (StatusA[md] & 0xFFFF0000) >> 16
            )

            StatusB[md] = ppr.ReadVal(
                0x11 + md * 2
            )

            StatusB1[md] = (
                (StatusB[md] & 0xFFFF0000) >> 16
            )

            time.sleep(0.01)

            DownLinkStatusA[md] = (
                ppr.GetDownLinkStatus(md, "A0")
            )

            DownLinkStatusB[md] = (
                ppr.GetDownLinkStatus(md, "B0")
            )

            nframesMD[md] = (
                (ppr.ReadVal(0x22 + (8 * md)) << 32)
                + ppr.ReadVal(0x21 + 8 * md)
            )

            if nframesMD[md] <= 0:

                print(
                    "nFrames=0! "
                    "Communication error? Reconnecting..."
                )

                reconnect_needed = True
                break

            nCRCerrorsA0_MD[md] = ppr.ReadVal(
                0x23 + (8 * md)
            )

            nCRCerrorsA1_MD[md] = ppr.ReadVal(
                0x24 + (8 * md)
            )

            nCRCerrorsB0_MD[md] = ppr.ReadVal(
                0x25 + (8 * md)
            )

            nCRCerrorsB1_MD[md] = ppr.ReadVal(
                0x26 + (8 * md)
            )

            nCRCEffectiveErrorsA[md] = ppr.ReadVal(
                0x27 + (8 * md)
            )

            nCRCEffectiveErrorsB[md] = ppr.ReadVal(
                0x28 + (8 * md)
            )

            fractionA0[md] = (
                (1_000_000 * nCRCerrorsA0_MD[md])
                / nframesMD[md]
            )

            fractionA1[md] = (
                (1_000_000 * nCRCerrorsA1_MD[md])
                / nframesMD[md]
            )

            fractionB0[md] = (
                (1_000_000 * nCRCerrorsB0_MD[md])
                / nframesMD[md]
            )

            fractionB1[md] = (
                (1_000_000 * nCRCerrorsB1_MD[md])
                / nframesMD[md]
            )

            lat_reg = ppr.ReadVal(
                0x85 + md // 2
            )

            LatA[md] = (
                (lat_reg >> (16 * (md % 2)))
                & 0x00FF
            )

            LatB[md] = (
                (lat_reg >> (8 + 16 * (md % 2)))
                & 0x00FF
            )

            Nbits[md] = 120 * nframesMD[md]

            BERA0[md] = (
                float(nCRCerrorsA0_MD[md])
                / Nbits[md]
            )

            BERA1[md] = (
                float(nCRCerrorsA1_MD[md])
                / Nbits[md]
            )

            BERB0[md] = (
                float(nCRCerrorsB0_MD[md])
                / Nbits[md]
            )

            BERB1[md] = (
                float(nCRCerrorsB1_MD[md])
                / Nbits[md]
            )

            # ------------------------------------------------
            # FPGA SIDE ALIVE STATUS
            # ------------------------------------------------

            a_side_alive = (
                bool(StatusA[md] & 0x400)
                or bool(StatusA1[md] & 0x400)
            )

            b_side_alive = (
                bool(StatusB[md] & 0x400)
                or bool(StatusB1[md] & 0x400)
            )

            # ------------------------------------------------
            # PREP DATA FOR INFLUX
            # ------------------------------------------------

            nframes = [nframesMD[md]] * 4

            ncrc = [
                nCRCerrorsA0_MD[md],
                nCRCerrorsA1_MD[md],
                nCRCerrorsB0_MD[md],
                nCRCerrorsB1_MD[md]
            ]

            lat = [
                LatA[md],
                LatA[md],
                LatB[md],
                LatB[md]
            ]

            downlink_status = [
                DownLinkStatusA[md],
                DownLinkStatusA[md],
                DownLinkStatusB[md],
                DownLinkStatusB[md]
            ]

            ber = [
                BERA0[md],
                BERA1[md],
                BERB0[md],
                BERB1[md]
            ]

            tx_pll = [
                StatusA[md] & 0x1,
                StatusA1[md] & 0x1,
                StatusB[md] & 0x1,
                StatusB1[md] & 0x1
            ]

            rx_frameclk = [
                (StatusA[md] & 0x2) >> 1,
                (StatusA1[md] & 0x2) >> 1,
                (StatusB[md] & 0x2) >> 1,
                (StatusB1[md] & 0x2) >> 1
            ]

            rx_wordclk = [
                (StatusA[md] & 0x4) >> 2,
                (StatusA1[md] & 0x4) >> 2,
                (StatusB[md] & 0x4) >> 2,
                (StatusB1[md] & 0x4) >> 2
            ]

            mgt_rdy = rx_wordclk

            bitslip = [
                (StatusA[md] & 0x3F0) >> 4,
                (StatusA1[md] & 0x3F0) >> 4,
                (StatusB[md] & 0x3F0) >> 4,
                (StatusB1[md] & 0x3F0) >> 4
            ]

            gbtrx_rdy = [
                (StatusA[md] & 0x400) >> 10,
                (StatusA1[md] & 0x400) >> 10,
                (StatusB[md] & 0x400) >> 10,
                (StatusB1[md] & 0x400) >> 10
            ]

            gbttx_rdy_lost = [
                (StatusA[md] & 0x800) >> 11,
                (StatusA1[md] & 0x800) >> 11,
                (StatusB[md] & 0x800) >> 11,
                (StatusB1[md] & 0x800) >> 11
            ]

            data_error = [
                (StatusA[md] & 0x1000) >> 12,
                (StatusA1[md] & 0x1000) >> 12,
                (StatusB[md] & 0x1000) >> 12,
                (StatusB1[md] & 0x1000) >> 12
            ]

            # ------------------------------------------------
            # WRITE LINK STATUS
            # ------------------------------------------------

            for l in range(4):

                data_point = [{

                    "measurement": "Link Status",

                    "tags": {
                        f"{ppr_label} MD{md+1}":
                        f"uplink {uplink_labels[l]}"
                    },

                    "fields": {

                        "crc": ncrc[l],

                        "frames": nframes[l],

                        "latency": lat[l],

                        "downlink_status":
                            downlink_status[l],

                        "ber": ber[l],

                        "tx_pll": tx_pll[l],

                        "rx_frameclk":
                            rx_frameclk[l],

                        "rx_wordclk":
                            rx_wordclk[l],

                        "mgt_rdy":
                            mgt_rdy[l],

                        "bitslip":
                            bitslip[l],

                        "gbtrx_rdy":
                            gbtrx_rdy[l],

                        "gbttx_rdy_lost":
                            gbttx_rdy_lost[l],

                        "data_error":
                            data_error[l]
                    }
                }]

                all_points.extend(data_point)

            # ------------------------------------------------
            # KU-DNA & DB STATUS
            # ------------------------------------------------

            db_data = []

            dna_data_array = [
                ppr.DB_Read_Val(
                    md,
                    lut_tx_address[c_stb_dna_2]
                ),

                ppr.DB_Read_Val(
                    md,
                    lut_tx_address[c_stb_dna_1]
                ),

                ppr.DB_Read_Val(
                    md,
                    lut_tx_address[c_stb_dna_0]
                )
            ]

            running_time = ppr.DB_Read_Val(
                md,
                lut_tx_address[
                    c_stb_running_time_status
                ]
            )

            db_reg_buff = ppr.DB_Read_Val(
                md,
                lut_tx_address[c_stb_pgood_reg]
            )

            for side, side_name in enumerate(
                ["A", "B"]
            ):

                side_alive = (
                    a_side_alive
                    if side_name == "A"
                    else b_side_alive
                )

                # ----------------------------------------
                # DEAD FPGA -> DEFAULT VALUES
                # ----------------------------------------

                if not side_alive:

                    db_data.append({

                        "measurement": "DB Status",

                        "tags": {
                            f"{ppr_label} MD{md+1}":
                            f"KU FPGA {side_name}"
                        },

                        "fields": {

                            "ku_dna_0": 0,

                            "ku_dna_1": 0,

                            "ku_dna_2": 0,

                            "ku_dna_hex":
                                "000000000000000000000000",

                            "running_time": 0,

                            "db_side": 0,

                            "db_switches": 0
                        }
                    })

                    continue

                # ----------------------------------------
                # NORMAL FPGA
                # ----------------------------------------

                ku_dna = (
                    (dna_data_array[0][side] << 64)
                    | (dna_data_array[1][side] << 32)
                    | dna_data_array[2][side]
                )

                db_data.append({

                    "measurement": "DB Status",

                    "tags": {
                        f"{ppr_label} MD{md+1}":
                        f"KU FPGA {side_name}"
                    },

                    "fields": {

                        "ku_dna_0":
                            dna_data_array[0][side],

                        "ku_dna_1":
                            dna_data_array[1][side],

                        "ku_dna_2":
                            dna_data_array[2][side],

                        "ku_dna_hex":
                            f"{ku_dna:024X}",

                        "running_time":
                            running_time[side],

                        "db_side":
                            (
                                (db_reg_buff[side] >> 27)
                                & 0b1
                            ),

                        "db_switches":
                            (
                                (db_reg_buff[side] >> 28)
                                & 0b1111
                            )
                    }
                })

            all_points.extend(db_data)

            # ------------------------------------------------
            # XADC DATA
            # ------------------------------------------------

            xadc_data = []

            xadc_fields = {
                "A": {},
                "B": {}
            }

            for xadc_idx, xadc_address in enumerate(
                lut_xadc_address
            ):

                addr = 0xA00 | xadc_address

                the_data = ppr.DB_Read_Val(
                    md,
                    addr
                )

                side_a_val = the_data[0]
                side_b_val = the_data[1]

                side_a_eval = (
                    side_a_val
                    * lut_xadc_fa[xadc_idx]
                    + lut_xadc_fb[xadc_idx]
                )

                side_b_eval = (
                    side_b_val
                    * lut_xadc_fa[xadc_idx]
                    + lut_xadc_fb[xadc_idx]
                )

                side_a_reeval = (
                    side_a_eval
                    * lut_xadc_fg[xadc_idx]
                )

                side_b_reeval = (
                    side_b_eval
                    * lut_xadc_fg[xadc_idx]
                )

                data_label = (
                    lut_xadc_address_labels[
                        xadc_idx
                    ]
                )

                xadc_fields["A"][
                    data_label
                ] = side_a_reeval

                xadc_fields["B"][
                    data_label
                ] = side_b_reeval

            # ------------------------------------------------
            # PG GOOD BITS
            # ------------------------------------------------

            the_data = ppr.DB_Read_Val(
                md,
                lut_tx_address[c_stb_pgood_reg]
            )

            for bit_num, label in enumerate(
                lut_pgood_labels
            ):

                xadc_fields["A"][label] = (
                    (the_data[0] >> bit_num)
                    & 0b1
                )

                xadc_fields["B"][label] = (
                    (the_data[1] >> bit_num)
                    & 0b1
                )

            # ------------------------------------------------
            # APPEND XADC DATA
            # ------------------------------------------------

            for side_name in ["A", "B"]:

                side_alive = (
                    a_side_alive
                    if side_name == "A"
                    else b_side_alive
                )

                # ----------------------------------------
                # DEAD FPGA -> DEFAULT VALUES
                # ----------------------------------------

                if not side_alive:

                    default_fields = {}

                    for label in (
                        lut_xadc_address_labels
                    ):

                        default_fields[label] = 0.0

                    for label in lut_pgood_labels:

                        default_fields[label] = 0

                    xadc_data.append({

                        "measurement": "xADC",

                        "tags": {
                            f"{ppr_label} MD{md+1}":
                            f"KU FPGA {side_name}"
                        },

                        "fields": default_fields
                    })

                    continue

                # ----------------------------------------
                # NORMAL FPGA
                # ----------------------------------------

                xadc_data.append({

                    "measurement": "xADC",

                    "tags": {
                        f"{ppr_label} MD{md+1}":
                        f"KU FPGA {side_name}"
                    },

                    "fields":
                        xadc_fields[side_name]
                })

            all_points.extend(xadc_data)

        # ------------------------------------------------
        # ACTIVE BENCH TEST LOGGING
        # ------------------------------------------------

        if benchtest_enabled:

            active_tests = get_active_bench_tests()

            if active_tests is not None:
                for test in active_tests:

                    all_points.append({

                        "measurement": "Bench Test",

                        "fields": {

                            "id":
                                int(test["id"]),

                            "test_op":
                                str(test["test_op"])
                                if test["test_op"] is not None
                                else "",

                            "test_pass":
                                int(test["test_pass"])
                                if test["test_pass"] is not None
                                else 0,

                            "db_slot1":
                                int(test["db_slot1"])
                                if test["db_slot1"] is not None
                                else 0,

                            "db_slot2":
                                int(test["db_slot2"])
                                if test["db_slot2"] is not None
                                else 0,

                            "db_slot3":
                                int(test["db_slot3"])
                                if test["db_slot3"] is not None
                                else 0,

                            "db_slot4":
                                int(test["db_slot4"])
                                if test["db_slot4"] is not None
                                else 0
                        }
                    })

        # ----------------------------------------------------
        # RECONNECT IF NEEDED
        # ----------------------------------------------------

        if reconnect_needed:

            ppr = connect_ppr()
            continue

        # ----------------------------------------------------
        # WRITE ALL POINTS
        # ----------------------------------------------------

        if all_points:

            influxdb.write_points(
                all_points,
                batch_size=500
            )

        time.sleep(1)

    except KeyboardInterrupt:

        print("\nExiting...")
        sys.exit(0)

    except Exception as e:

        print(f"MAIN LOOP ERROR: {e}")

        time.sleep(5)

        try:

            ppr = connect_ppr()

        except Exception as reconnect_error:

            print(
                f"Reconnect failed: "
                f"{reconnect_error}"
            )

            time.sleep(10)


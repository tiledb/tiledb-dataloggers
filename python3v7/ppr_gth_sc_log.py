#!/usr/bin/env python3
import sys
import time
import random
from array import array

# Tilecal libs
from db_lib import *
from db_ppr_ipbus import IPbus
from db_influx_lib import *

# -------------------- INFLUXDB SETUP --------------------
# host = "piro-atlas-lab.fysik.su.se"
host = "192.168.0.200"
port = 8086
username = "tiledb"
password = "T1le-db-word!"
database = "tiledb"

influxdb = InfluxDBClient(host=host, port=port, username=username, password=password, database=database)

# -------------------- CONNECTION SETUP --------------------
test_time_per_link = 3
total_cmd = 0
error_cmd = 0

ppr_label = "PprGTH"
controlhub_ipaddress = "192.168.0.201"
ppr_ipaddress = "192.168.0.2"

# Loopback test
test0 = random.randint(0, 0xFFFF)
connection_flag = False
while not connection_flag:
    ppr = IPbus(controlhub_ipaddress, ppr_ipaddress)
    ppr.RODConfigWrite(0, 0)
    ppr.RODConfigWrite(0, test0)
    test1 = ppr.ReadVal(0)
    if test1 == test0:
        print(f"PPr Loopback reg test Passed! {hex(test0)} = {hex(test1)}")
        connection_flag = True
    else:
        print("Warning! PPr Loopback reg test failed!")
        print(f"{hex(test0)} != {hex(test1)}")
        time.sleep(5)

print(f"Connected to controlhub: {controlhub_ipaddress}, interfaced with PPr: {ppr_ipaddress}, FW version: {hex(ppr.ReadVal(1))}")

# -------------------- INIT VARIABLES --------------------
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
uplink_labels = ["A0", "A1", "B0", "B1"]

firstMD = 0
nMD = 4
verbose = False

# -------------------- MAIN LOOP --------------------
while True:
    for md in range(firstMD, firstMD + nMD):
        # -------------------- STATUS READ --------------------
        StatusA[md] = ppr.ReadVal(0x10 + md * 2)
        StatusA1[md] = (StatusA[md] & 0xFFFF0000) >> 16
        StatusB[md] = ppr.ReadVal(0x11 + md * 2)
        StatusB1[md] = (StatusB[md] & 0xFFFF0000) >> 16

        time.sleep(0.01)

        DownLinkStatusA[md] = ppr.GetDownLinkStatus(md, "A0")
        DownLinkStatusB[md] = ppr.GetDownLinkStatus(md, "B0")

        nframesMD[md] = (ppr.ReadVal(0x22 + (8 * md)) << 32) + ppr.ReadVal(0x21 + 8 * md)
        nCRCerrorsA0_MD[md] = ppr.ReadVal(0x23 + (8 * md))
        nCRCerrorsA1_MD[md] = ppr.ReadVal(0x24 + (8 * md))
        nCRCerrorsB0_MD[md] = ppr.ReadVal(0x25 + (8 * md))
        nCRCerrorsB1_MD[md] = ppr.ReadVal(0x26 + (8 * md))
        nCRCEffectiveErrorsA[md] = ppr.ReadVal(0x27 + (8 * md))
        nCRCEffectiveErrorsB[md] = ppr.ReadVal(0x28 + (8 * md))

        if nframesMD[md] == 0:
            print("nFrames=0! Communication error? Reconnecting...")
            time.sleep(5)
            ppr = IPbus(controlhub_ipaddress, ppr_ipaddress)
            continue

        fractionA0[md] = (1_000_000 * nCRCerrorsA0_MD[md]) / nframesMD[md]
        fractionA1[md] = (1_000_000 * nCRCerrorsA1_MD[md]) / nframesMD[md]
        fractionB0[md] = (1_000_000 * nCRCerrorsB0_MD[md]) / nframesMD[md]
        fractionB1[md] = (1_000_000 * nCRCerrorsB1_MD[md]) / nframesMD[md]

        LatA[md] = (ppr.ReadVal(0x85 + md // 2) >> (16 * (md % 2))) & 0x00FF
        LatB[md] = (ppr.ReadVal(0x85 + md // 2) >> (8 + 16 * (md % 2))) & 0x00FF

        Nbits[md] = 120 * nframesMD[md]
        BERA0[md] = float(nCRCerrorsA0_MD[md]) / Nbits[md]
        BERA1[md] = float(nCRCerrorsA1_MD[md]) / Nbits[md]
        BERB0[md] = float(nCRCerrorsB0_MD[md]) / Nbits[md]
        BERB1[md] = float(nCRCerrorsB1_MD[md]) / Nbits[md]

        # -------------------- PREP DATA FOR INFLUX --------------------
        nframes = [nframesMD[md]] * 4
        ncrc = [nCRCerrorsA0_MD[md], nCRCerrorsA1_MD[md], nCRCerrorsB0_MD[md], nCRCerrorsB1_MD[md]]
        lat = [LatA[md], LatA[md], LatB[md], LatB[md]]
        downlink_status = [DownLinkStatusA[md], DownLinkStatusA[md], DownLinkStatusB[md], DownLinkStatusB[md]]
        ber = [BERA0[md], BERA1[md], BERB0[md], BERB1[md]]
        tx_pll = [StatusA[md] & 0x1, StatusA1[md] & 0x1, StatusB[md] & 0x1, StatusB1[md] & 0x1]
        rx_frameclk = [(StatusA[md] & 0x2) >> 1, (StatusA1[md] & 0x2) >> 1, (StatusB[md] & 0x2) >> 1, (StatusB1[md] & 0x2) >> 1]
        rx_wordclk = [(StatusA[md] & 0x4) >> 2, (StatusA1[md] & 0x4) >> 2, (StatusB[md] & 0x4) >> 2, (StatusB1[md] & 0x4) >> 2]
        mgt_rdy = rx_wordclk
        bitslip = [(StatusA[md] & 0x3F0) >> 4, (StatusA1[md] & 0x3F0) >> 4, (StatusB[md] & 0x3F0) >> 4, (StatusB1[md] & 0x3F0) >> 4]
        gbtrx_rdy = [(StatusA[md] & 0x400) >> 10, (StatusA1[md] & 0x400) >> 10, (StatusB[md] & 0x400) >> 10, (StatusB1[md] & 0x400) >> 10]
        gbttx_rdy_lost = [(StatusA[md] & 0x800) >> 11, (StatusA1[md] & 0x800) >> 11, (StatusB[md] & 0x800) >> 11, (StatusB1[md] & 0x800) >> 11]
        data_error = [(StatusA[md] & 0x1000) >> 12, (StatusA1[md] & 0x1000) >> 12, (StatusB[md] & 0x1000) >> 12, (StatusB1[md] & 0x1000) >> 12]

        # -------------------- WRITE TO INFLUX --------------------
        for l in range(4):
            data_point = [{
                "measurement": "Link Status",
                "tags": {f"{ppr_label} MD{md+1}": f"uplink {uplink_labels[l]}"},
                "fields": {
                    "crc": ncrc[l],
                    "frames": nframes[l],
                    "latency": lat[l],
                    "downlink_status": downlink_status[l],
                    "ber": ber[l],
                    "tx_pll": tx_pll[l],
                    "rx_frameclk": rx_frameclk[l],
                    "rx_wordclk": rx_wordclk[l],
                    "mgt_rdy": mgt_rdy[l],
                    "bitslip": bitslip[l],
                    "gbtrx_rdy": gbtrx_rdy[l],
                    "gbttx_rdy_lost": gbttx_rdy_lost[l],
                    "data_error": data_error[l]
                }
            }]
            influxdb.write_points(data_point)

        # -------------------- KU-DNA & DB STATUS --------------------
        db_data = []
        dna_data_array = [
            ppr.DB_Read_Val(md, lut_tx_address[c_stb_dna_2]),
            ppr.DB_Read_Val(md, lut_tx_address[c_stb_dna_1]),
            ppr.DB_Read_Val(md, lut_tx_address[c_stb_dna_0])
        ]
        running_time = ppr.DB_Read_Val(md, lut_tx_address[c_stb_running_time_status])
        db_reg_buff = ppr.DB_Read_Val(md, lut_tx_address[c_stb_pgood_reg])

        for side, side_name in enumerate(["A", "B"]):
            db_data.append({
                "measurement": "DB Status",
                "tags": {f"{ppr_label} MD{md+1}": f"KU FPGA {side_name}"},
                "fields": {
                    "ku_dna_0": dna_data_array[0][side],
                    "ku_dna_1": dna_data_array[1][side],
                    "ku_dna_2": dna_data_array[2][side],
                    "running_time": running_time[side],
                    "db_side": (db_reg_buff[side] >> 27) & 0b1,
                    "db_switches": (db_reg_buff[side] >> 28) & 0b1111
                }
            })
        influxdb.write_points(db_data)

        # -------------------- XADC DATA --------------------
        xadc_data = []
        for xadc_idx, xadc_address in enumerate(lut_xadc_address):
            addr = 0xA00 | xadc_address
            the_data = ppr.DB_Read_Val(md, addr)
            side_a_val = the_data[0]
            side_b_val = the_data[1]
            side_a_eval = side_a_val * lut_xadc_fa[xadc_idx] + lut_xadc_fb[xadc_idx]
            side_b_eval = side_b_val * lut_xadc_fa[xadc_idx] + lut_xadc_fb[xadc_idx]
            side_a_reeval = side_a_eval * lut_xadc_fg[xadc_idx]
            side_b_reeval = side_b_eval * lut_xadc_fg[xadc_idx]
            data_label = lut_xadc_address_labels[xadc_idx]

            for side, val in enumerate([side_a_reeval, side_b_reeval]):
                xadc_data.append({
                    "measurement": "xADC",
                    "tags": {f"{ppr_label} MD{md+1}": f"KU FPGA {'A' if side==0 else 'B'}"},
                    "fields": {data_label: val}
                })

        # -------------------- PG GOOD BITS --------------------
        the_data = ppr.DB_Read_Val(md, lut_tx_address[c_stb_pgood_reg])
        for bit_num, label in enumerate(lut_pgood_labels):
            for side, side_name in enumerate(["A", "B"]):
                xadc_data.append({
                    "measurement": "xADC",
                    "tags": {f"{ppr_label} MD{md+1}": f"KU FPGA {side_name}"},
                    "fields": {label: (the_data[side] >> bit_num) & 0b1}
                })

        influxdb.write_points(xadc_data)

    time.sleep(1)

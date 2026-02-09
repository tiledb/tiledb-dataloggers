#!/usr/bin/env python3
import time
import random
import datetime

# Tilecal libs
from db_lib import *
from db_ppr_ipbus import IPbus
from db_influx_lib import *

# ==========================================================
# INFLUXDB SETUP
# ==========================================================
host = "piro-atlas-lab.fysik.su.se"
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

# ==========================================================
# CONNECTION SETUP
# ==========================================================
controlhub_ipaddress = "192.168.0.201"
ppr_ipaddress = "192.168.0.2"
ppr_label = "PprGTH"

def connect_ppr():
    while True:
        try:
            ppr = IPbus(controlhub_ipaddress, ppr_ipaddress)
            test0 = random.randint(0, 0xFFFF)
            ppr.RODConfigWrite(0, 0)
            ppr.RODConfigWrite(0, test0)
            test1 = ppr.ReadVal(0)

            if test1 == test0:
                print(f"PPr Loopback Passed ({hex(test0)})")
                print(f"FW version: {hex(ppr.ReadVal(1))}")
                return ppr
            else:
                print("Loopback failed. Retrying...")
        except Exception as e:
            print("Connection error:", e)
        time.sleep(5)

ppr = connect_ppr()

# ==========================================================
# CIS CONFIGURATION
# ==========================================================
BCID_discharge = 2200
BCID_charge = 500
bcid_l1a = BCID_discharge + 44
Gain_cis = 0
DAC_CIS = 0xfc0

nMD = 4
nchan = 12
md_first = 0

nsamp = ppr.ReadVal(0x9F) & 0xFF
if nsamp == 0:
    nsamp = 16

# -------------------- Disable external TTC, enable internal --------------------
ppr.RODConfigWrite(0x2, 0x87)
ppr.RODConfigWrite(0x4, 0x0)
ppr.RODConfigWrite(0x5, 0x0)

DisableDCS = 1
ConfigDCS = (DisableDCS << 17)
ppr.RODConfigWrite(0x6, ConfigDCS)

# -------------------- Pedestal configuration --------------------
stableP = 1328
stableM = 2210
pedestalDAC = 10
chargeP = stableP + pedestalDAC
chargeM = stableM - pedestalDAC

for adc in range(nchan):
    FPGA = (adc // 6 << 1) + (adc % 2)
    card = (adc // 2) % 3

    for base, value in [(0x6000, chargeP), (0x7000, chargeM),
                        (0x4000, chargeP), (0x5000, chargeM)]:
        ppr.AsyncWrite(md_first, 0x1, 0x8000000)
        time.sleep(0.0001)
        ppr.AsyncWrite(md_first, 0x1, (1 << 22) + (FPGA << 18) + (card << 16) + base + int(value))
        time.sleep(0.0001)
        ppr.AsyncWrite(md_first, 0x1, 0x8000000)

    # Load LG / HG
    for load in [0xC000, 0xD000]:
        ppr.AsyncWrite(md_first, 0x1, 0x80000000)
        time.sleep(0.0001)
        ppr.AsyncWrite(md_first, 0x1, (1 << 22) + (FPGA << 18) + (card << 16) + load)
        time.sleep(0.0001)

# -------------------- Enable CIS --------------------
BCIDcharge = BCID_charge << 2
BCIDdischarge = BCID_discharge << 14
CIS_Enable = 1
CIS_Disable = 0
CIS_Gain = Gain_cis << 1

ppr.AsyncWrite(md_first, cfb_cis_config,
               BCIDdischarge + BCIDcharge + CIS_Gain + CIS_Enable)

print("CIS configured. Starting main logging loop...")

# ==========================================================
# MAIN LOOP
# ==========================================================
while True:

    try:
        all_points = []
        ppr.AsyncWrite(md_first, cfb_cis_config,
               BCIDdischarge + BCIDcharge + CIS_Gain + CIS_Enable)

        for md in range(md_first, md_first + nMD):

            # -------------------- Trigger CIS --------------------
            ppr.SyncClear()
            ppr.SyncRest()
            ppr.RODWrite(bcid_l1a & 0xFFF, 0x3)
            ppr.SyncLoop(0)
            ppr.SyncClear()
            ppr.SyncRest()

            # -------------------- Read raw samples --------------------
            the_data = ppr.RODReadMD(
                md=md,
                nchan=nchan,
                nsamp=nsamp,
                stride=32
            )

            # -------------------- Per-channel pulse extraction --------------------
            for ch in range(nchan):

                hg = [(word >> 16) & 0xFFF for word in the_data[ch]]
                lg = [word & 0xFFF for word in the_data[ch]]

                # Baseline
                baseline_hg = min(hg)
                baseline_lg = min(lg)
                hg_corr = [v - baseline_hg for v in hg]
                lg_corr = [v - baseline_lg for v in lg]

                # Height
                height_hg = max(hg_corr)
                height_lg = max(lg_corr)

                # Center (weighted mean)
                sum_hg = sum(hg_corr)
                sum_lg = sum(lg_corr)
                center_hg = sum(i*v for i,v in enumerate(hg_corr))/sum_hg if sum_hg>0 else 0
                center_lg = sum(i*v for i,v in enumerate(lg_corr))/sum_lg if sum_lg>0 else 0

                # -------------------- Prepare Influx point --------------------
                all_points.append({
                    "measurement": "CIS",
                    "tags": {
                        f"{ppr_label} MD{md+1}": f"CH{ch}",
                    },
                    "time": datetime.datetime.utcnow().isoformat(),
                    "fields": {
                        "height_hg": float(height_hg),
                        "height_lg": float(height_lg),
                        "center_hg": float(center_hg),
                        "center_lg": float(center_lg)
                    }
                })

        # -------------------- Write batch to Influx --------------------
        # print(f"{datetime.datetime.now()} - Writing {len(all_points)} points to InfluxDB...")
        influxdb.write_points(all_points)
        # print(f"{datetime.datetime.now()} - Logged CIS pulse data (4 MDs)")

        ppr.AsyncWrite(md_first, cfb_cis_config,
               BCIDdischarge + BCIDcharge + CIS_Gain + CIS_Disable)
        time.sleep(120)

    except Exception as e:
        print("Runtime error:", e)
        print("Reconnecting in 5 seconds...")
        time.sleep(5)
        ppr = connect_ppr()

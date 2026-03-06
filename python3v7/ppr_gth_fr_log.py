#!/usr/bin/env python3
import time
import random
import datetime
import Herakles
import math
from ppr_gth_fr_functions import *


# Tilecal libs
from db_lib import *
from db_ppr_ipbus import PPr, FEB, PPrReg, IPbus
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
            print(f"Connecting to PPr @ {ppr_ipaddress}")
            ipbus = Herakles.Uhal(f"tcp://{controlhub_ipaddress}:10203?target={ppr_ipaddress}:50001")
            ppr = PPr(ipbus)

            
            test0 = random.randint(0, 0xFFFF)
            ppr.write(0, 0)
            ppr.write(0, test0)
            test1 = ppr.read(0)

            if test1 == test0:
                print(f"PPr Loopback Passed ({hex(test0)})")
                print(f"FW version: {hex(ppr.get_firmware_version())}")
                return ppr
            else:
                print("Loopback failed. Retrying...")
        except Exception as e:
            print("Connection error:", e)
        time.sleep(5)

ppr = connect_ppr()
feb = FEB(ppr)
ipbus = IPbus(controlhub_ipaddress, ppr_ipaddress)




# ==========================================================
# MAIN LOOP
# ==========================================================
while True:

    try:
        all_points = []
        all_points = adc_lin_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        time.sleep(10)

        all_points = []
        all_points = cis_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        time.sleep(10)
        
        all_points = []
        all_points = cis_lin_readout(ppr, feb, ppr_label, gain=0)
        influxdb.write_points(all_points)
        time.sleep(10)

        all_points = []
        all_points = cis_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        time.sleep(10)
        
        all_points = []
        all_points = cis_lin_readout(ppr, feb, ppr_label, gain=1)
        influxdb.write_points(all_points)
        time.sleep(10)

        all_points = []
        all_points = cis_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        time.sleep(10)
        
        
        # time.sleep(60)
        
    except Exception as e:
        print("Runtime error:", e)
        print("Reconnecting in 5 seconds...")
        time.sleep(5)
        exit(1)

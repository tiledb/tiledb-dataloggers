#!/usr/bin/env python3
import time
import random
import datetime
import Herakles
import math
from ppr_gth_fr_functions import *
import gc
import psutil
import argparse


# Tilecal libs
from db_lib import *
from db_ppr_ipbus import PPr, FEB, PPrReg, IPbus
from db_influx_lib import *

def print_memory_usage():
    mem = psutil.virtual_memory()

    print(f"Total: {mem.total / 1024**3:.2f} GB")
    print(f"Available: {mem.available / 1024**3:.2f} GB")
    print(f"Used: {mem.used / 1024**3:.2f} GB")
    print(f"Free: {mem.free / 1024**3:.2f} GB")

def print_memory_usage_compact():
    mem = psutil.virtual_memory()
    process = psutil.Process()
    proc_mem = process.memory_info().rss  # Resident Set Size (actual RAM used)

    print(
        f"T: {mem.total / 1024**3:.2f} GB",
        f"A: {mem.available / 1024**3:.2f} GB",
        f"U: {mem.used / 1024**3:.2f} GB",
        f"F: {mem.free / 1024**3:.2f} GB",
        f"P: {proc_mem / 1024**2:.1f} MB"  # process memory
    )

def check_memory_or_exit(threshold_mb=500):
    mem = psutil.virtual_memory()
    available_mb = mem.available / (1024**2)

    if available_mb < threshold_mb:
        print(f"Low memory detected: {available_mb:.1f} MB available. Exiting...")
        exit(1)

# ==========================================================
# INFLUXDB SETUP
# ==========================================================
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

# ==========================================================
# CONNECTION SETUP
# ==========================================================
parser = argparse.ArgumentParser(description="PPr monitoring script")

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

args = parser.parse_args()

ppr_label = args.ppr_label
controlhub_ipaddress = args.controlhub_ip
ppr_ipaddress = args.ppr_ip

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
last_eye_time = 0  # or time.time() if you want delay before first run
wait_time = 1
print_memory_usage()

while True:

    try:
        
        # now = time.time()

        # # Run eye test every 60 seconds
        # if now - last_eye_time >= 60:
        #     all_points = eye_diagram_test(ppr, ppr_label)
        #     influxdb.write_points(all_points)
        #     last_eye_time = now

        print_memory_usage_compact()
        all_points = eye_diagram_test(ppr, ppr_label)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        # last_eye_time = now

        # --- Normal cycle continues ---
        all_points = integrator_lin_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        time.sleep(wait_time)
        

        all_points = adc_lin_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        time.sleep(wait_time)

        all_points = cis_lin_readout(ppr, feb, ppr_label, gain=0)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        time.sleep(wait_time)

        all_points = cis_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        time.sleep(wait_time)

        all_points = cis_lin_readout(ppr, feb, ppr_label, gain=1)
        influxdb.write_points(all_points)
        del all_points
        gc.collect()
        time.sleep(wait_time)

        all_points = cis_test(ppr, feb, ppr_label)
        influxdb.write_points(all_points)
        
        print_memory_usage_compact()
        
        del all_points
        gc.collect()
        time.sleep(wait_time)

        check_memory_or_exit()        
        
        # time.sleep(60)
        
    except Exception as e:
        print("Runtime error:", e)
        print("Reconnecting in 5 seconds...")
        time.sleep(5)
        exit(1)

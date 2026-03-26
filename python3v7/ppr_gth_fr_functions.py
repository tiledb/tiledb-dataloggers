#!/usr/bin/env python3
import time
import os
import Herakles
import time
import random
import datetime
import Herakles
import math
import numpy as np  # still needed for averaging stats
from ppr_gth_fr_functions import *
from db_ppr_ipbus import PPr, FEB, PPrReg

from itertools import groupby
from scipy.special import erfc


# ==========================================================
# SCIENTIFIC FUNCTIONS
# ==========================================================

def avg_std(data):
    arr = np.array(data)
    return np.mean(arr), np.std(arr)

def report_stats(name, data, nchanperMD):
    print(f"\n-- {name} --")
    for ch in range(nchanperMD):
        mean, std = avg_std(data[:, ch])
        print(f"Ch{ch}: mean={mean:.3f}, std={std:.3f}")


def linear_fit(x, y):
    """
    Returns slope, intercept, R2, max deviation
    """
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # slope
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den = sum((x[i] - mean_x) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0

    # intercept
    intercept = mean_y - slope * mean_x

    # predictions
    y_fit = [slope * xi + intercept for xi in x]

    # R^2
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((y[i] - y_fit[i]) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    # max deviation
    max_dev = max(abs(y[i] - y_fit[i]) for i in range(n))

    return slope, intercept, r2, max_dev


def analyze_pulse(samples,
                  pedestal_samples=4,
                  noise_sigma_threshold=5,
                  threshold_fraction=0.5):
    """
    Robust pulse analysis.

    Returns:
        pedestal
        peak_value
        peak_index
        center_of_mass
        fwhm
    If no pulse is detected → returns pedestal and 0s.
    """

    if not samples or len(samples) < pedestal_samples + 2:
        return 0, 0, 0, 0, 0

    # -------------------------------------------------
    # 1) Pedestal estimation (mean of first N samples)
    # -------------------------------------------------
    pedestal_region = samples[:pedestal_samples]
    pedestal = sum(pedestal_region) / pedestal_samples

    # Estimate noise sigma from pedestal region
    variance = sum((x - pedestal) ** 2 for x in pedestal_region) / pedestal_samples
    noise_sigma = math.sqrt(variance)

    # -------------------------------------------------
    # 2) Subtract pedestal
    # -------------------------------------------------
    signal = [x - pedestal for x in samples]

    peak_value = max(signal)
    peak_index = signal.index(peak_value)

    # -------------------------------------------------
    # 3) Pulse existence check
    # -------------------------------------------------
    # Require peak to be significantly above noise
    if noise_sigma == 0 or peak_value < noise_sigma_threshold * noise_sigma:
        return pedestal, 0, 0, 0, 0

    # -------------------------------------------------
    # 4) Center of mass
    # -------------------------------------------------
    total = sum(signal)
    if total > 0:
        center_of_mass = sum(i * v for i, v in enumerate(signal)) / total
    else:
        center_of_mass = 0

    # -------------------------------------------------
    # 5) FWHM
    # -------------------------------------------------
    half_max = peak_value * threshold_fraction
    above_half = [i for i, v in enumerate(signal) if v >= half_max]

    if len(above_half) >= 2:
        fwhm = above_half[-1] - above_half[0]
    else:
        fwhm = 0

    return pedestal, peak_value, peak_index, center_of_mass, fwhm



def adc_lin_test(ppr, feb, ppr_label):
    bcid_l1a = 3200
    dbside = 0  # All FPGAs
    verbose = True
    nsamp = 16
    nchanperMD = 12
    nMD = 4
    firstMD = 0
    nsteps = 10
    step_events = 1

    # Scan parameters
    scan_units = "ADC counts"  # "DACs bias offsets" or "ADC counts"
    min_DAC = 1278# 1650 #1278
    max_DAC = 2261# 2300 #2261

    step_length_DAC = (max_DAC - min_DAC) / nsteps
    step_length_ADC = (4096-0) / nsteps  # if using ADC counts

    # Allocate arrays for averaging
    step_x = []  # injected value per step (ADCped)

    avgHG = [[] for _ in range(nchanperMD * nMD)]
    avgLG = [[] for _ in range(nchanperMD * nMD)]
    stdHG = [[] for _ in range(nchanperMD * nMD)]
    stdLG = [[] for _ in range(nchanperMD * nMD)]


    # ------------------ CONFIG PHASE -------------------

    # print("Setting TTC internal... ", end="")
    ret = ppr.set_global_TTC_internal()
    # print("Ok" if ret else "Failed")

    # print("Resetting CRC counters... ", end="")
    ret = ppr.reset_integrator_fifo()  # or implement reset_CRC_counters()
    # print("Ok" if ret else "Failed")

    # print("Setting PPr enable deadtime bit in Global Trigger Conf...")
    ret = ppr.set_global_trigger_deadtime(0)
    # print(f"  set bit to 0: {'Ok' if ret else 'Fail'}")
    ret = ppr.set_global_trigger_deadtime(1)
    # print(f"  set bit to 1: {'Ok' if ret else 'Fail'}")

    for md in range(firstMD, firstMD + nMD):
        VinDACs = feb.convert_ped_ADC_to_DACs(0)
        DACbiasP, DACbiasN = VinDACs
        for feb_id in range(nchanperMD):
            # print(f"  MD{md} FEB{feb_id}: Setting DACbiasP={DACbiasP}, DACbiasN={DACbiasN}")
            feb.set_ped_HG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_HG_neg(md, dbside, feb_id, DACbiasN)
            feb.set_ped_LG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_LG_neg(md, dbside, feb_id, DACbiasN)
            
            feb.load_ped_HG(md, dbside, feb_id)
            feb.load_ped_LG(md, dbside, feb_id)

    time.sleep(0.01)  # small delay to ensure settings are applied
    feb.send_L1A(bcid_l1a, 3)
    last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
    last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)
    time.sleep(0.1)  # small delay to ensure settings are applied

    for step in range(nsteps):
        # ---- Compute DAC / ADC values per step ----
        if scan_units == "DACs bias offsets":
            DACbiasP = int(min_DAC + step * step_length_DAC)
            DACbiasN = int(max_DAC - step * step_length_DAC)
            ADCped = feb.convert_ped_DACs_to_ADC(DACbiasP, DACbiasN)
            # print(f"Step {step}: DAC Vp={DACbiasP}, DAC Vn={DACbiasN}, ADC counts={ADCped}")
        elif scan_units == "ADC counts":
            ADCped = int(step * step_length_ADC)
            VinDACs = feb.convert_ped_ADC_to_DACs(ADCped)
            DACbiasP, DACbiasN = VinDACs
            # print(f"Step {step}: ADC counts={ADCped}, DAC Vp={DACbiasP}, DAC Vn={DACbiasN}")
        if step>0:
            step_x.append(ADCped)
        # ---- Configure FEBs ----
        # print("Setting FEB ADC bias offsets...")
        for md in range(firstMD, firstMD + nMD):
            for feb_id in range(nchanperMD):
                # print(f"  MD{md} FEB{feb_id}: Setting DACbiasP={DACbiasP}, DACbiasN={DACbiasN}")
                feb.set_ped_HG_pos(md, dbside, feb_id, DACbiasP)
                feb.set_ped_HG_neg(md, dbside, feb_id, DACbiasN)
                feb.set_ped_LG_pos(md, dbside, feb_id, DACbiasP)
                feb.set_ped_LG_neg(md, dbside, feb_id, DACbiasN)
                
                feb.load_ped_HG(md, dbside, feb_id)
                feb.load_ped_LG(md, dbside, feb_id)
                
            # ---- Loop over events per step ----
            time.sleep(0.02)  # small delay to ensure settings are applied
            for event in range(step_events):
                # Reads last Event BCID (disables busy to read pipelines).
                # LastEvtBCID = ppr.get_counter_last_event_BCID()

                # Reads last Event L1ID (disables busy to read pipelines).
                # LastEvtL1ID = ppr.get_counter_last_event_L1ID()
                # print(f"  Step {step} Event {event}: Sent L1A with BCID={bcid_l1a}, LastEvtBCID={LastEvtBCID}")

                # Send L1A trigger
                feb.send_L1A(bcid_l1a, 3)

                # Read pipeline data for selected MDs
                if step>0:
                    for adc in range(nchanperMD):
                        hg_data = ppr.get_data_HG(md, adc, nsamp)
                        lg_data = ppr.get_data_LG(md, adc, nsamp)

                        hg_mean = sum(hg_data) / len(hg_data)
                        lg_mean = sum(lg_data) / len(lg_data)
                        
                        hg_stddev = math.sqrt(sum((x - hg_mean) ** 2 for x in hg_data) / len(hg_data))
                        lg_stddev = math.sqrt(sum((x - lg_mean) ** 2 for x in lg_data) / len(lg_data))
                        # print(f"  Step {step} Event {event}: MD{md} ADC{adc} HG data={hg_data} LG data={lg_data}")
                        
                        avgHG[md * nchanperMD + adc].append(hg_mean)
                        avgLG[md * nchanperMD + adc].append(lg_mean)
                        stdHG[md * nchanperMD + adc].append(hg_stddev)
                        stdLG[md * nchanperMD + adc].append(lg_stddev)
                        # print(f"  Step {step} Event {event}: MD{md} ADC{adc} HG mean={hg_mean:.2f} LG mean={lg_mean:.2f}")
                        # time.sleep(1)  # small delay for readability
                        
                        # print(f"  Step {step} Event {event}: MD{md} ADC{adc} HG={hg_data} LG={lg_data}")
                        # print(f"  Step {step} Event {event}: MD{md} ADC{adc} HG avg={sum(hg_data)/len(hg_data):.2f} LG avg={sum(lg_data)/len(lg_data):.2f}")
                        # print(f"  Step {step} Event {event}: MD{md} ADC{adc} ADCped {ADCped} HG mean={hg_mean:.2f} LG mean={lg_mean:.2f}")

                # Print last event IDs for monitoring
                last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
                last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)
                # print(f"Step {step} done. Last L1ID={last_L1ID}, BCID={last_BCID}")


    for md in range(firstMD, firstMD + nMD):
        VinDACs = feb.convert_ped_ADC_to_DACs(0)
        DACbiasP, DACbiasN = VinDACs
        for feb_id in range(nchanperMD):
            # print(f"  MD{md} FEB{feb_id}: Setting DACbiasP={DACbiasP}, DACbiasN={DACbiasN}")
            feb.set_ped_HG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_HG_neg(md, dbside, feb_id, DACbiasN)
            feb.set_ped_LG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_LG_neg(md, dbside, feb_id, DACbiasN)
            
            feb.load_ped_HG(md, dbside, feb_id)
            feb.load_ped_LG(md, dbside, feb_id)

    time.sleep(0.01)  # small delay to ensure settings are applied
    feb.send_L1A(bcid_l1a, 3)
    last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
    last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)
    time.sleep(0.1)  # small delay to ensure settings are applied

    all_points = []
    now = datetime.datetime.utcnow().isoformat()
    
    for md in range(nMD):
        # ascii_plot_grid(md, step_x, avgHG, avgLG, nchanperMD=nchanperMD, ncols=6, nrows=2, width=20, height=20)
        
        
        
        for ch in range(nchanperMD):
            idx = md * nchanperMD + ch

            # ---- HG fit ----
            slope_hg, offset_hg, r2_hg, maxdev_hg = linear_fit(step_x, avgHG[idx])

            # ---- LG fit ----
            slope_lg, offset_lg, r2_lg, maxdev_lg = linear_fit(step_x, avgLG[idx])

            all_points.append({
                "measurement": "ADC_Linearity",
                "tags": {
                    f"{ppr_label} MD{md+1}": f"CH{ch}",
                },
                "time": now,
                "fields": {
                    "slope_hg": float(slope_hg),
                    "slope_lg": float(slope_lg),
                    "offset_hg": float(offset_hg),
                    "offset_lg": float(offset_lg),
                    "r2_hg": float(r2_hg),
                    "r2_lg": float(r2_lg),
                    "maxdev_hg": float(maxdev_hg),
                    "maxdev_lg": float(maxdev_lg)
                }
            })
            
            
            

            for step_i, adc_in in enumerate(step_x):

                all_points.append({
                    "measurement": "ADC_Linearity_Samples",
                    "tags": {
                        "channel": f"{ppr_label}_MD{md+1}_CH{ch}",
                        "gain": "HG",
                        "step": step_i
                    },
                    "time": now,
                    "fields": {
                        "adc_input": float(adc_in),
                        "value": float(avgHG[idx][step_i]),
                        "std": float(stdHG[idx][step_i])
                    }
                })

                all_points.append({
                    "measurement": "ADC_Linearity_Samples",
                    "tags": {
                        "channel": f"{ppr_label}_MD{md+1}_CH{ch}",
                        "gain": "LG",
                        "step": step_i
                    },
                    "time": now,
                    "fields": {
                        "adc_input": float(adc_in),
                        "value": float(avgLG[idx][step_i]),
                        "std": float(stdLG[idx][step_i])
                    }
                })
            

    return all_points


def read_md_data_with_retry(ppr, feb, md, nsamp, nchanperMD, bcid_l1a, previous_hg_peaks=None, previous_lg_peaks=None,
                            threshold=0.9, max_retries=3):
    """
    Reads all channels of an MD, retries if any peak is below threshold*previous_peak.
    Returns:
        hg_peaks, lg_peaks, hg_centers, lg_centers, hg_fwhm, lg_fwhm, hg_pedestal, lg_pedestal
    """
    retry = 0
    while retry <= max_retries:
        hg_peaks_step = []
        lg_peaks_step = []
        hg_centers_step = []
        lg_centers_step = []
        hg_fwhm_step = []
        lg_fwhm_step = []
        hg_pedestal_step = []
        lg_pedestal_step = []

        # Send L1A before readout
        feb.send_L1A(bcid_l1a, 3)
        time.sleep(0.05)

        for adc in range(nchanperMD):
            hg_data = ppr.get_data_HG(md, adc, nsamp)
            lg_data = ppr.get_data_LG(md, adc, nsamp)

            hg_ped, hg_peak, hg_idx, hg_center, hg_width = analyze_pulse(hg_data)
            lg_ped, lg_peak, lg_idx, lg_center, lg_width = analyze_pulse(lg_data)

            hg_peaks_step.append(hg_peak)
            lg_peaks_step.append(lg_peak)
            hg_centers_step.append(hg_center)
            lg_centers_step.append(lg_center)
            hg_fwhm_step.append(hg_width)
            lg_fwhm_step.append(lg_width)
            hg_pedestal_step.append(hg_ped)
            lg_pedestal_step.append(lg_ped)

        # Read last L1ID and BCID
        last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
        last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)

        # Check if retry is needed
        retry_needed = False
        if previous_hg_peaks is not None:
            for ch in range(nchanperMD):
                if hg_peaks_step[ch] < previous_hg_peaks[ch] * threshold or \
                   lg_peaks_step[ch] < previous_lg_peaks[ch] * threshold:
                    retry_needed = True
                    break

        if not retry_needed:
            return (hg_peaks_step, lg_peaks_step, hg_centers_step, lg_centers_step,
                    hg_fwhm_step, lg_fwhm_step, hg_pedestal_step, lg_pedestal_step)
        else:
            retry += 1
            # print(f"MD{md} retry {retry}/{max_retries} due to low peak(s)...")
            time.sleep(0.05)

    # If still failing after max_retries, return last readout anyway
    # print(f"MD{md} reached max retries ({max_retries}), returning last readout")
    return (hg_peaks_step, lg_peaks_step, hg_centers_step, lg_centers_step,
            hg_fwhm_step, lg_fwhm_step, hg_pedestal_step, lg_pedestal_step)


        

def cis_test(ppr, feb, ppr_label):
    all_points = []
    dbside = 0  # All FPGAs
    nsamp = 16
    nchanperMD = 12
    nMD = 4
    firstMD = 0
    step_events = 1

    n_events = 1  # number of CIS events per step

    #BCID parameters
    bcid_l1a = 2246
    BCID_charge = 500
    BCID_discharge = 2200
    gain = 0

    min_DAC = 1278# 1650 #1278
    max_DAC = 2261# 2300 #2261
    ADCped = 100

    # CIS DAC charge for test
    DACcharge = 1500

    # ------------------ INITIALIZATION -------------------
    # Allocate arrays for storing CIS data
    step_x = []  # injected step number
    all_hg_data = [[] for _ in range(nchanperMD * nMD)]
    all_lg_data = [[] for _ in range(nchanperMD * nMD)]

    # ------------------ CONFIG PHASE -------------------

    # print("Setting TTC internal... ", end="")
    ppr.set_global_TTC_internal()
    # print("Ok" if ret else "Failed")

    # print("Resetting CRC counters... ", end="")
    # ret = ppr.reset_CRC_counters()
    # print("Ok" if ret else "Failed")

    # print("Reading CRC counters... ")
    initial_crc_sideA = []
    initial_crc_sideB = []
    final_crc_sideA = []
    final_crc_sideB = []

    # print("Initial CRC Counters")
    # print("=" * 40)
    # print(f"{'MD':<6}{'Side A':<15}{'Side B':<15}")
    # print("-" * 40)

    for i in range(firstMD, firstMD + nMD):
        a = ppr.get_CRC_tot_errors(i, side="A")
        b = ppr.get_CRC_tot_errors(i, side="B")

        initial_crc_sideA.append(a)
        initial_crc_sideB.append(b)

    #     print(f"{f'MD{i}':<6}{a:<15}{b:<15}")

    # print("=" * 40)
    # print(f"{'Totals:':<6}{str(initial_crc_sideA):<15}{str(initial_crc_sideB):<15}")

    # print("Setting PPr enable deadtime bit in Global Trigger Conf...")
    # ret = ppr.set_global_trigger_deadtime(0)
    # print(f"  set bit to 0: {'Ok' if ret else 'Fail'}")
    # ret = ppr.set_global_trigger_deadtime(1)
    # print(f"  set bit to 1: {'Ok' if ret else 'Fail'}")



    # ------------------ CIS TEST -------------------

    # print("==> Starting CIS test...")

    # 1) Configure FEB ADC DACs
    DACbiasP, DACbiasN = feb.convert_ped_ADC_to_DACs(ADCped)
    
    # print("Configuring FEB pedestal DACs... ", end="")
    for md in range(firstMD, firstMD + nMD):
        for feb_id in range(nchanperMD):
            feb.set_ped_HG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_HG_neg(md, dbside, feb_id, DACbiasN)
            feb.set_ped_LG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_LG_neg(md, dbside, feb_id, DACbiasN)

            feb.load_ped_HG(md, dbside, feb_id)
            feb.load_ped_LG(md, dbside, feb_id)
    # print("Ok")

    # 2) Set FEB switches
    # print("Setting FEB switches... ", end="")
    for md in range(firstMD, firstMD + nMD):
        for adc in range(nchanperMD):
            ret = feb.set_switches_noise(md, dbside=2, feb=adc)

    # 3) Set CIS BCID parameters
    # print("Setting CIS on minidrawers... ", end="")
    for md in range(firstMD, firstMD + nMD):
        for feb_id in range(nchanperMD):
            feb.set_CIS_BCID_settings(md, dbside, BCID_charge, BCID_discharge, gain)
    # print("Ok")

    # 4) Set FEB CIS DACs
    # print(f"Setting FEB CIS DACs to {DACcharge}... ", end="")
    for md in range(firstMD, firstMD + nMD):
        for feb_id in range(nchanperMD):
            feb.set_CIS_DAC(md, dbside, feb_id, DACcharge)
    # print("Ok")

    # 5) Loop on CIS events

    step_x = [int(i) for i in range(nsamp)]

    for event in range(n_events):
        # Send L1A trigger
        feb.send_L1A(bcid_l1a, 3)
        for md in range(firstMD, firstMD + nMD):
            for adc in range(nchanperMD):
                # Read ADC pipeline data
                hg_data = ppr.get_data_HG(md, adc, nsamp)
                lg_data = ppr.get_data_LG(md, adc, nsamp)

                all_hg_data[md * nchanperMD + adc].extend(hg_data)
                all_lg_data[md * nchanperMD + adc].extend(lg_data)

                # print(f"MD{md} ADC{adc} HG data={hg_data} LG data={lg_data}")

        last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
        last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)

    # ------------------ ASCII PLOTS -------------------
    # print(all_hg_data)

    # print("\nPulse Analysis Results")
    # print("=" * 80)
    # print(f"{'MD':<6}{'Ch':<6}{'HG_Ped':<10}{'HG_Peak':<10}{'HG_PeakIdx':<10}{'HG_Center':<12}{'HG_FWHM':<8}{'LG_Ped':<10}{'LG_Peak':<10}{'LG_PeakIdx':<10}{'LG_Center':<12}{'LG_FWHM':<8}")
    # print("-" * 80)

    for i in range(firstMD, firstMD + nMD):
        a = ppr.get_CRC_tot_errors(i, side="A")
        b = ppr.get_CRC_tot_errors(i, side="B")

        final_crc_sideA.append(a)
        final_crc_sideB.append(b)

    # print("\nFinal CRC Counters")
    # print("=" * 40)
    # print(f"{'MD':<6}{'A_init':<12}{'A_final':<12}{'ΔA':<12}"
    #     f"{'B_init':<12}{'B_final':<12}{'ΔB':<12}")

    all_delta_crc_errors_sideA = []
    all_delta_crc_errors_sideB = []
    for idx, i in enumerate(range(firstMD, firstMD + nMD)):
        a0 = initial_crc_sideA[idx]
        b0 = initial_crc_sideB[idx]
        a1 = final_crc_sideA[idx]
        b1 = final_crc_sideB[idx]

        da = a1 - a0
        db = b1 - b0

        all_delta_crc_errors_sideA.append(da)
        all_delta_crc_errors_sideB.append(db)

        # print(f"{f'MD{i}':<6}"
        #     f"{a0:<12}{a1:<12}{da:<12}"
        #     f"{b0:<12}{b1:<12}{db:<12}")

    
    
    now = datetime.datetime.utcnow().isoformat()
    for md in range(firstMD, firstMD + nMD):
        
        for adc in range(nchanperMD):
            
            idx = md * nchanperMD + adc

            # Pulse analysis
            hg_pedestal, hg_peak, hg_peak_idx, hg_center, hg_width = analyze_pulse(all_hg_data[idx])
            lg_pedestal, lg_peak, lg_peak_idx, lg_center, lg_width = analyze_pulse(all_lg_data[idx])
            
            # Delta CRC
            delta_crc = all_delta_crc_errors_sideA[md] if adc % 2 == 0 else all_delta_crc_errors_sideB[md]

            
            # ---------------------- Add CIS summary ----------------------
            all_points.append({
                "measurement": "CIS",
                "tags": {
                    f"{ppr_label} MD{md+1}": f"CH{adc}",
                },
                "time": now,
                "fields": {
                    "hg_pedestal": float(hg_pedestal),
                    "hg_peak": float(hg_peak),
                    "hg_peak_idx": float(hg_peak_idx),
                    "hg_center": float(hg_center),
                    "hg_width": float(hg_width),
                    "lg_pedestal": float(lg_pedestal),
                    "lg_peak": float(lg_peak),
                    "lg_peak_idx": float(lg_peak_idx),
                    "lg_center": float(lg_center),
                    "lg_width": float(lg_width),
                    "delta_crc": float(delta_crc)
                }
            })



            # ---------------------- Add CIS samples for Grafana ----------------------
            for i, (hg, lg) in enumerate(zip(all_hg_data[idx], all_lg_data[idx])):
                event = i // nsamp
                sample = i % nsamp

                # HG sample
                all_points.append({
                    "measurement": "CIS_Samples",
                    "tags": {
                        "channel": f"{ppr_label}_MD{md+1}_CH{adc}",
                        "gain": "HG",
                        "event": str(event),
                        "sample": sample
                    },
                    "time": now,
                    "fields": {
                        "value": float(hg)
                    }
                })

                # LG sample
                all_points.append({
                    "measurement": "CIS_Samples",
                    "tags": {
                        "channel": f"{ppr_label}_MD{md+1}_CH{adc}",
                        "gain": "LG",
                        "event": str(event),
                        "sample": sample
                    },
                    "time": now,
                    "fields": {
                        "value": float(lg)
                    }
                })

            # ---------------------- Add CIS samples for Grafana ----------------------
            # for i, (hg, lg) in enumerate(zip(all_hg_data[idx], all_lg_data[idx])):
            #     event = i // nsamp
            #     sample = i % nsamp

            #     all_points.append({
            #         "measurement": "CIS_Samples",
            #         "tags": {
            #             f"{ppr_label} MD{md+1}": f"HG_{event}_CH{adc}"
            #         },
            #         "time": now,
            #         "fields": {
            #             f"Sample_{sample}": float(hg)
            #         }
            #     })

            #     # LG sample as separate point
            #     all_points.append({
            #         "measurement": "CIS_Samples",
            #         "tags": {
            #             f"{ppr_label} MD{md+1}": f"LG_{event}_CH{adc}"
            #         },
            #         "time": now,
            #         "fields": {
            #             f"Sample_{sample}": float(lg)
            #         }
            #     })


        # print(f"{md:<6}{adc:<6}{hg_pedestal:<10}{hg_peak:<10}{hg_peak_idx:<10}{hg_center:<12.2f}{hg_width:<8}{lg_pedestal:<10}{lg_peak:<10}{lg_peak_idx:<10}{lg_center:<12.2f}{lg_width:<8}")




    return all_points


def cis_lin_readout(ppr, feb, ppr_label, gain=0):
    all_points = []
    
    nsamp = 16
    nchanperMD = 12
    nMD = 4
    firstMD = 0
    dbside = 0

    n_events = 1

    bcid_l1a = 2246
    BCID_charge = 500
    BCID_discharge = 2200

    ADCped = 100

    nsteps = 40
    max_DAC_charge = 4095
    min_DAC_charge = 0
    step_length_DAC = (max_DAC_charge - min_DAC_charge) / (nsteps - 1)

    step_x = []

    all_hg_peaks = []
    all_lg_peaks = []
    all_hg_centers = []
    all_lg_centers = []
    all_hg_fwhm = []
    all_lg_fwhm = []
    all_hg_pedestal = []
    all_lg_pedestal = []


    # print("Reading CRC counters... ")
    initial_crc_sideA = []
    initial_crc_sideB = []
    final_crc_sideA = []
    final_crc_sideB = []

    # print("Initial CRC Counters")
    # print("=" * 40)
    # print(f"{'MD':<6}{'Side A':<15}{'Side B':<15}")
    # print("-" * 40)

    for i in range(firstMD, firstMD + nMD):
        a = ppr.get_CRC_tot_errors(i, side="A")
        b = ppr.get_CRC_tot_errors(i, side="B")

        initial_crc_sideA.append(a)
        initial_crc_sideB.append(b)


    # ------------------ CONFIG PHASE -------------------

    ppr.set_global_TTC_internal()
    DACbiasP, DACbiasN = feb.convert_ped_ADC_to_DACs(ADCped)

    for md in range(firstMD, firstMD + nMD):
        for feb_id in range(nchanperMD):
            feb.set_ped_HG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_HG_neg(md, dbside, feb_id, DACbiasN)
            feb.set_ped_LG_pos(md, dbside, feb_id, DACbiasP)
            feb.set_ped_LG_neg(md, dbside, feb_id, DACbiasN)
            feb.load_ped_HG(md, dbside, feb_id)
            feb.load_ped_LG(md, dbside, feb_id)

    for md in range(firstMD, firstMD + nMD):
        for adc in range(nchanperMD):
            feb.set_switches_noise(md, dbside, feb=adc)

    for md in range(firstMD, firstMD + nMD):
        feb.set_CIS_BCID_settings(md, dbside, BCID_charge, BCID_discharge, gain)


    # ------------------ DACcharge SWEEP -------------------

    # print("\n==> Starting DACcharge sweep")

    for step in range(nsteps):

        DACcharge = int(min_DAC_charge + step * step_length_DAC)
        step_x.append(DACcharge)

        # print(f"Step {step+1}/{nsteps}  DACcharge = {DACcharge}")

        for md in range(firstMD, firstMD + nMD):
            for feb_id in range(nchanperMD):
                feb.set_CIS_DAC(md, dbside, feb_id, DACcharge)

        time.sleep(0.05)

        hg_peaks_step = []
        lg_peaks_step = []
        hg_centers_step = []
        lg_centers_step = []
        hg_fwhm_step = []
        lg_fwhm_step = []
        hg_pedestal_step = []
        lg_pedestal_step = []

        for event in range(n_events):
            feb.send_L1A(bcid_l1a, 3)
            time.sleep(0.05)

            for md in range(firstMD, firstMD + nMD):
                previous_hg = all_hg_peaks[-1][md*nchanperMD:(md+1)*nchanperMD] if step>0 else None
                previous_lg = all_lg_peaks[-1][md*nchanperMD:(md+1)*nchanperMD] if step>0 else None

                hg_peaks_step_md, lg_peaks_step_md, hg_centers_step_md, lg_centers_step_md, \
                hg_fwhm_step_md, lg_fwhm_step_md, hg_pedestal_step_md, lg_pedestal_step_md = \
                    read_md_data_with_retry(ppr, feb, md, nsamp, nchanperMD, bcid_l1a,
                                            previous_hg_peaks=previous_hg,
                                            previous_lg_peaks=previous_lg,
                                            threshold=0.9, max_retries=0)

                # Append MD data
                hg_peaks_step.extend(hg_peaks_step_md)
                lg_peaks_step.extend(lg_peaks_step_md)
                hg_centers_step.extend(hg_centers_step_md)
                lg_centers_step.extend(lg_centers_step_md)
                hg_fwhm_step.extend(hg_fwhm_step_md)
                lg_fwhm_step.extend(lg_fwhm_step_md)
                hg_pedestal_step.extend(hg_pedestal_step_md)
                lg_pedestal_step.extend(lg_pedestal_step_md)


            last_L1ID = ppr.read(PPrReg.LAST_EVT_L1ID)
            last_BCID = ppr.read(PPrReg.LAST_EVT_BCID)

        all_hg_peaks.append(hg_peaks_step)
        all_lg_peaks.append(lg_peaks_step)
        all_hg_centers.append(hg_centers_step)
        all_lg_centers.append(lg_centers_step)
        all_hg_fwhm.append(hg_fwhm_step)
        all_lg_fwhm.append(lg_fwhm_step)
        all_hg_pedestal.append(hg_pedestal_step)
        all_lg_pedestal.append(lg_pedestal_step)
    
    
    for i in range(firstMD, firstMD + nMD):
        a = ppr.get_CRC_tot_errors(i, side="A")
        b = ppr.get_CRC_tot_errors(i, side="B")

        final_crc_sideA.append(a)
        final_crc_sideB.append(b)

    # print("\nFinal CRC Counters")
    # print("=" * 40)
    # print(f"{'MD':<6}{'A_init':<12}{'A_final':<12}{'ΔA':<12}"
    #     f"{'B_init':<12}{'B_final':<12}{'ΔB':<12}")

    all_delta_crc_errors_sideA = []
    all_delta_crc_errors_sideB = []
    for idx, i in enumerate(range(firstMD, firstMD + nMD)):
        a0 = initial_crc_sideA[idx]
        b0 = initial_crc_sideB[idx]
        a1 = final_crc_sideA[idx]
        b1 = final_crc_sideB[idx]

        da = a1 - a0
        db = b1 - b0

        all_delta_crc_errors_sideA.append(da)
        all_delta_crc_errors_sideB.append(db)

        # print(f"{f'MD{i}':<6}"
        #     f"{a0:<12}{a1:<12}{da:<12}"
        #     f"{b0:<12}{b1:<12}{db:<12}")
    
    now = datetime.datetime.utcnow().isoformat()
    
    for md in range(firstMD, firstMD + nMD):
        # print(f"\n==> MD{md} summary")

        step_hg_peaks = np.array([all_hg_peaks[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_hg_peaks))])
        step_lg_peaks = np.array([all_lg_peaks[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_lg_peaks))])
        
        step_hg_centers = np.array([all_hg_centers[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_hg_centers))])
        step_lg_centers = np.array([all_lg_centers[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_lg_centers))])
        
        step_hg_fwhm = np.array([all_hg_fwhm[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_hg_fwhm))])
        step_lg_fwhm = np.array([all_lg_fwhm[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_lg_fwhm))])
        
        step_hg_pedestal = np.array([all_hg_pedestal[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_hg_pedestal))])
        step_lg_pedestal = np.array([all_lg_pedestal[s][md * nchanperMD:(md + 1) * nchanperMD] for s in range(len(all_lg_pedestal))])

    
        for ch in range(nchanperMD):
            # linear fit HG
            hg_slope, hg_intercept, hg_r2, hg_max_dev = linear_fit(step_x, step_hg_peaks[:, ch])
            # linear fit LG
            lg_slope, lg_intercept, lg_r2, lg_max_dev = linear_fit(step_x, step_lg_peaks[:, ch])
            # averages and stds
            hg_center_mean, hg_center_std = avg_std(step_hg_centers[:, ch])
            lg_center_mean, lg_center_std = avg_std(step_lg_centers[:, ch])
            hg_fwhm_mean, hg_fwhm_std = avg_std(step_hg_fwhm[:, ch])
            lg_fwhm_mean, lg_fwhm_std = avg_std(step_lg_fwhm[:, ch])
            hg_ped_mean, hg_ped_std = avg_std(step_hg_pedestal[:, ch])
            lg_ped_mean, lg_ped_std = avg_std(step_lg_pedestal[:, ch])
        
            delta_crc=-1
            if ch % 2 == 0:
                delta_crc = all_delta_crc_errors_sideA[md]
            else:
                delta_crc = all_delta_crc_errors_sideB[md]
        
            if gain == 1:
                for step_i, dac in enumerate(step_x):

                    hg_val = step_hg_peaks[step_i, ch]
                    # lg_val = step_lg_peaks[step_i, ch]

                    all_points.append({
                        "measurement": "CIS_Linearity_Samples",
                        "tags": {
                            "channel": f"{ppr_label}_MD{md+1}_CH{ch}",
                            "gain": "HG",
                            "step": step_i
                        },
                        "time": now,
                        "fields": {
                            "dac_charge": float(dac),
                            "value": float(hg_val)
                        }
                    })

                    
                all_points.append({
                        "measurement": "CIS_Linearity",
                        "tags": {
                            f"{ppr_label} MD{md+1}": f"CH{ch}",
                        },
                        "time": datetime.datetime.utcnow().isoformat(),
                        "fields": {
                            "hg_slope": float(hg_slope),
                            "hg_intercept": float(hg_intercept),
                            "hg_r2": float(hg_r2),
                            "hg_max_dev": float(hg_max_dev),
                            "hg_center_mean": float(hg_center_mean),
                            "hg_center_std": float(hg_center_std),
                            "hg_fwhm_mean": float(hg_fwhm_mean),
                            "hg_fwhm_std": float(hg_fwhm_std),
                            "hg_ped_mean": float(hg_ped_mean),
                            "hg_ped_std": float(hg_ped_std),
                            "delta_crc": float(delta_crc)

                        }
                    })
            else:
                
                
                for step_i, dac in enumerate(step_x):
                    # hg_val = step_hg_peaks[step_i, ch]
                    lg_val = step_lg_peaks[step_i, ch]    
                    
                    all_points.append({
                        "measurement": "CIS_Linearity_Samples",
                        "tags": {
                            "channel": f"{ppr_label}_MD{md+1}_CH{ch}",
                            "gain": "LG",
                            "step": step_i
                        },
                        "time": now,
                        "fields": {
                            "dac_charge": float(dac),
                            "value": float(lg_val)
                        }
                    })
                                    
                all_points.append({
                        "measurement": "CIS_Linearity",
                        "tags": {
                            f"{ppr_label} MD{md+1}": f"CH{ch}",
                        },
                        "time": datetime.datetime.utcnow().isoformat(),
                        "fields": {
                            "lg_slope": float(lg_slope),
                            "lg_intercept": float(lg_intercept),
                            "lg_r2": float(lg_r2),
                            "lg_max_dev": float(lg_max_dev),
                            "lg_center_mean": float(lg_center_mean),
                            "lg_center_std": float(lg_center_std),
                            "lg_fwhm_mean": float(lg_fwhm_mean),
                            "lg_fwhm_std": float(lg_fwhm_std),
                            "lg_ped_mean": float(lg_ped_mean),
                            "lg_ped_std": float(lg_ped_std),
                            "delta_crc": float(delta_crc)

                        }
                    })
    
    return all_points


def integrator_lin_test(ppr, feb, ppr_label, nsteps=20, step_events=1):
    all_points = []

    nsamp = 1  # integrator readout returns 1 value
    nchanperMD = 12
    nMD = 4
    firstMD = 0
    dbside = 0

    min_DAC = 0
    max_DAC = 4095
    step_length = (max_DAC - min_DAC) / (nsteps - 1)

    step_x = []

    # Store values: list of steps → flat channel array
    all_values = []

    # ------------------ CONFIG PHASE -------------------

    ppr.set_global_TTC_internal()

    ppr.set_global_trigger_deadtime(0)
    ppr.set_global_trigger_deadtime(1)

    feb.set_FEB_ADC_bias_offsets_DACs()
    feb.set_FEB_load_ADC_DACs()
    feb.set_FEB_switches()

    feb.set_CIS_Integrator_BCID_settings()

    # integrator readout frequency
    readout_frequency = 112
    feb.async_write(None, 0x115, readout_frequency)

    # internal TTC mode
    ppr.write(0x4, 0)

    feb.set_integrator_switches()

    # Initialize DAC = 0
    feb.set_FEB_integrator_DACs(charge=0)
    ppr.reset_integrator_fifo()
    time.sleep(0.2)

    # ------------------ DAC SWEEP -------------------

    for step in range(nsteps):

        DACcharge = int(min_DAC + step * step_length)
        step_x.append(DACcharge)

        feb.set_FEB_integrator_DACs(charge=DACcharge)
        ppr.reset_integrator_fifo()
        time.sleep(0.1)

        step_values = []

        for md in range(firstMD, firstMD + nMD):
            for adc in range(nchanperMD):

                vals = []
                for event in range(step_events):
                    data = ppr.get_data_integrator(md, adc, nsamp)
                    if data:
                        vals.append(max(data))

                avg_val = sum(vals) / len(vals) if vals else 0
                step_values.append(avg_val)

        all_values.append(step_values)

    # Convert to numpy-like structure
    all_values = np.array(all_values)  # shape: (steps, channels)

    now = datetime.datetime.utcnow().isoformat()

    # ------------------ ANALYSIS -------------------

    for md in range(firstMD, firstMD + nMD):

        for ch in range(nchanperMD):

            idx = md * nchanperMD + ch
            y = all_values[:, idx]

            slope, intercept, r2, maxdev = linear_fit(step_x, y)
            mean_val, std_val = avg_std(y)

            # -------- Summary --------
            all_points.append({
                "measurement": "Integrator_Linearity",
                "tags": {
                    f"{ppr_label} MD{md+1}": f"CH{ch}",
                },
                "time": now,
                "fields": {
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r2": float(r2),
                    "maxdev": float(maxdev),
                    "mean": float(mean_val),
                    "std": float(std_val)
                }
            })

            # -------- Samples --------
            for step_i, dac in enumerate(step_x):
                all_points.append({
                    "measurement": "Integrator_Linearity_Samples",
                    "tags": {
                        "channel": f"{ppr_label}_MD{md+1}_CH{ch}",
                        "step": step_i
                    },
                    "time": now,
                    "fields": {
                        "dac_charge": float(dac),
                        "value": float(all_values[step_i, idx])
                    }
                })

    return all_points


def compute_metrics(data, threshold=1e-6):
    """
    Compute comprehensive eye diagram metrics with proper handling
    of all-zero or bad data. Returns worst-case values if eye is flat.
    Also adds calibrated (_cal) timing metrics in ps.
    """

    # ---------------------------
    # CALIBRATION CONSTANTS
    # ---------------------------
    DATA_RATE = 9.6e9
    UI_PS = 1e12 / DATA_RATE              # ≈104.17 ps
    EFFECTIVE_BINS = 128 / 4              # due to n=4 duplication
    TIME_PER_BIN_PS = UI_PS / EFFECTIVE_BINS   # ≈3.255 ps

    # Handle all-zero data
    if np.all(data == 0):
        return {
            'open_area': 0.0,
            'max_h_open': 0,
            'max_v_open': 0,
            'eye_height': 0.0,
            'rms_jitter': 0.0,
            'peak_to_peak_jitter': 0.0,
            'q_factor': 0.0,
            'snr': 0.0,
            'crossing_point': 0.5,
            'ber': 1.0,

            # ---- calibrated ----
            'rms_jitter_cal': 0.0,
            'peak_to_peak_jitter_cal': 0.0,
            'max_h_open_cal': 0.0,
            'crossing_point_cal': 0.5 * UI_PS
        }

    v, h = data.shape
    max_val = data.max()
    min_val = data.min()
    thr = threshold if threshold > 0 else max_val * 0.01

    # ---------------------------
    # Eye open area
    # ---------------------------
    mask = data >= thr
    open_area = np.sum(mask) / (v * h)

    max_h_open = max(
        (sum(1 for _ in g) for row in mask for k, g in groupby(row) if k),
        default=0
    )

    max_v_open = max(
        (sum(1 for _ in g) for col in mask.T for k, g in groupby(col) if k),
        default=0
    )

    eye_height = max_val - min_val

    # ---------------------------
    # Crossing point & jitter
    # ---------------------------
    mid_val = (max_val + min_val) / 2
    crossing_positions = []

    for row in data:
        for i in range(1, len(row)):
            if (row[i-1] < mid_val <= row[i]) or (row[i-1] >= mid_val > row[i]):
                crossing_positions.append(i)

    if crossing_positions:
        rms_jitter = np.std(crossing_positions)
        peak_to_peak_jitter = np.max(crossing_positions) - np.min(crossing_positions)
        crossing_point = np.mean(crossing_positions) / h
    else:
        rms_jitter = 0.0
        peak_to_peak_jitter = 0.0
        crossing_point = 0.5

    # ---------------------------
    # Q-factor & SNR
    # ---------------------------
    ones = data > mid_val
    zeros = data <= mid_val

    mu1, sigma1 = (data[ones].mean(), data[ones].std()) if np.any(ones) else (0, 1)
    mu0, sigma0 = (data[zeros].mean(), data[zeros].std()) if np.any(zeros) else (0, 1)

    q_factor = (mu1 - mu0) / (sigma1 + sigma0) if (sigma1 + sigma0) > 0 else 0
    snr = eye_height / (np.std(data) or 1)
    ber_estimate = 0.5 * erfc(q_factor / np.sqrt(2)) if q_factor > 0 else 1.0

    # ---------------------------
    # CALIBRATED METRICS (ps)
    # ---------------------------
    rms_jitter_cal = rms_jitter * TIME_PER_BIN_PS
    peak_to_peak_jitter_cal = peak_to_peak_jitter * TIME_PER_BIN_PS
    max_h_open_cal = max_h_open * TIME_PER_BIN_PS
    crossing_point_cal = crossing_point * UI_PS

    return {
        'open_area': open_area,
        'max_h_open': max_h_open,
        'max_v_open': max_v_open,
        'eye_height': eye_height,
        'rms_jitter': rms_jitter,
        'peak_to_peak_jitter': peak_to_peak_jitter,
        'q_factor': q_factor,
        'snr': snr,
        'crossing_point': crossing_point,
        'ber': ber_estimate,

        # ---- calibrated additions ----
        'rms_jitter_cal': rms_jitter_cal,
        'peak_to_peak_jitter_cal': peak_to_peak_jitter_cal,
        'max_h_open_cal': max_h_open_cal,
        'crossing_point_cal': crossing_point_cal
    }



def eye_diagram_test(ppr, ppr_label, threshold=1e-6, verbose=False):
    all_points = []

    md_labels = ["1", "2", "3", "4", "1", "2", "3", "4", "1", "2", "3", "4", "1", "2", "3", "4"]
    uplink_labels = ["A0", "A0", "A0", "A0", "A1", "A1", "A1", "A1", "B0", "B0", "B0", "B0", "B1", "B1", "B1", "B1"]
    

    # ------------------ ACQUISITION ------------------
    eye_data = ppr.read_eye(verbose=verbose)
    now = datetime.datetime.utcnow().isoformat()

    # Convert to numpy for easier handling
    eye_data = np.array(eye_data)  # shape: (16 lanes, v, h)

    nlanes = len(eye_data)

    # ------------------ ANALYSIS ------------------
    for l in range(nlanes):

        data = np.array(eye_data[l])

        metrics = compute_metrics(data, threshold=threshold)

        # -------- Summary --------
        all_points.append({
            "measurement": "Link_Eye_Diagram",
            "tags": {f"{ppr_label} MD{md_labels[l]}": f"uplink {uplink_labels[l]}"},
            "time": now,
            "fields": {k: float(v) for k, v in metrics.items()}
        })

        # -------- Samples (optional, can be large!) --------
        v, h = data.shape
        for vv in range(v):
            for hh in range(h):
                all_points.append({
                    "measurement": "Link_Eye_Diagram_Samples",
                    "tags": {f"{ppr_label} MD{md_labels[l]}": f"uplink {uplink_labels[l]}",
                        "v": vv,
                        "h": hh
                    },
                    "time": now,
                    "fields": {
                        "value": float(data[vv, hh])
                    }
                })

    return all_points
import Herakles
import time
import random

# db declarations
from db_lib import *



import math
from typing import List


# ============================================================
# Utility Bit Tools (Java ByteTools replacement)
# ============================================================

class BitTools:

    @staticmethod
    def set_bit(bit: int, value: int, word: int) -> int:
        if value:
            return word | (1 << bit)
        else:
            return word & ~(1 << bit)

    @staticmethod
    def set_bits(start: int, end: int, value: int, word: int) -> int:
        mask = ((1 << (end - start + 1)) - 1) << start
        word &= ~mask
        word |= (value << start) & mask
        return word

    @staticmethod
    def get_bit(bit: int, value: int) -> int:
        return (value >> bit) & 0x1





# ============================================================
# PPrReg (FULL Java port)
# ============================================================

class PPrReg:
    RO_DUMMY = 0x0
    RO_FIRMWARE_VERSION = 0x1
    RO_GLOBAL = 0x2
    RO_GLOBAL_PIPELINE = 0x3
    RO_GLOBAL_TTC = 0x4
    RO_GLOBAL_TRIGGER = 0x5
    RO_SYNC_CMD = 0x6
    RO_RESET_CRC_CNTS = 0x20

    RO_GLOBAL_TTC_INT_MASK = 0x400000
    RO_GLOBAL_TTC_INT_OFFSET = 22
    RO_GLOBAL_TTC_MASK = 0xFFBFFFFF

    CMD_COUNTER = 0x00000007
    ASYNC_CMD_COUNTER = 0x00000008
    SYNC_CMD_COUNTER = 0x00000009
    L1A_COUNTER = 0x0000000A
    EVTS_OUT_COUNTER = 0x0000000B

    LINKS_CTRL_GLB_RESETS = 0x0000000F
    GBT_LINKS_RESETS = 0x0000000E

    SYNC_ADDRESS = 0x00010000
    SYNC_COMMAND = 0x00010001
    SYNC_ADDRESS_MD_MASK = 0x70000000

    ASYNC_ADDRESS = 0x00010002
    ASYNC_COMMAND = 0x00010003
    ASYNC_ADDRESS_MD_MASK = 0x70000000

    SYNC_PPR_ADDRESS = 0x00010004
    SYNC_PPR_COMMAND = 0x00010005

    LAST_EVT_BCID = 0x0000009D
    LAST_EVT_L1ID = 0x0000009E

    PIPELINE_HG = 0x00000100
    PIPELINE_LG = 0x00000700
    INTEGRATOR_SLOW_READOUT = 0x00020130
    INTEGRATOR_FIFO = 0x00000083

    CRC_FRAMES1_MD1 = 0x00000021
    CRC_FRAMES2_MD1 = 0x00000022
    CRC_FRAMES1_MD2 = 0x00000029
    CRC_FRAMES2_MD2 = 0x0000002A
    CRC_FRAMES1_MD3 = 0x00000031
    CRC_FRAMES2_MD3 = 0x00000032
    CRC_FRAMES1_MD4 = 0x00000039
    CRC_FRAMES2_MD4 = 0x0000003A

    LINK_STAT_MD1A = 0x00000010
    LINK_STAT_MD1B = 0x00000011
    LINK_STAT_MD2A = 0x00000012
    LINK_STAT_MD2B = 0x00000013
    LINK_STAT_MD3A = 0x00000014
    LINK_STAT_MD3B = 0x00000015
    LINK_STAT_MD4A = 0x00000016
    LINK_STAT_MD4B = 0x00000017

    CRC_ERR_LINK_A0_MD1 = 0x00000023
    CRC_ERR_LINK_A1_MD1 = 0x00000024
    CRC_ERR_LINK_B0_MD1 = 0x00000025
    CRC_ERR_LINK_B1_MD1 = 0x00000026
    CRC_ERR_TOT_SIDE_A_MD1 = 0x00000027
    CRC_ERR_TOT_SIDE_B_MD1 = 0x00000028

    CRC_ERR_LINK_A0_MD2 = 0x0000002B
    CRC_ERR_LINK_A1_MD2 = 0x0000002C
    CRC_ERR_LINK_B0_MD2 = 0x0000002D
    CRC_ERR_LINK_B1_MD2 = 0x0000002E
    CRC_ERR_TOT_SIDE_A_MD2 = 0x0000002F
    CRC_ERR_TOT_SIDE_B_MD2 = 0x00000030

    CRC_ERR_LINK_A0_MD3 = 0x00000033
    CRC_ERR_LINK_A1_MD3 = 0x00000034
    CRC_ERR_LINK_B0_MD3 = 0x00000035
    CRC_ERR_LINK_B1_MD3 = 0x00000036
    CRC_ERR_TOT_SIDE_A_MD3 = 0x00000037
    CRC_ERR_TOT_SIDE_B_MD3 = 0x00000038

    CRC_ERR_LINK_A0_MD4 = 0x0000003B
    CRC_ERR_LINK_A1_MD4 = 0x0000003C
    CRC_ERR_LINK_B0_MD4 = 0x0000003D
    CRC_ERR_LINK_B1_MD4 = 0x0000003E
    CRC_ERR_TOT_SIDE_A_MD4 = 0x0000003F
    CRC_ERR_TOT_SIDE_B_MD4 = 0x00000040

    RAM_MEM_HG = 0x00000100
    RAM_MEM_LG = 0x00000700

    PPR_FEB_CTRL_REG = [0x00010011, 0x00110011, 0x00210011, 0x00310011]
    PPR_FEB_DATA_REG = [0x00010012, 0x00110012, 0x00210012, 0x00310012]

    PPR_FEB_SWITCHES = [0x7, 0x10, 0x19, 0x22, 0x2B, 0x34]
    PPR_FEB_CIS_DAC = [0x8, 0x11, 0x1A, 0x23, 0x2C, 0x35]
    PPR_FEB_PED_HG_POS = [0x9, 0x12, 0x1B, 0x24, 0x2D, 0x36]
    PPR_FEB_PED_HG_NEG = [0xA, 0x13, 0x1C, 0x25, 0x2E, 0x37]
    PPR_FEB_PED_LG_POS = [0xB, 0x14, 0x1D, 0x26, 0x2F, 0x38]
    PPR_FEB_PED_LG_NEG = [0xC, 0x15, 0x1E, 0x27, 0x30, 0x39]

    PPR_DB_XADC = [0x9, 0x12, 0x21, 0x24, 0x2D, 0x36]

    LAT_MD1_MD2 = 0x00000085
    LAT_MD3_MD4 = 0x00000086
    
    EYE_CONTROL = 0x40007
    EYE_STATUS  = 0x40009
    EYE_CONFIG  = 0x40008
    EYE_READ    = 0x4000A

# ============================================================
# DBReg
# ============================================================

class DBReg:
    DB_FEB_COMMAND = 0x001
    DB_VERSION = 0x011
    DB_CONF_REG1 = 0x012
    DB_CONF_REG2 = 0x013
    DB_CONF_REG3_LINK_RESETS = 0x014
    DB_CONF_REG4_TEMP = 0x015
    DB_CONF_REG5_SOFT_ERR = 0x016
    DB_CONF_REG6 = 0x017
    DB_XADC_REG1 = 0x0E0
    DB_CIS = 0x121

    FPGA = [1, 3, 1, 3, 1, 3, 0, 2, 0, 2, 0, 2]
    FPGA_CHANNEL = [2, 2, 1, 1, 0, 0, 2, 2, 1, 1, 0, 0]
    ADC_MAP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    CMD_BIT_E_MASK = 0x400000
    CMD_BIT_E_OFFSET = 22
    CMD_BIT_B_MASK = 0x200000
    CMD_BIT_B_OFFSET = 21
    CMD_FPGA_MASK = 0x1C0000
    CMD_FPGA_OFFSET = 18
    CMD_FPGA_CHANNEL_MASK = 0x030000
    CMD_FPGA_CARD_OFFSET = 16
    CMD_MASK = 0xF000
    CMD_OFFSET = 12
    CMD_DATA_MASK = 0xFFF

    CMD_SET_SWITCHES = 0
    CMD_SET_CIS_DAC = 1
    CMD_GET_SWITCHES = 2
    CMD_GET_CIS_DAC = 3
    CMD_SET_PED_LG_POS = 4
    CMD_SET_PED_LG_NEG = 5
    CMD_SET_PED_HG_POS = 6
    CMD_SET_PED_HG_NEG = 7
    CMD_GET_PED_LG_POS = 8
    CMD_GET_PED_LG_NEG = 9
    CMD_GET_PED_HG_POS = 10
    CMD_GET_PED_HG_NEG = 11
    CMD_LOAD_ADC_DAC_HG = 12
    CMD_LOAD_ADC_DAC_LG = 13




class PPr:

    def __init__(self, ipbus):
        self.ipbus = ipbus

    # -------------------------------------------------
    # Basic Read/Write
    # -------------------------------------------------

    def read(self, addr, size=None, fifo=False):
        if size:
            if fifo:
                return self.ipbus.ReadFIFO(addr, size,fifo)
            else:
                return self.ipbus.Read(addr, size)
        return self.ipbus.Read(addr, 1)


    def write(self, addr, *values):
        if len(values) == 1:
            self.ipbus.Write(addr, values[0])
        else:
            self.ipbus.Write(addr, list(values))
        return True

    # -------------------------------------------------
    # Firmware
    # -------------------------------------------------

    def get_firmware_version(self):
        return self.read(PPrReg.RO_FIRMWARE_VERSION)

    # -------------------------------------------------
    # Global TTC
    # -------------------------------------------------

    def get_global_TTC(self):
        return self.read(PPrReg.RO_GLOBAL_TTC)

    def set_global_TTC(self, val):
        self.write(PPrReg.RO_GLOBAL_TTC, val)
        if self.get_global_TTC() != val:
            print(f"Warning: Global TTC readback mismatch! Wrote 0x{val:08X}, read back 0x{self.get_global_TTC():08X}")
            return False
        return True

    def set_global_TTC_internal(self):
        val = PPrReg.RO_GLOBAL_TTC_MASK & self.read(PPrReg.RO_GLOBAL_TTC)
        if val == -1:
            return False
        else:
            self.write(PPrReg.RO_GLOBAL_TTC, val)
            # print(f"Set Global TTC to internal. New value: 0x{val:08X}")
        return True

    def get_global_TTC_internal(self):
        val = self.get_global_TTC()
        return BitTools.get_bit(22, val)

    def get_global_TTC_enable_maxBCID(self):
        val = self.get_global_TTC()
        return BitTools.get_bit(26, val)

    def get_counter_last_event_BCID(self):
        return self.read(PPrReg.LAST_EVT_BCID) & 0xFFF

    def get_counter_last_event_L1ID(self):
        return self.read(PPrReg.LAST_EVT_L1ID) & 0xFFF

    # -------------------------------------------------
    # Global Trigger
    # -------------------------------------------------

    def get_global_trigger(self):
        return self.read(PPrReg.RO_GLOBAL_TRIGGER)

    def set_global_trigger(self, val):
        return self.write(PPrReg.RO_GLOBAL_TRIGGER, val)

    def get_global_trigger_rate_orbits(self):
        val = self.get_global_trigger()
        return (val >> 25) & 0x7F

    def get_global_trigger_L1A_delay(self):
        val = self.get_global_trigger()
        return (val >> 4) & 0x1FF

    def set_global_trigger_deadtime(self, setbit):
        val = self.read(PPrReg.RO_GLOBAL_TRIGGER)
        if val == -1:
            return False
        else:
            val = BitTools.set_bit(3, setbit, val)
            self.write(PPrReg.RO_GLOBAL_TRIGGER, val)
            if self.get_global_trigger() != val:
                print(f"Warning: Global Trigger readback mismatch! Wrote 0x{val:08X}, read back 0x{self.get_global_trigger():08X}")
                return False
            return True 

    # -------------------------------------------------
    # Links
    # -------------------------------------------------

    def get_frames(self, md):
        frame1 = self.read(PPrReg.CRC_FRAMES1[md])
        frame2 = self.read(PPrReg.CRC_FRAMES2[md])
        return (frame2 << 32) | (frame1 & 0xFFFFFFFF)

    def reset_CRC_counters(self):
        self.write(PPrReg.RO_RESET_CRC_CNTS, 0)
        # print("PPr.ppr_reset_CRC_counters() -> IPbus write transaction error")

        self.write(PPrReg.RO_RESET_CRC_CNTS, 1)
        # print("PPr.ppr_reset_CRC_counters() -> IPbus write transaction error")

        self.write(PPrReg.RO_RESET_CRC_CNTS, 0)
        print("PPr.ppr_reset_CRC_counters() -> IPbus write transaction error")
        return True 

    def get_links_status_bits(self, word, link):
        values = []

        if link < 0 | link > 1:
            return None

        if link == 1:
            word = (word & 0xFFFF0000) >> 16

        values.append(word & 0x1)
        values.append((word & 0x2) >> 1)
        values.append((word & 0x4) >> 2)
        values.append((word & 0x8) >> 3)
        values.append((word & 0x3F0) >> 4)
        values.append((word & 0x400) >> 10)
        values.append((word & 0x800) >> 11)
        values.append((word & 0x1000) >> 12)

        return values



    def get_GBT_links_resets(self):
        return self.read(PPrReg.GBT_LINKS_RESETS)

    def set_GBT_links_resets(self, val):
        return self.write(PPrReg.GBT_LINKS_RESETS, val)

    def get_CRC_errors(self, md, link):
        if md < 0 | md > 3 | (link not in ["A0", "A1", "B0", "B1"]):
            return None

        if md == 0:
            if link == "A0":
                return self.read(PPrReg.CRC_ERR_LINK_A0_MD1)
            if link == "A1":
                return self.read(PPrReg.CRC_ERR_LINK_A1_MD1)
            if link == "B0":
                return self.read(PPrReg.CRC_ERR_LINK_B0_MD1)
            if link == "B1":
                return self.read(PPrReg.CRC_ERR_LINK_B1_MD1)

        if md == 1:
            if link == "A0":
                return self.read(PPrReg.CRC_ERR_LINK_A0_MD2)
            if link == "A1":
                return self.read(PPrReg.CRC_ERR_LINK_A1_MD2)
            if link == "B0":
                return self.read(PPrReg.CRC_ERR_LINK_B0_MD2)
            if link == "B1":
                return self.read(PPrReg.CRC_ERR_LINK_B1_MD2)

        if md == 2:
            if link == "A0":
                return self.read(PPrReg.CRC_ERR_LINK_A0_MD3)
            if link == "A1":
                return self.read(PPrReg.CRC_ERR_LINK_A1_MD3)
            if link == "B0":
                return self.read(PPrReg.CRC_ERR_LINK_B0_MD3)
            if link == "B1":
                return self.read(PPrReg.CRC_ERR_LINK_B1_MD3)


        if md == 3:
            if link == "A0":
                return self.read(PPrReg.CRC_ERR_LINK_A0_MD4)
            if link == "A1":
                return self.read(PPrReg.CRC_ERR_LINK_A1_MD4)
            if link == "B0":
                return self.read(PPrReg.CRC_ERR_LINK_B0_MD4)
            if link == "B1":
                return self.read(PPrReg.CRC_ERR_LINK_B1_MD4)

        return None

    def get_CRC_tot_errors(self, md, side):
        if md < 0 | md > 3 | (side not in ["A", "B"]):
            return None

        if md == 0:
            if side == "A":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_A_MD1)
            if side == "B":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_B_MD1)


        if md == 1:
            if side == "A":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_A_MD2)
            if side == "B":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_B_MD2)

        if md == 2:
            if side == "A":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_A_MD3)
            if side == "B":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_B_MD3)

        if md == 3:
            if side == "A":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_A_MD4)
            if side == "B":
                return self.read(PPrReg.CRC_ERR_TOT_SIDE_B_MD4)

        return None

    def get_CRC_BER(self, CRCerr, frames):
        if frames != 0:
            return CRCerr / (120 * frames)
        return None

    def get_CRC_fraction_per_million(self, CRCerr, frames):
        if frames != 0:
            return (10**6 * CRCerr) / frames
        return None


    def get_frames(self, md):
        frame1, frame2 = 0, 0
        lframe1, lframe2 = 0, 0

        if md == 0:
            frame1 = self.read(PPrReg.CRC_FRAMES1_MD1)
            if frame1 is None:
                return None
            frame2 = self.read(PPrReg.CRC_FRAMES2_MD1)
            if frame2 is None:
                return None
        elif md == 1:
            frame1 = self.read(PPrReg.CRC_FRAMES1_MD2)
            if frame1 is None:
                return None
            frame2 = self.read(PPrReg.CRC_FRAMES2_MD2)
            if frame2 is None:
                return None
        elif md == 2:
            frame1 = self.read(PPrReg.CRC_FRAMES1_MD3)
            if frame1 is None:
                return None
            frame2 = self.read(PPrReg.CRC_FRAMES2_MD3)
            if frame2 is None:
                return None
        elif md == 3:
            frame1 = self.read(PPrReg.CRC_FRAMES1_MD4)
            if frame1 is None:
                return None
            frame2 = self.read(PPrReg.CRC_FRAMES2_MD4)
            if frame2 is None:
                return None
        return (frame1, frame2)

        lframe1 = frame1.longValue() & 0xFFFFFFFF
        lframe2 = frame2.longValue() & 0xFFFFFFFF  

        return ((lframe1 & 0xFFFFFFFF) | lframe2 << 32)

    def get_latencies(self, md):
        latency = []
        val = None

        if md == 0:
            val = self.read(PPrReg.LAT_MD1_MD2)
            if val is None:
                return None
            else:
                latency.append(val & 0xFF)
                latency.append((val >> 8) & 0xFF)
                return latency
        elif md == 1:
            val = self.read(PPrReg.LAT_MD1_MD2)
            if val is None:
                return None
            else:
                latency.append((val >> 16) & 0xFF)
                latency.append((val >> 24) & 0xFF)
                return latency
        elif md == 2:
            val = self.read(PPrReg.LAT_MD3_MD4)
            if val is None:
                return None
            else:
                latency.append(val & 0xFF)
                latency.append((val >> 8) & 0xFF)
                return latency
        elif md == 3:
            val = self.read(PPrReg.LAT_MD3_MD4)
            if val is None:
                return None
            else:
                latency.append((val >> 16) & 0xFF)
                latency.append((val >> 24) & 0xFF)
                return latency
        else:
            return None


    # -------------------------------------------------
    # ADC Data
    # -------------------------------------------------

    def get_data_HG(self, md, adc, samples):
        offset = (adc + md * 12) * 32
        values = self.read(PPrReg.PIPELINE_HG + offset, samples)
        return [(v >>16) & 0xFFF for v in values]

    def get_data_LG(self, md, adc, samples):
        offset = (adc + md * 12) * 32
        values = self.read(PPrReg.PIPELINE_LG + offset, samples)
        return [v & 0xFFF for v in values]

    # -------------------------------------------------
    # Integrator
    # -------------------------------------------------

    def get_data_integrator(self, md: int, adc: int, samples: int = 1):
        """
        Reads input single samples from Integrator Slow Readout (Python version of Java function)
        """
        dead_beef = True
        offset = md * 12

        integrator_value = None

        while dead_beef:
            # Read from integrator FIFO
            integrator_value = self.read(
                PPrReg.INTEGRATOR_SLOW_READOUT + (DBReg.ADC_MAP[adc] + offset),
                size=samples
            )

            # If single int, convert to list
            if isinstance(integrator_value, int):
                integrator_value = [integrator_value]
            # print(integrator_value, end=" -> ")
            # Mask each value to 16-bit
            integrator_value = [v & 0xFFFF for v in integrator_value]
            # print(integrator_value)
            # Exit loop if first value is not 0xDEADBEEF
            if integrator_value[0] != 0xDEADBEEF:
                dead_beef = False

        return integrator_value

    def reset_integrator_fifo(self):
        self.write(PPrReg.INTEGRATOR_FIFO, 0x10000)
        self.write(PPrReg.INTEGRATOR_FIFO, 0x0)
        return True



    # -------------------------------------------------
    # FEB Control
    # -------------------------------------------------

    def feb_write(self, md, reg_array, feb, value):
        ctrl = PPrReg.PPR_FEB_CTRL_REG[md]
        data = PPrReg.PPR_FEB_DATA_REG[md]

        self.write(ctrl, reg_array[feb >> 1])
        self.write(data, value)

    def set_feb_switch(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_SWITCHES, feb, value)

    def set_feb_cis_dac(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_CIS_DAC, feb, value)

    def set_feb_ped_hg_pos(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_PED_HG_POS, feb, value)

    def set_feb_ped_hg_neg(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_PED_HG_NEG, feb, value)

    def set_feb_ped_lg_pos(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_PED_LG_POS, feb, value)

    def set_feb_ped_lg_neg(self, md, feb, value):
        self.feb_write(md, PPrReg.PPR_FEB_PED_LG_NEG, feb, value)

    # -------------------------------------------------
    # Latency
    # -------------------------------------------------

    def set_latency(self, md, value):
        if md in (0, 1):
            self.write(PPrReg.LAT_MD1_MD2, value)
        else:
            self.write(PPrReg.LAT_MD3_MD4, value)


    def read_eye(self, verbose=False):
        # ---------------------------
        # Registers
        # ---------------------------
        reg_control = 0x40007
        reg_status = 0x40009
        reg_config = 0x40008
        reg_read = 0x4000A

        # ---------------------------
        # Config params
        # ---------------------------
        lpm = 1
        ver = 2
        hor = 2
        psc = 1
        ut = 0

        # ---------------------------
        # CONFIG
        # ---------------------------
        if verbose:
            print("Writing CONFIG...")

        word = (0 << 31 | ut << 13 | psc << 8 | hor << 4 | ver)
        self.write(reg_config, word)

        word = (1 << 31 | ut << 13 | psc << 8 | hor << 4 | ver)
        self.write(reg_config, word)

        # ---------------------------
        # RESET
        # ---------------------------
        if verbose:
            print("Resetting...")
        self.write(reg_control, (1 << 31 | 0xF << 27))
        self.write(reg_control, (1 << 31 | 0 << 27))

        # ---------------------------
        # START
        # ---------------------------
        if verbose:
            print("Starting...")
        self.write(reg_control, (1 << 31 | 0xF << 23))
        self.write(reg_control, (1 << 31 | 0 << 23))

        # ---------------------------
        # WAIT FOR READY
        # ---------------------------
        if verbose:
            print("Waiting for READY...")

        rdy = 0
        start_time = time.time()
        timeout = 10

        while rdy != 0xFFFF:
            rdy = 0xFFFF & self.read(reg_status)
            if verbose:
                print(f"Status: 0x{rdy:04X}")

            if time.time() - start_time > timeout:
                # print("ERROR: Timeout waiting for READY")
                break

            time.sleep(0.1)

        # ---------------------------
        # Prepare eye matrix as nested lists
        # ---------------------------
        for rr in range(16):
            _ = self.read(reg_read + rr)

        n = 4
        h = (64 // hor + 1) * n
        v = 127 if ver == 1 else (128 // ver + 1)

        if verbose:
            print(f"Matrix size: lanes=16, v={v}, h={h}")

        # 3D list: eye[lane][vert][hor]
        eye = [[[0.0 for _ in range(h)] for _ in range(v)] for _ in range(16)]

        # ---------------------------
        # Acquisition
        # ---------------------------
        if verbose:
            print("Starting acquisition...")

        for rr in range(16):
            if verbose:
                print(f"Lane {rr}")

            for vv in range(v):
                for hh in range(0, h, n):
                    aux = self.read(reg_read + rr)

                    sample = aux & 0xFFFF
                    error = (aux >> 16) & 0xFFFF

                    if sample == 0:
                        sample = 1

                    value = float(error) / float(2 ** (psc + 1) * sample * 40)

                    for ii in range(n):
                        eye[rr][vv][hh + ii] = value

        if verbose:
            print("Eye acquisition done.")

        return eye




class FEB:

    DEBUG = False

    def __init__(self, io):
        self.io = io

    # ========================================================
    # Low-level command builders
    # ========================================================

    def async_write(self, md=None, addr=0, command=0):
        if md is None:
            for md in range(4):
                addr = BitTools.set_bit(13, 1, addr)
                addr = BitTools.set_bit(12, 1, addr)
                self.io.write(PPrReg.ASYNC_ADDRESS, (md+1 << 28) & PPrReg.ASYNC_ADDRESS_MD_MASK + addr, command)
        else:
                addr = BitTools.set_bit(13, 1, addr)
                addr = BitTools.set_bit(12, 1, addr)
                self.io.write(PPrReg.ASYNC_ADDRESS, (md+1 << 28) & PPrReg.ASYNC_ADDRESS_MD_MASK + addr, command)
        
        return True
                
                
    def sync_write(self, bcid, addr, command):
        addr = BitTools.set_bit(13, 1, addr)
        addr = BitTools.set_bit(12, 1, addr)
        self.io.write(PPrReg.SYNC_ADDRESS, addr, command)



    def _build_async_address(self, md: int, dbside: int) -> int:
        addr = (md << 28) & PPrReg.ASYNC_ADDRESS_MD_MASK

        if dbside == 0:
            addr = BitTools.set_bit(13, 0, addr)
        elif dbside == 1:
            addr = BitTools.set_bit(13, 1, addr)
            addr = BitTools.set_bit(12, 0, addr)
        elif dbside == 2:
            addr = BitTools.set_bit(13, 1, addr)
            addr = BitTools.set_bit(12, 1, addr)
        else:
            raise ValueError("Invalid dbside")

        return addr

    # ========================================================
    # ASYNC FE COMMAND
    # ========================================================

    def send_asyncFEcommand(self, md: int, dbside: int, command: int) -> bool:
        addr = self._build_async_address(md, dbside)
        addr |= DBReg.DB_FEB_COMMAND

        if self.DEBUG:
            print(f"send_asyncFEcommand MD={md} DB={dbside}")
            print(f"ADDR=0x{addr:08X} CMD=0x{command:08X}")

        self.io.write(PPrReg.ASYNC_ADDRESS, addr, command)
        return True

    def send_asyncCIScommand(self, md: int, dbside: int, command: int) -> bool:
        addr = self._build_async_address(md, dbside)
        addr |= DBReg.DB_CIS
        self.io.write(PPrReg.ASYNC_ADDRESS, addr, command)
        return True

    # ========================================================
    # SYNC COMMANDS
    # ========================================================

    def send_syncFEcommand(self, md, dbside, bcid, command):
        addr = (md << 28) & PPrReg.SYNC_ADDRESS_MD_MASK

        if dbside == 1:
            addr = BitTools.set_bit(13, 1, addr)
        elif dbside == 2:
            addr = BitTools.set_bit(13, 1, addr)
            addr = BitTools.set_bit(12, 1, addr)

        addr = BitTools.set_bits(16, 27, bcid, addr)
        addr |= DBReg.DB_FEB_COMMAND

        return self.io.write(PPrReg.SYNC_ADDRESS, addr, command)

    def send_syncPPrcommand(self, bcid, command):
        addr = BitTools.set_bits(16, 27, bcid & 0xFFF, 0)
        return self.io.write(PPrReg.SYNC_PPR_ADDRESS, addr, command)

    # ========================================================
    # FPGA Mapping
    # ========================================================

    def feb_to_FPGA(self, feb: int) -> int:
        return ((DBReg.FPGA[feb] << DBReg.CMD_FPGA_OFFSET)
                & DBReg.CMD_FPGA_MASK)

    def feb_to_card(self, feb: int) -> int:
        return ((DBReg.FPGA_CHANNEL[feb] << DBReg.CMD_FPGA_CARD_OFFSET)
                & DBReg.CMD_FPGA_CHANNEL_MASK)

    # ========================================================
    # Generic double pulse transmitter (E=0 then E=1)
    # ========================================================

    def _transmit_double(self, md, dbside, command_base):
        self.send_asyncFEcommand(md, dbside, command_base)
        self.send_asyncFEcommand(md, dbside, command_base | DBReg.CMD_BIT_E_MASK)
        return True

    # ========================================================
    # CIS DAC
    # ========================================================

    def transmit_CIS_DAC(self, md, dbside, feb, val):
        cmd = (self.feb_to_FPGA(feb)
               | self.feb_to_card(feb)
               | ((DBReg.CMD_SET_CIS_DAC << DBReg.CMD_OFFSET)
                  & DBReg.CMD_MASK)
               | (val & DBReg.CMD_DATA_MASK))
        return self._transmit_double(md, dbside, cmd)

    def set_CIS_DAC(self, md, dbside, feb, val):
        cmd = (DBReg.CMD_BIT_E_MASK
               | self.feb_to_FPGA(feb)
               | self.feb_to_card(feb)
               | ((DBReg.CMD_SET_CIS_DAC << DBReg.CMD_OFFSET)
                  & DBReg.CMD_MASK)
               | (val & DBReg.CMD_DATA_MASK))
        return self.send_asyncFEcommand(md, dbside, cmd)


    # ========================================================
    # CIS (SWITCHES)
    # ========================================================


    def set_switches_noise(self, md, dbside, feb):
        val = 0

        # Builds data field switches for noise.
        # TPH=0; TPL=0;ITG=1;S1=S2=S3=S4=0;TRG=1
        val = val | (1 << 7) | (1 << 2)

        command = (DBReg.CMD_BIT_E_MASK
                   | self.feb_to_FPGA(feb)
                   | self.feb_to_card(feb)
                   | ((DBReg.CMD_SET_SWITCHES << DBReg.CMD_OFFSET) & DBReg.CMD_MASK)
                   | (val & DBReg.CMD_DATA_MASK))

        return self.send_asyncFEcommand(md, dbside, command)


    def set_switches(self, md, dbside, feb, val):

        command = (DBReg.CMD_BIT_E_MASK
                   | self.feb_to_FPGA(feb)
                   | self.feb_to_card(feb)
                   | ((DBReg.CMD_SET_SWITCHES << DBReg.CMD_OFFSET) & DBReg.CMD_MASK)
                   | (val & DBReg.CMD_DATA_MASK))

        return self.send_asyncFEcommand(md, dbside, command)




    # ========================================================
    # PEDESTALS (ALL variants)
    # ========================================================

    def set_ped_HG_pos(self, md, dbside, feb, val):
        self._set_ped(md, dbside, feb, DBReg.CMD_SET_PED_HG_POS, val)

    def set_ped_HG_neg(self, md, dbside, feb, val):
        self._set_ped(md, dbside, feb, DBReg.CMD_SET_PED_HG_NEG, val)

    def set_ped_LG_pos(self, md, dbside, feb, val):
        self._set_ped(md, dbside, feb, DBReg.CMD_SET_PED_LG_POS, val)

    def set_ped_LG_neg(self, md, dbside, feb, val):
        self._set_ped(md, dbside, feb, DBReg.CMD_SET_PED_LG_NEG, val)

    def _set_ped(self, md, dbside, feb, cmd_id, val):
        cmd = (DBReg.CMD_BIT_E_MASK
               | self.feb_to_FPGA(feb)
               | self.feb_to_card(feb)
               | ((cmd_id << DBReg.CMD_OFFSET)
                  & DBReg.CMD_MASK)
               | (val & DBReg.CMD_DATA_MASK))
        self.send_asyncFEcommand(md, dbside, cmd)

    def load_ped_HG(self, md, dbside, feb):
        command = (DBReg.CMD_BIT_E_MASK
                   | self.feb_to_FPGA(feb)
                   | self.feb_to_card(feb)
                   | (DBReg.CMD_LOAD_ADC_DAC_HG << DBReg.CMD_OFFSET) & DBReg.CMD_MASK)

        self.send_asyncFEcommand(md, dbside, command)

    def load_ped_LG(self, md, dbside, feb):
        command = (DBReg.CMD_BIT_E_MASK
                   | self.feb_to_FPGA(feb)
                   | self.feb_to_card(feb)
                   | (DBReg.CMD_LOAD_ADC_DAC_LG << DBReg.CMD_OFFSET) & DBReg.CMD_MASK)

        self.send_asyncFEcommand(md, dbside, command)


    # ========================================================
    # L1A Trigger
    # ========================================================

    def send_L1A(self, BCID, arg):
        cmd = 0

        cmd = BitTools.set_bit(0, 1, cmd)
        self.io.write(PPrReg.RO_SYNC_CMD, cmd)
        
        cmd = BitTools.set_bit(0, 0, cmd)
        self.io.write(PPrReg.RO_SYNC_CMD, cmd)

        self.send_syncPPrcommand(BCID & 0xFFF, arg)

        cmd = BitTools.set_bit(1, 1, cmd)
        self.io.write(PPrReg.RO_SYNC_CMD, cmd)

        cmd = BitTools.set_bit(1, 0, cmd)
        self.io.write(PPrReg.RO_SYNC_CMD, cmd)

        cmd = BitTools.set_bit(0, 1, cmd)
        self.io.write(PPrReg.RO_SYNC_CMD, cmd)

    # ========================================================
    # CIS BCID SETTINGS
    # ========================================================

    def set_CIS_BCID_settings(self, md, dbside,
                              BCID_charge,
                              BCID_discharge,
                              gain):

        # command = ((BCID_discharge << 14)
        #            | (BCID_charge << 2)
        #            | (gain << 1)
        #            | 0x0)

        # self.send_asyncCIScommand(md, dbside, command)
        
        command = ((BCID_discharge << 14)
                   | (BCID_charge << 2)
                   | (gain << 1)
                   | 0x1)

        self.send_asyncCIScommand(md, dbside, command)
        return True

    # ========================================================
    # Pedestal conversions
    # ========================================================

    def convert_ped_DACs_to_ADC(self, VpDACs, VnDACs):
        DACrange = 2261 - 1278
        countBase = VpDACs - VnDACs + DACrange
        return round(math.ceil((4096 * countBase)
                               / (2 * DACrange)))

    def convert_ped_ADC_to_DACs(self, ADCcounts) -> List[int]:
        DACrange = 2261 - 1278

        diff = round(math.floor(DACrange * ADCcounts / 4096))
        v1 = 1278 + diff

        diff = round(math.floor(DACrange * ADCcounts / 4096) + 0.5)
        v2 = 2261 - diff

        return [v1, v2]



    def set_FEB_ADC_bias_offsets_DACs(self, ADCped = 200, md=None, dbside=0, verbose=False):
        """
        Set FEB ADC bias offsets (pedestals) for all MDs and FEBs.
        Uses the FEB methods: set_ped_HG_pos, set_ped_HG_neg, set_ped_LG_pos, set_ped_LG_neg.
        """
        ret = True
        DACbiasP, DACbiasN = self.convert_ped_ADC_to_DACs(ADCped)

        # Determine which MDs to process
        if md is None:
            MDmin, MDmax = 0, 4
        else:
            MDmin, MDmax = md, md + 1

        mdidx = 0
        for md in range(MDmin, MDmax):

            for feb in range(12):  # loop over FEB channels
                r = self.set_ped_HG_pos(md, dbside, feb, DACbiasP)
                ret = ret and r
                if verbose:
                    print(f"  MD {md} FEB {feb} set ped HGpos: {DACbiasP} -> {'Ok' if r else 'Fail'}")

                r = self.set_ped_HG_neg(md, dbside, feb, DACbiasN)
                ret = ret and r
                if verbose:
                    print(f"  MD {md} FEB {feb} set ped HGneg: {DACbiasN} -> {'Ok' if r else 'Fail'}")

                r = self.set_ped_LG_pos(md, dbside, feb, DACbiasP)
                ret = ret and r
                if verbose:
                    print(f"  MD {md} FEB {feb} set ped LGpos: {DACbiasP} -> {'Ok' if r else 'Fail'}")

                r = self.set_ped_LG_neg(md, dbside, feb, DACbiasN)
                ret = ret and r
                if verbose:
                    print(f"  MD {md} FEB {feb} set ped LGneg: {DACbiasN} -> {'Ok' if r else 'Fail'}")


        return ret
    # -------------------------
    # FEB ADC pedestal setters
    # -------------------------
    def set_ped_HG_pos(self, md, dbside, feb, val):
        """Set FEB High Gain positive pedestal (DAC)"""
        command = DBReg.CMD_BIT_E_MASK \
                | self.feb_to_FPGA(feb) \
                | self.feb_to_card(feb) \
                | ((DBReg.CMD_SET_PED_HG_POS << DBReg.CMD_OFFSET) & DBReg.CMD_MASK) \
                | (val & DBReg.CMD_DATA_MASK)
        
        return self.send_asyncFEcommand(md, dbside, command)


    def set_ped_HG_neg(self, md, dbside, feb, val):
        """Set FEB High Gain negative pedestal (DAC)"""
       
        command = DBReg.CMD_BIT_E_MASK \
                | self.feb_to_FPGA(feb) \
                | self.feb_to_card(feb) \
                | ((DBReg.CMD_SET_PED_HG_NEG << DBReg.CMD_OFFSET) & DBReg.CMD_MASK) \
                | (val & DBReg.CMD_DATA_MASK)
        
        return self.send_asyncFEcommand(md, dbside, command)


    def set_ped_LG_pos(self, md, dbside, feb, val):
        """Set FEB Low Gain positive pedestal (DAC)"""
        
        command = DBReg.CMD_BIT_E_MASK \
                | self.feb_to_FPGA(feb) \
                | self.feb_to_card(feb) \
                | ((DBReg.CMD_SET_PED_LG_POS << DBReg.CMD_OFFSET) & DBReg.CMD_MASK) \
                | (val & DBReg.CMD_DATA_MASK)
        
        return self.send_asyncFEcommand(md, dbside, command)


    def set_ped_LG_neg(self, md, dbside, feb, val):
        """Set FEB Low Gain negative pedestal (DAC)"""
        command = DBReg.CMD_BIT_E_MASK \
                | self.feb_to_FPGA(feb) \
                | self.feb_to_card(feb) \
                | ((DBReg.CMD_SET_PED_LG_NEG << DBReg.CMD_OFFSET) & DBReg.CMD_MASK) \
                | (val & DBReg.CMD_DATA_MASK)
        
        return self.send_asyncFEcommand(md, dbside, command)




    def set_FEB_integrator_DACs(self, charge: int, md = None, dbside: int = 0, verbose: bool = False) -> bool:
        """
        Set the CIS DAC for all FEBs (12 channels) across selected MDs.

        Args:
            charge (int): DAC value to set
            MDbroadcast (int): 1 = broadcast to all MDs, 0 = selective MDs
            MDsel (list): List of flags (1/0) for selected MDs when not broadcasting
            dbside (int): Which DB side (0, 1, 2)
            verbose (bool): Print debug info
        Returns:
            bool: Success of the last operation
        """
        if md is None:
            MDmin, MDmax =  0, 4
        else:
            MDmin, MDmax = md, md+1

        ret = True

        for md in range(MDmin, MDmax):

            for adc in range(12):
                # Set CIS DAC
                ret = self.transmit_CIS_DAC(md, dbside, adc, charge)

                # Reset integrator FIFO
                self.reset_integrator_fifo()

                # Verbose output
                if verbose:
                    print(f"  MD: {md} FEB: {adc:2d} set Integrator DAC: {charge} result: {'Ok' if ret else 'Fail'}")


        return ret

    def set_integrator_switches(self, gain: int = 1, card_type: int = 1,
                                md = None, dbside: int = 0,
                                verbose: bool = False) -> bool:
        """
        Sets switches for the Integrator run for selected FEBs.

        Args:
            selected_gain_plot (str): Gain string (1-6)
            card_type (int): 0 = 3-in-1, 1 = FENICS2
            MDbroadcast (int): 1 = broadcast to all MDs, 0 = selective MDs
            MDsel (list): List of 0/1 for selected MDs if not broadcasting
            dbside (int): Which DB side
            verbose (bool): Verbose output
        Returns:
            bool: Success of last command
        """
        if md is None:
            MDmin, MDmax = 0, 4
        else:
            MDmin, MDmax = md, md + 1

        ret = False
        sw = [0x8, 0x4, 0x0, 0x2, 0x1, 0x3]

        # Determine gain index
        gain = gain - 1
        if verbose:
            print(f"Gain = {gain}")
        isw = sw[gain]

        # Build switch value
        switchval = (0xb << 7) | (isw << 3)
        if card_type == 1:
            switchval |= 0x4
        elif card_type != 0:
            print("ERROR: Unknown Card Type!!!")

        if verbose:
            card_name = "3-in-1" if card_type == 0 else "FENICS2"
            print(f"Card Type: {card_name}")
            print(f"Switchval = {switchval}")

        # Determine MD range
        for md in range(MDmin, MDmax):
            for adc in range(12):
                command = (1 << 22) + (DBReg.FPGA[adc] << 18) + (DBReg.FPGA_CHANNEL[adc] << 16) + switchval
                ret = self.send_asyncFEcommand(md, dbside, command)
                if verbose:
                    print(f"  MD: {md} FEB: {adc:2d} set Integrator switches result: {'Ok' if ret else 'Fail'}")


        return ret

    def set_FEB_load_ADC_DACs(self, md=None, dbside=0) -> bool:
        """
        Load ADC/DAC pedestals for all FEB channels.

        Args:
            MDbroadcast (int): 1 = broadcast to all MDs, 0 = selective MDs
            MDsel (list): List of 0/1 for selected MDs if not broadcasting
            dbside (int): Which DB side
        Returns:
            bool: Success of the last operation
        """
        if md is None:
            MDmin, MDmax = 0, 4
        else:
            MDmin, MDmax = md, md + 1

        ret = True

        for md in range(MDmin, MDmax):

            for adc in range(12):
                # Load High Gain pedestal
                ret = self.load_ped_HG(md, dbside, adc)
                if self.DEBUG:
                    print(f"  MD: {md} FEB: {adc:2d} load HG result: {'Ok' if ret else 'Fail'}")

                # Load Low Gain pedestal
                ret = self.load_ped_LG(md, dbside, adc)
                if self.DEBUG:
                    print(f"  MD: {md} FEB: {adc:2d} load LG result: {'Ok' if ret else 'Fail'}")



        return ret


    def set_FEB_switches(self, md=None, dbside=0, verbose=False) -> bool:
        """
        Set FEB switches for all MDs and FEBs (noise configuration).

        Args:
            MDbroadcast (int): 1 = broadcast to all MDs, 0 = selective MDs
            MDsel (list): List of flags (1/0) for selected MDs if not broadcasting
            dbside (int): Which DB side
            verbose (bool): Enable verbose output

        Returns:
            bool: Success of the last operation
        """
        ret = True

        if md is None:
            MDmin, MDmax = 0, 4
        else:
            MDmin, MDmax = md, md+1




        for md in range(MDmin, MDmax):

            for adc in range(12):
                ret = self.set_switches_noise(md, dbside, adc)
                if verbose:
                    print(f"  MD: {md} FEB: {adc:2d} set switches result: {'Ok' if ret else 'Fail'}")

        return ret


    def set_CIS_Integrator_BCID_settings(self, md=None, dbside=0,
                            BCID_charge=0, BCID_discharge=0, gain=1, verbose=False) -> bool:
        """
        Configure CIS BCID settings for selected MDs.

        Args:
            MDbroadcast (int): 1 = broadcast to all MDs, 0 = selective MDs
            MDsel (list): List of flags (1/0) for selected MDs if not broadcasting
            dbside (int): Which DB side
            BCID_charge (int): BCID charge setting
            BCID_discharge (int): BCID discharge setting
            gain (int): Gain setting
            verbose (bool): Enable verbose output

        Returns:
            bool: Success of the last operation
        """
        ret = True

        if md is None:
            MDmin, MDmax = 0 , 4
        else:    
            MDmin, MDmax = md, md + 1


        for md in range(MDmin, MDmax):

            ret = self.set_CIS_BCID_settings(md, dbside, BCID_charge, BCID_discharge, gain)
            if verbose:
                print(f"  MD: {md} CIS configuration result: {'Ok' if ret else 'Fail'}")


        return ret



    def reset_integrator_fifo(self):
        self.io.write(PPrReg.INTEGRATOR_FIFO, 0x10000)
        self.io.write(PPrReg.INTEGRATOR_FIFO, 0x0)
        return True








chanMap = [[10, 8, 6], [4, 2, 0], [11, 9, 7], [5, 3, 1]]
RBack_CMDtoOffset = [0, 1, 999, 999, 999, 999, 999, 999, 4, 5, 2, 3]


class IPbus:
    def __init__(self, controlhub_ipaddress, ppr_ipaddress, verbose=False):
        if ppr_ipaddress is None:
            ppr_ipaddress = "192.168.0.1"
        if controlhub_ipaddress is None:
            controlhub_ipaddress = "localhost"
        self.ipbus = Herakles.Uhal(f"tcp://{controlhub_ipaddress}:10203?target={ppr_ipaddress}:50001")
        self.ipbus.SetVerbose(verbose)

    def SyncClear(self):
        self.ipbus.Write(0x6, 0x1)

    def SyncRest(self):
        self.ipbus.Write(0x6, 0x0)

    def SyncEnable(self):
        self.ipbus.Write(0x6, 0x2)

    def SyncLoop(self, num):
        self.ipbus.Write(0x6, (num << 2) + 0x2)
        time.sleep(0.0001)

    def SyncFlush(self, bcid, dba):
        time.sleep(0.0001)
        self.SyncWrite(bcid, dba, 0x80000000)
        time.sleep(0.0001)

    def SyncWrite(self, bcid, dba, val):
        self.ipbus.Write(0x00010000, [bcid << 16 | dba, val])

    def AsyncWrite(self, md, dba, val):
        self.ipbus.Write(0x10002, [((md + 1) << 28) + dba, val])

    def RODRead(self, chan, gain, num):
        addr = 0x100 + (chan * num)
        # Read array of num elements
        raw_data = self.ipbus.Read(addr, num)
        print(f"RODRead addr: {hex(addr)} num: {num} raw_data: {raw_data}")
        # Apply bitwise operations to each element based on gain
        if not gain:
            # For gain=False: mask each element to 12 bits
            data = [value & 0xFFF for value in raw_data]
        else:
            # For gain=True: shift each element right by 16 bits, then mask to 12 bits
            data = [(value >> 16) & 0xFFF for value in raw_data]
        
        return data

    def RODReadOld(self, chan, gain, num):
        addr = 0x100 + (chan * num)
        if not gain:
            addr = 0x700 + (chan * num)
        return self.ipbus.Read(addr, num)

    def RODReadMD(self, md=0, nchan=12, nsamp=16, stride=32):
        """
        Read CIS data from multiple channels with memory stride.

        Args:
            firstMD (int): The first module (MD) index for this read
            nchan (int): Number of channels to read (default 12)
            nsamp (int): Number of samples per channel (default 16)
            stride (int): Memory spacing between channels (default 32)

        Returns:
            List[List[int]]: A list of channels, each containing nsamp samples.
                             Example: data[channel][sample]
        """
        data = []
        for ch in range(nchan):
            addr = 0x100 + stride * (ch + 12 * md)
            samples = self.ipbus.Read(addr, nsamp)
            data.append(samples)
        return data


    def RODReadChunck(self, addr, num):
        return self.ipbus.Read(addr, num)

    def RODWrite(self, bcid, val):
        self.ipbus.Write(0x00010004, [bcid << 16, val])

    def RODConfigWrite(self, add, val):
        self.ipbus.Write(add, val)

    def ReadVal(self, add):
        return self.ipbus.Read(add, 1)

    def CheckValue2(self, md, FPGA, card, setting, value, verbose=False):
        adc = FPGACARDtoADC[FPGA][card]
        readbackvalue = self.ReadVal(((md) << 20) + 0x10020 + (adc << 4) + setting)
        time.sleep(0.01)

        if value != (readbackvalue & 0xFFF):
            if verbose:
                print(f"Readback ERROR!! ADC: {adc} FPGA: {FPGA} Card: {card} "
                      f"Expected Value: {hex(value)} Addr: {hex(((1 * md) << 20) + 0x10020 + (adc << 4) + setting)} "
                      f"Real readback: {hex(readbackvalue)}")
            return False
        else:
            return True

    def CheckValue(self, md, fpga, card, setting, value, verbose=False):
        cmd = (1 << 22) + (fpga << 18) + (card << 16) + (setting << 12) + 0x111
        self.ipbus.Write(0x10002, [(md + 1 << 28) + 0x1, cmd])
        time.sleep(0.00001)
        cmd = (1 << 21) + (fpga << 18) + (card << 16) + (setting << 12) + 0x111
        self.ipbus.Write(0x10002, [(md + 1 << 28) + 0x1, cmd])
        time.sleep(0.00001)

        addr = 0x10000 + (md << 20) + ((chanMap[fpga][card] + 2) << 4) + RBack_CMDtoOffset[setting]
        readbackvalue = self.ipbus.Read(addr)
        if verbose:
            print(f"Send command request: {hex(cmd)}")
            print(f"Address to read from: {hex(addr)}")
            print(f"Value expected/received: 0x{value:x} / {hex(readbackvalue)}")

        readbackvaluemask = readbackvalue & 0xFFF
        return value == readbackvaluemask

    def DB_Read_Val(self, md, reg):
        md_ctrl = 0x00010018 + (md << 20)
        md_reg = 0x00010019 + (md << 20)

        rbkvalue = [0, 0]
        for i, the_side in enumerate(range(0, 2)):
            md_addr = (the_side << 31 | reg)
            self.RODConfigWrite(md_ctrl, md_addr)
            time.sleep(0.05)
            rbkvalue[i] = self.ReadVal(md_reg)

        return rbkvalue

    def DB_Write_Val(self, md, fpga, register, value, mask=0):
        if mask == 0:
            mask = 0xFFFFFFFF

        # send mask
        self.AsyncWrite(md, (fpga << 12) + cfb_db_reg_mask, mask)
        # write value
        self.AsyncWrite(md, (fpga << 12) + register, value)
        # clear mask
        self.AsyncWrite(md, (fpga << 12) + cfb_db_reg_mask, 0xFFFFFFFF)

    def DB_Deskew_All_Channels(self, md, fpga, phase):
        if phase < 24949:
            value = phase
            ps_value = (((int(value / 48.828125)) & 0b111111111111) << 3)
            command = (ps_value << 16) + (0b1 << 13) + (ps_value) + (0b1 << 12)

            if fpga == -1:
                self.DB_Write_Val(md, 0, cfb_mb_phase_config, command, 0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0, cfb_mb_phase_config, command, 0)
            else:
                print(fpga)
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config, command, 0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config, command, 0)
        else:
            print(f"****************PHASE TOO CLOSE TO LIMIT: {phase} ******************")

    def DB_Deskew_Channels(self, md, fpga, quadrant, phase):
        if phase < 24949:
            ps_value = (((int(phase / 48.828125)) & 0b111111111111) << 3)

            if quadrant == 0:
                command = ps_value + (0b1 << 12)
            elif quadrant == 1:
                command = (ps_value << 16) + (0b1 << 13)
            else:
                command = (ps_value << 16) + (0b1 << 13) + ps_value + (0b1 << 12)

            if fpga == -1:
                self.DB_Write_Val(md, 0, cfb_mb_phase_config, command, 0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0, cfb_mb_phase_config, command, 0)
            else:
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config, command, 0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config, command, 0)
        else:
            print(f"****************PHASE TOO CLOSE TO LIMIT: {phase} ******************")

    def GetDownLinkStatus(self, md, link, verbose=False):
        card = 2
        command = 4  # DAC
        data = int(4095 * random.random())
        if link in ["A0", "A1"]:
            FPGA = 1
        else:
            FPGA = 3

        self.AsyncWrite(md, 0x1, (1 << 22) + (FPGA << 18) + (card << 16) + (command << 12) + data)
        time.sleep(0.001)
        command = 8  # readback
        ReadbackCheck = self.CheckValue(md, FPGA, card, command, data)
        # Try twice
        if not ReadbackCheck:
            ReadbackCheck = self.CheckValue(md, FPGA, card, command, data)
        if verbose:
            print(f"Test of readback: {ReadbackCheck}")
        return ReadbackCheck

import Herakles
import time
import random

# db declarations
from db_lib import *

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

    def DB_Write_Val(self, md, fpga, register, value, mask):
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

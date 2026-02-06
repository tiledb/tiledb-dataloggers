import Herakles
import time
import random

#db declarations
from db_lib import *

chanMap=[[10,8,6],[4,2,0],[11,9,7],[5,3,1]]
RBack_CMDtoOffset=[0,1,999,999,999,999,999,999,4,5,2,3]

class IPbus:
    def __init__(self, controlhub_ipaddress, ppr_ipaddress, verbose=False):
        if ppr_ipaddress == None:
            ppr_ipaddress = "192.168.0.1"
        if controlhub_ipaddress ==None:
            controlhub_ipaddress="localhost"
        self.ipbus = Herakles.Uhal("tcp://"+controlhub_ipaddress+":10203?target="+ppr_ipaddress+":50001")
#        self.ipbus = Herakles.Uhal(ipaddress)
        #print("Connected")
        self.ipbus.SetVerbose(verbose)
        pass
    def SyncClear(self): self.ipbus.Write(0x6, 0x1)
    def SyncRest(self): self.ipbus.Write(0x6, 0x0)
    def SyncEnable(self): self.ipbus.Write(0x6, 0x2)
    def SyncLoop(self, num):
        self.ipbus.Write(0x6, (num << 2) + 0x2)
        time.sleep(0.0001)
        pass
    def SyncFlush(self, bcid, dba):
        time.sleep(0.0001)
        self.SyncWrite(bcid, dba, 0x80000000)
        time.sleep(0.0001)
    def SyncWrite(self, bcid, dba, val): self.ipbus.Write(0x00010000, [bcid << 16|dba, val])
    def AsyncWrite(self, md, dba, val):
        self.ipbus.Write(0x10002, [((md+1)<<28)+dba, val])

      #  print "Async writing : In sROD address:",0x10002," - ",  hex((md+1<<28)+dba), "/", hex(val)
#    def AsyncWrite(self, dba, val):
#        self.ipbus.Write(0x00010002, [dba, val])


    def RODRead(self, chan, gain, num):
        addr = 0x100 + (chan*num)
        if not gain: addr = 0x700 + (chan*num)
        #print " Read from address:", hex(addr)
        return self.ipbus.Read(addr, num)

    def RODReadChunck(self,addr,num):
        return self.ipbus.Read(addr, num)

    def RODWrite(self, bcid, val): self.ipbus.Write(0x00010004, [bcid << 16, val])

    def RODConfigWrite(self,add,val): self.ipbus.Write(add,val)

    def ReadVal(self, add): return self.ipbus.Read(add,1)

    def CheckValue2(self,md,FPGA,card,setting,value, verbose=False):
        adc=FPGACARDtoADC[FPGA][card]
        readbackvalue = ipbus.ReadVal( ((md)<<20) +0x10020 + (adc<<4) + setting)
        time.sleep(0.01)

        if(value != (readbackvalue&0xFFF)):
            if(verbose==True):print "Readback ERROR!!. ADC:",adc, " FPGA:",FPGA," Card:",card, " Expected Value: ",hex(value),  " Addr: ", hex( ((1*md)<<20) +0x10020 + (adc<<4) + setting), " real  readback: ", hex(readbackvalue)
            return False
        else:
            return True

    def CheckValue(self,md,fpga,card,setting,value, verbose=False):
        cmd = (1<<22)+(fpga<<18)+(card<<16)+(setting<<12)+0x111
        #print 'Send command request: %s'  %hex(cmd)
        self.ipbus.Write(0x10002, [(md+1<<28)+0x1, cmd])
        time.sleep(0.00001)
        cmd = (1<<21)+(fpga<<18)+(card<<16)+(setting<<12)+0x111
        self.ipbus.Write(0x10002, [(md+1<<28)+0x1, cmd])
        time.sleep(0.00001)
        #self.ipbus.Write(0x10002, [(md+1<<28)+0x1, 0x80000000])
        time.sleep(0.00001)
        addr=0x10000+(md<<20)+((chanMap[fpga][card]+2)<<4)+RBack_CMDtoOffset[setting]
        readbackvalue=self.ipbus.Read(addr)
        if(verbose==True):
                        print "Send command request: %s"  %hex(cmd)
                        print "Address to read from:",  hex(addr)
                        print "Value expected/received: 0x%x  / %s " %((value),hex(readbackvalue))

        readbackvaluemask = readbackvalue & 0xFFF
        if (value == readbackvaluemask):
            return True
        else:
            return False

    def DB_Read_Val(self,md,reg):
        md_ctrl	= (0x00010018 + (md<<20))
        md_reg 	= (0x00010019 + (md<<20))
        
        # if side=="A":
            # the_side=0
        # elif side=="B":
            # the_side=2
        rbkvalue = [0,0]
        i=0
        for the_side in range(0,2):
            md_addr 	= (the_side<<31 | reg)
            self.RODConfigWrite(md_ctrl,md_addr)
            time.sleep(0.05)
            rbkvalue[i] = self.ReadVal(md_reg)
            i=i+1

        return rbkvalue
        #print ("side ", sd  ," reg ",hex(reg), " value  ", hex(rbkvalue))

    def DB_Write_Val(self, md,fpga,register,value,mask):
        if mask == 0:
            mask = 0xFFFFFFFF

        #send mask
        self.AsyncWrite(md,(fpga<<12) + cfb_db_reg_mask, mask)#(1<<22)+(0<<18)+(0<<16)+(0<<12)+0)
        #time.sleep(0.1)
        #self.ipbus. AsyncWrite(1,the_register,the_value)
        #self.ipbus.AsyncWrite(md,0x1, (1<<22)+(FPGA<<18)+(card<<16)+(command<<12)+data)
        self.AsyncWrite(md,(fpga<<12) + register, value)#(1<<22)+(0<<18)+(0<<16)+(0<<12)+0)
        #time.sleep(0.1)
            
        #clear mask
        self.AsyncWrite(md,(fpga<<12) + cfb_db_reg_mask, 0xFFFFFFFF)#(1<<22)+(0<<18)+(0<<16)+(0<<12)+0)
        #print " Write to ConfigBus: ", register," ",hex(value)

    def DB_Deskew_All_Channels(self, md, fpga, phase):
        if phase < 24949: # 24950: #24900:
            value = phase	
            #coarse_delay_value= (((int((value)/781.25)) <<4))<<2
            #fine_delay_value= ((int((value)/48.828125)))<<2

            #ps_value = (coarse_delay_value+fine_delay_value) & 0b111111111111
            ps_value=((((int((value)/48.828125)))&0b111111111111)<<3)

            command=(ps_value<<16) + (0b1<<13) + (ps_value) + (0b1<<12)
            #print("phase: ", str(phase))
            #print("coarse_delay_value: ", str(int((value)/781.25)), "bin:",  bin(coarse_delay_value>>6))
            #print("fine_delay_value: ",  str(int((value)/48.828125)), "bin:", bin(fine_delay_value>>2))
            # print("command value: " + bin(command) + " GBTx Channel: " + str(gbtx_channel) + ": " + str(phase) + " ps...")

            if fpga == -1:
                self.DB_Write_Val(md, 0,cfb_mb_phase_config,command,0)
                #self.DB_Write_Val(md, 1,cfb_mb_phase_config,command,0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0,cfb_mb_phase_config,command,0)
                #self.DB_Write_Val(md, 1,cfb_mb_phase_config,command,0)
            else:
                print fpga
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config,command,0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0b10 | fpga ,cfb_mb_phase_config,command,0)
                
        else:
            print("****************PHASE TOO CLOSE TO LIMIT: ", phase, " ******************")

    def DB_Deskew_Channels(self, md, fpga, quadrant, phase):
        
        if phase < 24949: # 24950: #24900:
            value=phase
                            
            value = phase	
            #coarse_delay_value= (((int((value)/781.25)) <<4))<<2
            #fine_delay_value= ((int((value)/48.828125)))<<2

            #ps_value = (coarse_delay_value+fine_delay_value) & 0b111111111111
            ps_value=((((int((value)/48.828125)))&0b111111111111)<<3)
            
            if quadrant == 0:
                command=(ps_value) + (0b1<<12)
            elif quadrant == 1:
                command=(ps_value<<16) + (0b1<<13)
            else:
                command=(ps_value<<16) + (0b1<<13) + (ps_value) + (0b1<<12)
             
#            command=(ps_value<<16) + (0b1<<13) + (ps_value) + (0b1<<12)
            #print("phase: ", str(phase))
            #print("coarse_delay_value: ", str(int((value)/781.25)), "bin:",  bin(coarse_delay_value>>6))
            #print("fine_delay_value: ",  str(int((value)/48.828125)), "bin:", bin(fine_delay_value>>2))
            # print("command value: " + bin(command) + " GBTx Channel: " + str(gbtx_channel) + ": " + str(phase) + " ps...")


            if fpga == -1:
                self.DB_Write_Val(md, 0,cfb_mb_phase_config,command,0)
                #self.DB_Write_Val(md, 1,cfb_mb_phase_config,command,0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0,cfb_mb_phase_config,command,0)
                #self.DB_Write_Val(md, 1,cfb_mb_phase_config,command,0)
            else:
                #print fpga
                self.DB_Write_Val(md, 0b10 | fpga, cfb_mb_phase_config,command,0)
                command = 0x0
                time.sleep(0.1)
                self.DB_Write_Val(md, 0b10 | fpga ,cfb_mb_phase_config,command,0)
        else:
            print("****************PHASE TOO CLOSE TO LIMIT: ", phase, " ******************")

    def GetDownLinkStatus(self,md,link,verbose=False):
        card=2
        command=4 #DAC
        data=int(4095*(random.random()))
        if(link=="A0" or link=="A1"):
            FPGA=1
        else:
            FPGA=3
        self.AsyncWrite(md,0x1, (1<<22)+(FPGA<<18)+(card<<16)+(command<<12)+data)
        time.sleep(0.001)
        command=8 #readback
        ReadbackCheck=self.CheckValue(md,FPGA,card,command,data)
        #Try twice#
        if(ReadbackCheck==False):ReadbackCheck=self.CheckValue(md,FPGA,card,command,data)
        if(verbose==True):print "Test of readback:", ReadbackCheck
        return ReadbackCheck

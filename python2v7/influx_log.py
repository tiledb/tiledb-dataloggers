import sys, time, datetime
from array import array
import Herakles
import random
from optparse import OptionParser

#tilecal libs
from db_lib import *
from db_ppr_ipbus import *
from db_influx_lib import *

#python libs
from optparse import OptionParser
import sys
import time


# Set up the connection parameters
#host = "172.16.168.131"  # Replace with your InfluxDB host
host = "192.168.0.252"  # Replace with your InfluxDB host
port = 8086  # Default port for InfluxDB 1.x
username = "tiledb"  # Replace with your InfluxDB username (if required)
password = "T1le-db-word!"  # Replace with your InfluxDB password (if required)
database = "tiledb"  # Replace with your InfluxDB database name

# Initialize the InfluxDB client
influxdb = InfluxDBClient(host=host, port=port, username=username, password=password, database=database)

testTimePerLink=3

total_cmd=0
error_cmd=0

controlhub_ipaddress="localhost"
ppr_ipaddress = "192.168.0.2"#"199.169.0.50"#"192.168.0.1"

test0= random.randint(0, 0xFFFF)
connection_flag=0
while connection_flag==0:
	ppr = IPbus(controlhub_ipaddress,ppr_ipaddress)
	#test0= ppr.ReadVal(0)
	ppr.RODConfigWrite(0,0)
	ppr.RODConfigWrite(0,test0)
	test1= ppr.ReadVal(0)
	if test1==test0:
	    print "PPr Loopback reg test Passed! " +  hex(test0) + " = " + hex(test1)
	    connection_flag=1
	else:
	    print "Warning!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
	    print "PPr Loopback reg test: " + hex(test0) + " is not " + hex(test1)
	    print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
	    time.sleep(5)


print("Connected to controlhub: "+ controlhub_ipaddress + ", interfaced with PPr: " + ppr_ipaddress + ", FW version: " + str(hex(ppr.ReadVal(1))))



    
nframesMD=[0. for i in range(4)]
nCRCerrorsA0_MD=[0. for i in range(4)]
nCRCerrorsA1_MD=[0. for i in range(4)]
nCRCerrorsB0_MD=[0. for i in range(4)]
nCRCerrorsB1_MD=[0. for i in range(4)]
nCRCEffectiveErrorsA=[0. for i in range(4)]
nCRCEffectiveErrorsB=[0. for i in range(4)]

LatA=[0. for i in range(4)]
LatB=[0. for i in range(4)]

fractionA0=[0. for i in range(4)]
fractionA1=[0. for i in range(4)]
fractionB0=[0. for i in range(4)]
fractionB1=[0. for i in range(4)]

Nbits=[0. for i in range(4)]

BERA0=[0. for i in range(4)]
BERA1=[0. for i in range(4)]
BERB0=[0. for i in range(4)]
BERB1=[0. for i in range(4)]

DownLinkStatusA= [False for i in range(4)]
DownLinkStatusB= [False for i in range(4)]

StatusA=[0 for i in range(4)]
StatusA1=[0 for i in range(4)]
StatusB=[0 for i in range(4)]
StatusB1=[0 for i in range(4)]

#measurement-labels=["MD0"]
uplink_labels=["A0","A1","B0","B1"]


firstMD=0
nMD=4
verbose=False

while True:
    for md in range(firstMD, firstMD+nMD):
        
	StatusA[md]=ppr.ReadVal(0x10+md*2)
	StatusA1[md]=(StatusA[md]&0xFFFF0000)>>16
	StatusB[md]=ppr.ReadVal(0x11+md*2)
	StatusB1[md]=(StatusB[md]&0xFFFF0000)>>16
	
	time.sleep(0.01)

	DownLinkStatusA[md] = ppr.GetDownLinkStatus(md,"A0")
	DownLinkStatusB[md] = ppr.GetDownLinkStatus(md,"B0")
	nframesMD[md]= ppr.ReadVal(0x21+8*md)
	nframesMD[md]= (ppr.ReadVal(0x22+(8*md))<<32 ) + nframesMD[md]
	nCRCerrorsA0_MD[md] = ppr.ReadVal(0x23+(8*md))
	nCRCerrorsA1_MD[md] = ppr.ReadVal(0x24+(8*md))
	nCRCerrorsB0_MD[md] = ppr.ReadVal(0x25+(8*md))
	nCRCerrorsB1_MD[md] = ppr.ReadVal(0x26+(8*md))
	nCRCEffectiveErrorsA[md] =     ppr.ReadVal(0x27+(8*md))
	nCRCEffectiveErrorsB[md] =     ppr.ReadVal(0x28+(8*md))

	if nframesMD[md]==0:
		print("nFrames=0! Communication error?")
		time.sleep(5)
		print("Recconecting")
		ppr = IPbus(controlhub_ipaddress,ppr_ipaddress)
		print("Retrying...")
		continue
	
        fractionA0[md]=(1000000*nCRCerrorsA0_MD[md])/(nframesMD[md])
        fractionA1[md]=(1000000*nCRCerrorsA1_MD[md])/(nframesMD[md])
        fractionB0[md]=(1000000*nCRCerrorsB0_MD[md])/(nframesMD[md])
        fractionB1[md]=(1000000*nCRCerrorsB1_MD[md])/(nframesMD[md])
        LatA[md] =     (ppr.ReadVal(0x85 + md/2) >> (16*(md%2))  )&0x00FF
        LatB[md] =     (ppr.ReadVal(0x85 + md/2) >> (8 + 16*(md%2)) )&0x00FF
        Nbits[md]=120*nframesMD[md]
        BERA0[md]=float(nCRCerrorsA0_MD[md])/Nbits[md]
        BERA1[md]=float(nCRCerrorsA1_MD[md])/Nbits[md]
        BERB0[md]=float(nCRCerrorsB0_MD[md])/Nbits[md]
        BERB1[md]=float(nCRCerrorsB1_MD[md])/Nbits[md]

	nframes=[nframesMD[0],nframesMD[0],nframesMD[0],nframesMD[0]]
	ncrc=[nCRCerrorsA0_MD[0],nCRCerrorsA1_MD[0],nCRCerrorsB0_MD[0],nCRCerrorsB1_MD[0]]
	lat=[LatA[0],LatA[0],LatB[0],LatB[0]]
	downlink_status=[DownLinkStatusA[0],DownLinkStatusA[0],DownLinkStatusB[0],DownLinkStatusB[0]]
	ber=[BERA0[0],BERA1[0],BERB0[0],BERB1[0]]
	tx_pll=[StatusA[0]&0x1,StatusA1[0]&0x1,StatusB[0]&0x1,StatusB1[0]&0x1]
	rx_frameclk=[(StatusA[md]&0x2)>>1,(StatusA1[md]&0x2)>>1,(StatusB[md]&0x2)>>1,(StatusB1[md]&0x2)>>1]
	rx_wordclk=[(StatusA[md]&0x4)>>2,(StatusA1[md]&0x4)>>2,(StatusB[md]&0x4)>>2,(StatusB1[md]&0x4)>>2]
	mgt_rdy=[(StatusA[md]&0x4)>>2,(StatusA1[md]&0x4)>>2,(StatusB[md]&0x4)>>2,(StatusB1[md]&0x4)>>2]
	bitslip=[(StatusA[md]&0x3F0)>>4,(StatusA1[md]&0x3F0)>>4,(StatusB[md]&0x3F0)>>4,(StatusB1[md]&0x3F0)>>4]
	gbtrx_rdy=[(StatusA[md]&0x400)>>10,(StatusA1[md]&0x400)>>10,(StatusB[md]&0x400)>>10,(StatusB1[md]&0x400)>>10]
	gbttx_rdy_lost=[(StatusA[md]&0x800)>>11,(StatusA1[md]&0x800)>>11,(StatusB[md]&0x800)>>11,(StatusB1[md]&0x800)>>11]
	data_error=[(StatusA[md]&0x1000)>>12,(StatusA1[md]&0x1000)>>12,(StatusB[md]&0x1000)>>12,(StatusB1[md]&0x1000)>>12]
		

	
	for l in range(4):
		data = [
		    {
			"measurement": "Link Status",
			"tags": {
				"PPrEmu MD" + str(md+1): ("uplink " + uplink_labels[l])   #"A0"
			},
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
		    } 
		]
		# Write the data point to the database
		influxdb.write_points(data)


    time.sleep(1)
	














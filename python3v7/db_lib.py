#daughterboard configuration registers		
cfg_register_zero = 0;
cfb_mb_adc_config = 1;
cfb_mb_phase_config = 2;
cfb_cis_config = 3;
cfb_cs_command = 4;
cfb_integrator_interval = 5;
cfb_bc_num_offset = 6;
cfb_sem_control = 7;
cfb_tx_control = 8;
cfb_gbtx_reg_config = 9;
cfb_db_control = 10;
cfb_loopback = 11;
cfb_db_advanced_reg_value = 12;
cfb_db_debug = 13;
cfb_db_reg_mask = 14;
cfb_strobe_reg = 15;
bc_number = 16; 
cfb_wr_strobe = 17;

#advanced configbus registers
adv_cfg_gty_txdiffctrl = 18;
adv_cfg_gty_txpostcursor = 19;
adv_cfg_gty_txprecursor= 20;
adv_cfg_gty_txmaincursor = 21;

adc_register_config     = 26;
adc_readout_idelay3_0   = 27;
adc_readout_idelay3_1   = 28;
adc_readout_idelay3_2   = 29;
adc_readout_idelay3_3   = 30;
adc_readout_idelay3_4   = 31;
adc_readout_idelay3_5   = 32;

#configbus and dataformat offsets
fpga_side_offset=12
md_offset=28

lut_xadc_address_labels = [
"db_temperature", 
"db_vccint(0.9v)",
"db_vccaux(1.8v)",
"db_mon_0.95v(vaux0)",
"db_mon_2.5v(vaux1)",
"db_sense_3(vaux2)",
"db_mon_1.5v(vaux3)",
"db_sense_2(vaux04)",
"db_mon_1.0v(vaux5)",
"db_sense_1(vaux6)",
"mb_mon_-5v(vaux7)",
"db_mon_1.8v(vaux8)",
"db_mon_1.2v(vaux9)",
"mb_mon_+5v(vaux10)",
"db_mon_3.3v(vaux11)",
"mb_mon_1.8v(vaux12)",
"mb_mon_10v(vaux13)",
"mb_mon_1.2v(vaux14)",
"mb_mon_2.5v(vaux15)",
"vp_vn",
"vp_ref",
"vn_ref",
"vram",
"max_temp",
"max_vccout",
"max_vccint",
"max_vram",
"min_temp",
"min_vccout",
"min_vccint",
"min_vram"
]


lut_xadc_address = [
0x00,
0x01,
0x02,
0x10,
0x11,
0x12,
0x13,
0x14,
0x15,
0x16,
0x17,
0x18,
0x19,
0x1a,
0x1b,
0x1c,
0x1d,
0x1e,
0x1f,
0x03,
0x04,
0x05,
0x06,
0x20,
0x21,
0x22,
0x23,
0x24,
0x25,
0x26,
0x27]

lut_xadc_fa=[
502.9098/65536,
0.244*3/16,
0.244*3/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244/16,
0.244*3/16,
0.244*3/16,
0.244*3/16,
0.244*3/16,
502.9098/65536,
0.244*3/16,
0.244*3/16,
0.244*3/16,
502.9098/65536,
0.244*3/16,
0.244*3/16,
0.244*3/16
]

lut_xadc_fb=[-273.819,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
0,
-273.819,
0,
0,
0,
-273.819,
0,
0,
0]


#db_rg_2v5=(1./((100000/(200))+1)*0.002)
db_rg_2v5=(1./(((100000/(124))+1)*0.002)) / (10000./(20000+10000))
#db_rg_3v3=(1./((100000/(560))+1)*0.002)
db_rg_3v3=(1./(((100000/(124))+1)*0.002)) / (10000./(20000+10000))
#db_rg_0v95=(1./((100000/(750))+1)*0.002)
db_rg_0v95=(1./(((100000/(200))+1)*0.002)) / (10000./(10000+10000))
#db_rg_1v2=(1./((100000/(750))+1)*0.002)
db_rg_1v2= (1./(1+(100000/187))) * (1./(10000./(10000+10000))) * (1./0.002)
#db_rg_1v8=(1./((100000/(560))+1)*0.002)
db_rg_1v8=(1./(((100000/(124))+1)*0.002)) / (10000./(20000+10000))
#db_rg_1v5=(1./((100000/(560))+1)*0.002)
db_rg_1v5= (1./(1+(100000/187))) * (1./(10000./(10000+10000))) * (1./0.002)
#db_rg_1v0=(1./((100000/(560))+1)*0.002)
db_rg_1v0= (1./(1+(100000/187))) * (1./(10000./(10000+10000))) * (1./0.002)


mb_rg_5v0n=1./(20*0.02)
mb_rg_5v0=1./(20*0.02)
mb_rg_10v0=1./10
mb_rg_2v5=1./(20*0.01)
mb_rg_1v8=1./(20*0.02)
mb_rg_1v2=1./(20*0.2)


lut_xadc_fg=[
1,
1,
1,
db_rg_0v95,
db_rg_2v5,
1,
db_rg_1v5,
1,
db_rg_1v0,
1,
mb_rg_5v0n,
db_rg_1v8,
db_rg_1v2,
mb_rg_5v0,
db_rg_3v3,
mb_rg_1v8,
mb_rg_10v0,
mb_rg_1v2,
mb_rg_2v5,
1,
1,
1,
1,
1,
1,
1,
1,
1,
1,
1,
1
]

lut_xadc_dimensions= [
" C",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" mV",
" C",
" mV",
" mV",
" mV",
" C",
" mV",
" mV",
" mV"
]

lut_xadc_fg_dimensions= [
" C",
" mV",
" mV",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mA",
" mV",
" mV",
" mV",
" mV",
" C",
" mV",
" mV",
" mV",
" C",
" mV",
" mV",
" mV"
]


lut_cfgbus_address = [
0x000,
0x001,
0x0F0,
0x121,
0x004,
0x115,
0x006,
0x007,
0x008,
0x009,
0x00A,
0xFFF,
0x00C,
0x00D,
0x00E,
0x00F
] #,0x010]

lut_cfgbus_address_labels = ["cfg_register_zero",
"cfb_mb_adc_config",
"cfb_mb_phase_config",
"cfb_cis_config",
"bc_number",
"cfb_integrator_interval",
"cfb_tx_reg_address",
"cfb_sem_control",
"cfb_tx_control",
"cfb_gbtx_reg_config",
"cfb_strobe_lenght",
"cfb_loopback",
"cfb_db_cfg_fw_version",
"cfb_db_debug",
"cfb_db_reg_mask",
"cfb_strobe_reg"
] #,"cfb_strobe_reg"]


c_stb_mb          = 0;
c_stb_db_fwversion          = 1;
c_stb_mb_q0          = 2;
c_stb_mb_q1          = 3;
c_stb_db_debug          = 4;
c_stb_db_xadc          = 5;
c_stb_sem          = 6;
c_stb_loopback          = 7;#10;
c_stb_gbtxa_reg          = 8;#16;
c_stb_sfp0_reg          = 9; #19;
c_stb_sfp1_reg          = 10; #20;
c_stb_pgood_reg         = 11; #21;
c_stb_tmr               = 12; #22
c_stb_db_status        = 13;
c_stb_adc_readout_status        = 14;
c_stb_adc_readout_counter_status        = 15;
c_stb_global_date  = 15+1;# 32 bit date of last commit when the project was modified. format: ddmmyyyy (hex with decimal digits, no digit greater than 9 is used)
c_stb_global_time = 16+1; # 32 bit time of last commit when the project was modified. format: 00hhmmss (hex with decimal digits, no digit greater than 9 is used)
c_stb_global_ver = 17+1; # 32 bit last version tag when the project was modified. the version of the form m.m.p is encoded in hexadecimal as mmmmpppp
c_stb_global_sha = 18+1; # 32 bit git hash (sha) of the last commit when the project was modified.
c_stb_top_ver = 19+1; # 32 bit top directory version, containing the hog.conf file and other files. the version of the form m.m.p is encoded in hexadecimal as mmmmpppp
c_stb_top_sha = 20+1; # 32 bit top directory version, containing the hog.conf file and other files.
c_stb_con_ver = 21+1; # 32 bit the version of the constraint files. the version of the form m.m.p is encoded in hexadecimal as mmmmpppp
c_stb_con_sha = 22+1; # 32 bit the git commit hash (sha) of the constraint files.
c_stb_hog_ver = 23+1; # 32 bit hog submodule version. the version of the form m.m.p is encoded in hexadecimal as mmmmpppp
c_stb_hog_sha = 24+1; # 32 bit hog submodule git commit hash (sha).
c_stb_xml_ver = 25+1; # 32 bit (optional) ipbus xml version. the version of the form m.m.p is encoded in hexadecimal as mmmmpppp
c_stb_xml_sha = 26+1; # 32 bit (optional) ipbus xml git commit hash (sha).
c_stb_dna_2 = 27+1;
c_stb_dna_1 = 28+1;
c_stb_dna_0 = 29+1;
c_stb_running_time_status = 30+1;
c_stb_integrator_status = 31+1;


lut_tx_address = [
0x001,
0xF0F,
0x012,
0x013,
0xD0D,
0x015,
0x016,
0xFFF,
0x330,
0x340,
0x341,
0xAFF,
0x00C,
0x00D,
0x00E,
0x00F,
0x100,
0x101,
0x102,
0x103,
0x104,
0x105,
0x106,
0x107,
0x108,
0x109,
0x10A,
0x10B,
0x10C,
0x10D,
0x10E,
0x10F,
0x00A

]

lut_tx_address_labels = [
"stb_mb",
"stb_db_fwversion",
"stb_mb_q0",
"stb_mb_q1",
"stb_db_debug",
"stb_db_xadc",
"stb_sem",
"stb_loopback",
"stb_gbtxa_reg",
"stb_sfp0_reg",
"stb_sfp1_reg",
"stb_pgood_reg",
"stb_tmr",
"stb_db_status",
"stb_adc_readout_status",
"stb_adc_readout_counter_status",
"stb_global_date",
"stb_global_time",
"stb_global_ver",
"stb_global_sha",
"stb_top_ver",
"stb_top_sha",
"stb_con_ver",
"stb_con_sha",
"stb_hog_ver",
"stb_hog_sha",
"stb_xml_ver",
"stb_xml_sha",
"stb_dna_2",
"stb_dna_1",
"stb_dna_0",
"stb_running_time_status",
"stb_integrator_status"
]



lut_cfgbus_address_labels = [
"cfg_register_zero",
"cfb_mb_adc_config",
"cfb_mb_phase_config",
"cfb_cis_config",
"cfb_cs_command",
"cfb_integrator_interval",
"cfb_bc_num_offset",
"cfb_sem_control",
"cfb_tx_control",
"cfb_gbtx_reg_config",
"cfb_strobe_lenght",
"cfb_loopback",
"cfb_db_advanced_reg_value",
"cfb_db_debug",
"cfb_db_reg_mask",
"cfb_strobe_reg",
"cfb_strobe_reg"]

#configuration constants
c_db_sm_reset_bit = 0;
c_mb1_reset_bit = 1;
c_mb0_reset_bit = 2;
c_master_reset_bit = 3;
c_clknet_reset_bit = 4;
c_commbus_reset_bit = 5;
c_cfgbus_reset_bit = 6;
c_adc_readout_reset_bit = 7;
c_sem_reset_bit = 8;
c_adc_config_reset_bit = 9;  
c_cis_reset_bit  = 10;  
c_integrator_reset_bit = 11;
c_gbt_reset_bit = 12; 
c_gth_reset_bit = 13;
c_adc_channel_reset_bit = 14;
c_gth_reset_tx_pll_and_datapath_bit = 15;
c_gth_reset_tx_datapath_bit = 16;
c_gth_buffbypass_tx_reset_bit = 17;
c_gth_buffbypass_tx_start_use_bit = 18;
c_adc_readout_reset_channel_0_bit= 19;
c_adc_readout_reset_channel_1_bit= 20;
c_adc_readout_reset_channel_2_bit= 21;
c_adc_readout_reset_channel_3_bit= 22;
c_adc_readout_reset_channel_4_bit= 23;
c_adc_readout_reset_channel_5_bit= 24;
c_gbt_ch0_reset_bit= 25; 
c_gbt_ch1_reset_bit= 26;
c_gth_ch0_reset_bit= 27; 
c_gth_ch1_reset_bit= 28;
c_gbt_encoder_reset_bit= 29;

c_db_debug_cis_tp_clk_mux = 9;
c_db_debug_adc_clk_mux = 10;
c_db_debug_gbtx_deskew_clk_mux = 8;
c_db_debug_mb_adc_config_mode = 11;
c_db_debug_mb_adc_config_trigger = 12;


#status constants
c_db_status_bcr_locked_bit =0;

c_adc_readout_status_adc0_missalignment_bit =1;
c_adc_readout_status_adc1_missalignment_bit =2;
c_adc_readout_status_adc2_missalignment_bit =3;
c_adc_readout_status_adc3_missalignment_bit =4;
c_adc_readout_status_adc4_missalignment_bit =5;
c_adc_readout_status_adc5_missalignment_bit =6;
c_db_status_mb_tx_collission_q0_bit =1;
c_db_status_mb_tx_collission_q1_bit =2;

#pgood
c_pgood_db_1v2_bit = 0;        
c_pgood_db_5v0_bit = 1;
c_pgood_db_1v5_bit = 2;
c_pgood_db_3v3_bit = 3;
c_pgood_db_0v95_bit = 4;
c_pgood_db_1v0_bit = 5;
c_pgood_db_1v8_bit = 6;
c_pgood_db_2v5_bit = 7;
c_pgood_mb_3v3_bit = 8;
c_pgood_mb_5v0_n_bit = 9;
c_pgood_mb_5v0_bit = 10;
c_pgood_mb_1v8_bit = 11;
c_pgood_mb_1v2_bit = 12;
c_pgood_mb_2v5_bit = 13;
c_pgood_mb_10v0_bit = 14; 


lut_pgood_labels = [
"pgood_db_1v2",
"pgood_db_5v0",
"pgood_db_1v5",
"pgood_db_3v3",
"pgood_db_0v95",
"pgood_db_1v0",
"pgood_db_1v8",
"pgood_db_2v5",
"pgood_mb_3v3",
"pgood_mb_5v0_n",
"pgood_mb_5v0",
"pgood_mb_1v8",
"pgood_mb_1v2",
"pgood_mb_2v5",
"pgood_mb_10v0"
]


#useful stuff

# Terminal control characters
char_line_up = '\033[1A'
char_line_clear = '\x1b[2K'

def format_number(number):
    """
    Converts a number string in decimal, binary (prefix '0b'), or hexadecimal (prefix '0x')
    into an integer.
    """
    number_str = str(number).lower()  # ensure consistent case
    if number_str.startswith('0b'):
        number_buffer = int(number_str, 2)
    elif number_str.startswith('0x'):
        number_buffer = int(number_str, 16)
    else:
        number_buffer = int(number_str)
    return number_buffer

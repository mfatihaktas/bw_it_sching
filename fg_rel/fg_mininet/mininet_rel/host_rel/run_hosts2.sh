#!/bin/bash

echo $1
sel=$1

###
C0D=1
P0D=2
P0_REQDICT='{"data_size":100,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P0_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P0_CLIP=10.0.1.0

C1D=1
P1D=7
P1_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P1_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P1_CLIP=10.0.1.1

C2D=1
P2D=12
P2_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P2_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P2_CLIP=10.0.1.2

C3D=1
P3D=20
P3_REQDICT='{"data_size":100,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P3_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P3_CLIP=10.0.1.3

C4D=1
P4D=100
P4_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P4_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P4_CLIP=10.0.1.4

C5D=1
P5D=110
P5_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P5_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P5_CLIP=10.0.1.5

C6D=1
P6D=120
P6_REQDICT='{"data_size":20,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P6_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P6_CLIP=10.0.1.6

C7D=1
P7D=130
P7_REQDICT='{"data_size":80,"slack_metric":150,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P7_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P7_CLIP=10.0.1.7

C8D=1
P8D=235
P8_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P8_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P8_CLIP=10.0.1.8

C9D=1
P9D=240
P9_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P9_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P9_CLIP=10.0.1.9

#extra <down path>
###
C20D=1
P20D=3
P20_REQDICT='{"data_size":100,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P20_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P20_CLIP=10.0.1.20

C21D=1
P21D=8
P21_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P21_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P21_CLIP=10.0.1.21

C22D=1
P22D=13
P22_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P22_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P22_CLIP=10.0.1.22

C23D=1
P23D=21
P23_REQDICT='{"data_size":100,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P23_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P23_CLIP=10.0.1.23

C24D=1
P24D=101
P24_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P24_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P24_CLIP=10.0.1.24

C25D=1
P25D=111
P25_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P25_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P25_CLIP=10.0.1.25

C26D=1
P26D=121
P26_REQDICT='{"data_size":20,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P26_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P26_CLIP=10.0.1.26

C27D=1
P27D=131
P27_REQDICT='{"data_size":80,"slack_metric":150,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P27_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P27_CLIP=10.0.1.27

C28D=1
P28D=236
P28_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P28_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P28_CLIP=10.0.1.28

C29D=1
P29D=241
P29_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P29_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P29_CLIP=10.0.1.29


MINHTBDIR='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'

if [ ${sel:0:1}  = 'p' ]; then
  i=${sel:1}
  dvar='P'$i'D'
  sleep ${!dvar}
  
  reqdictvar='P'$i'_REQDICT'
  appprefvar='P'$i'_APPPREFDICT'
  clipvar='P'$i'_CLIP'
  python producer.py --intf=$sel'-eth0' --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=${!clipvar} \
                     --proto=tcp --tx_type=fastdata --file_url=ltx1.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp --logto=file --nodename=$sel \
                     --req_dict=${!reqdictvar} --app_pref_dict=${!appprefvar} --htbdir=$MINHTBDIR
elif [ ${sel:0:1}  = 'c' ]; then
  i=${sel:1}
  dvar='C'$i'D'
  sleep ${!dvar}
  python consumer.py --intf=$sel'-eth0' --cl_port_list=6000 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=file --nodename=$sel
elif [ ${sel:0:1}  = 't' ]; then
  python transit.py --nodename=$sel --intf=$sel'-eth0' --htbdir=$MINHTBDIR --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
else
  echo "Argument did not match !"
fi

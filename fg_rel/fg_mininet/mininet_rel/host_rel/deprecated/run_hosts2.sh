#!/bin/bash

sel=$1
###
C1D=1
P1D=2
P1_REQDICT='{"data_size":100,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P1_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P1_CLIP=10.0.1.0

C2D=1
P2D=7
P2_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P2_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P2_CLIP=10.0.1.1

C3D=1
P3D=12
P3_REQDICT='{"data_size":10,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P3_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P3_CLIP=10.0.1.2

C4D=1
P4D=20
P4_REQDICT='{"data_size":100,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P4_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P4_CLIP=10.0.1.3

C5D=1
P5D=100
P5_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P5_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P5_CLIP=10.0.1.4

C6D=1
P6D=110
P6_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P6_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P6_CLIP=10.0.1.5

C7D=1
P7D=120
P7_REQDICT='{"data_size":20,"slack_metric":400,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P7_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P7_CLIP=10.0.1.6

C8D=1
P8D=130
P8_REQDICT='{"data_size":80,"slack_metric":150,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P8_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P8_CLIP=10.0.1.7

C9D=1
P9D=235
P9_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P9_APPPREFDICT='{"m_p":0.5,"m_u":0.5,"x_p":0,"x_u":0}'
P9_CLIP=10.0.1.8

C10D=1
P10D=240
P10_REQDICT='{"data_size":20,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P10_APPPREFDICT='{"m_p":2,"m_u":2,"x_p":0,"x_u":0}'
P10_CLIP=10.0.1.9

C11D=1
P11D=245
P11_REQDICT='{"data_size":20,"slack_metric":50,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P11_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P11_CLIP=10.0.1.10
#extra <down path>

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

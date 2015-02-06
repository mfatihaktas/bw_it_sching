#!/bin/bash

echo $1
sel=$1

C1D=1
P1D=4
P1_REQDICT='{"datasize":88,"slack_metric":118,"func_list":["fft","upsampleplot"]}'
P1_APPPREFDICT='{"m_p":10,"m_u":0,"x_p":0,"x_u":0}'
P1_CLIP=10.0.1.0

C2D=1
P2D=40
P2_REQDICT='{"datasize":71,"slack_metric":106,"func_list":["fft","upsampleplot"]}'
P2_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P2_CLIP=10.0.1.1

C3D=1
P3D=60
P3_REQDICT='{"datasize":88,"slack_metric":145,"func_list":["fft","upsampleplot"]}'
P3_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P3_CLIP=10.0.1.2

C4D=1
P4D=80
P4_REQDICT='{"datasize":67,"slack_metric":95,"func_list":["fft","upsampleplot"]}'
P4_APPPREFDICT='{"m_p":1,"m_u":10,"x_p":0,"x_u":0}'
P4_CLIP=10.0.1.3

C5D=1
P5D=220
P5_REQDICT='{"datasize":30,"slack_metric":44,"func_list":["fft","upsampleplot"]}'
P5_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P5_CLIP=10.0.1.4

C6D=1
P6D=238
P6_REQDICT='{"datasize":70,"slack_metric":108,"func_list":["fft","upsampleplot"]}'
P6_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P6_CLIP=10.0.1.5

C7D=1
P7D=285
P7_REQDICT='{"datasize":66,"slack_metric":122,"func_list":["fft","upsampleplot"]}'
P7_APPPREFDICT='{"m_p":10,"m_u":1,"x_p":0,"x_u":0}'
P7_CLIP=10.0.1.6

C8D=1
P8D=293
P8_REQDICT='{"datasize":84,"slack_metric":125,"func_list":["fft","upsampleplot"]}'
P8_APPPREFDICT='{"m_p":1,"m_u":10,"x_p":0,"x_u":0}'
P8_CLIP=10.0.1.7

C9D=1
P9D=328
P9_REQDICT='{"datasize":49,"slack_metric":80,"func_list":["fft","upsampleplot"]}'
P9_APPPREFDICT='{"m_p":1,"m_u":10,"x_p":0,"x_u":0}'
P9_CLIP=10.0.1.8

C10D=1
P10D=335
P10_REQDICT='{"datasize":62,"slack_metric":101,"func_list":["fft","upsampleplot"]}'
P10_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P10_CLIP=10.0.1.9

C11D=1
P11D=376
P11_REQDICT='{"datasize":53,"slack_metric":87,"func_list":["fft","upsampleplot"]}'
P11_APPPREFDICT='{"m_p":10,"m_u":1,"x_p":0,"x_u":0}'
P11_CLIP=10.0.1.10

if [ ${sel:0:1}  = 'p' ]; then
  i=${sel:1}
  dvar='P'$i'D'
  sleep ${!dvar}
  
  reqdictvar='P'$i'_REQDICT'
  appprefvar='P'$i'_APPPREFDICT'
  clipvar='P'$i'_CLIP'
  python producer.py --intf=$sel'-eth0' --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=${!clipvar} \
                     --proto=tcp --tx_type=fastdata --file_url=ltx1.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp \
                     --logto=file --nodename=$sel --req_dict=${!reqdictvar} --app_pref_dict=${!appprefvar} \
                     --htbdir=$MINHTBDIR
elif [ ${sel:0:1}  = 'c' ]; then
  i=${sel:1}
  dvar='C'$i'D'
  sleep ${!dvar}
  python consumer.py --intf=$sel'-eth0' --cl_port_list=6000 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=file --nodename=$sel
elif [ ${sel:0:1}  = 't' ]; then
  python transit.py --nodename=$sel --intf=$sel'-eth0' --htbdir=$MINHTBDIR --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 'k' ]; then
  sudo pkill -f sleep
  echo 'sleeps are killed'
  sudo pkill -f transit
  echo 'transits are killed'
  sudo pkill -f producer
  echo 'producers are killed'
  sudo pkill -f consumer
  echo 'consumers are killed'
  sudo pkill -f run_hosts
  echo 'run_hosts are killed'
  #sudo pkill -f eceiproc
else
  echo "Argument did not match !"
fi

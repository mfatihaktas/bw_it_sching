#!/bin/bash
# Port conventions and mappings:
# for transit P t{?} -> l_port:90{?}
# TCPServer running at controller1 -> port: 9999
# TCPServer running at scheduler   -> port: 9998
echo $1
sel=$1

DS=20

C1D=1
P1D=2
P1_REQDICT='{"data_size":20,"slack_metric":30,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P1_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P1_CLIP=10.0.1.0

C2D=1
P2D=7
P2_REQDICT='{"data_size":10,"slack_metric":15,"func_list":["fft"],"parism_level":1,"par_share":[1]}'
P2_APPPREFDICT='{"m_p":0.1,"m_u":0.1,"x_p":0,"x_u":0}'
P2_CLIP=10.0.1.1

C3D=1
P3D=12
P3_REQDICT='{"data_size":10,"slack_metric":15,"func_list":["fft"],"parism_level":1,"par_share":[1]}'
P3_APPPREFDICT='{"m_p":10,"m_u":10,"x_p":0,"x_u":0}'
P3_CLIP=10.0.1.2

C4D=1
P4D=20
P4_REQDICT='{"data_size":100,"slack_metric":200,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P4_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P4_CLIP=10.0.1.3

C5D=1
P5D=100
P5_REQDICT='{"data_size":40,"slack_metric":120,"func_list":["fft"],"parism_level":1,"par_share":[1]}'
P5_APPPREFDICT='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}'
P5_CLIP=10.0.1.4

C6D=1
P6D=110
P6_REQDICT='{"data_size":40,"slack_metric":1000,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}'
P6_APPPREFDICT='{"m_p":0.1,"m_u":0.1,"x_p":0,"x_u":0}'
P6_CLIP=10.0.1.5

MINHTBDIR='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'

if [ $1  = 'p' ]; then
  python producer.py --intf=p-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.0.1 \
                     --proto=tcp --tx_type=file --file_url=ltx.dat --kstardata_url=... --logto=console --nodename=p \
                     --req_dict='{"data_size":1,"slack_metric":10,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
                     --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
                     --htbdir='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
elif [ ${sel:0:1}  = 'p' ]; then
  i=${sel:1:1}
  dvar='P'$i'D'
  sleep ${!dvar}
  
  reqdictvar='P'$i'_REQDICT'
  appprefvar='P'$i'_APPPREFDICT'
  clipvar='P'$i'_CLIP'
  python producer.py --intf=$sel'-eth0' --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=${!clipvar} \
                     --proto=tcp --tx_type=kstardata --file_url=ltx1.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp --logto=file --nodename=$sel \
                     --req_dict=${!reqdictvar} --app_pref_dict=${!appprefvar} --htbdir=$MINHTBDIR
elif [ $1  = 'c' ]; then
  python consumer.py --intf=lo --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=console --nodename=mfa
elif [ ${sel:0:1}  = 'c' ]; then
  i=${sel:1:1}
  dvar='C'$i'D'
  sleep ${!dvar}
  python consumer.py --intf=$sel'-eth0' --cl_port_list=6000 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=file --nodename=$sel
elif [ $1  = 't' ]; then
  python transit.py --nodename=t --intf=lo --htbdir=$MINHTBDIR --dtsl_ip=127.0.0.1 --dtsl_port=7002 --dtst_port=7001 --logto=file --trans_type=file
elif [ ${sel:0:1}  = 't' ]; then
  python transit.py --nodename=$sel --intf=$sel'-eth0' --htbdir=$MINHTBDIR --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 's' ]; then
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=file --file_url=ltx.dat --logto=console --kstardata_url=/media/portable_large/large_ecei_data.bp
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/home/ubuntu/large_ecei_data.bp
  python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console  --kstardata_url=/media/portable_large/large_ecei_data.bp
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/media/mehmet/portable_large/large_ecei_data.bp
elif [ ${sel:0:1}  = 's' ]; then
  python sender.py --dst_ip=127.0.0.1 --dst_lport=${sel:1} --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/home/ubuntu/large_ecei_data.bp
elif [ $1  = 'r' ]; then
  #python receiver.py --lintf=lo --lport=6000 --proto=tcp --rx_type=dummy --file_url=rx.dat --logto=console
  python receiver.py --lintf=lo --lport=6000 --proto=tcp --rx_type=kstardata --file_url=/home/mehmet/Desktop/rx.dat --logto=console
elif [ $1  = 'glf' ]; then
	dd if=/dev/urandom of=ltx.dat bs=1728 count=10000 #outputs bs x count Bs 
elif [ $1  = 'k' ]; then
  #sudo rm -r /tmp/fft6*; mkdir /tmp/fft6000; mkdir /tmp/fft6001
  #sudo rm -r /tmp/upsampleplot6*; mkdir /tmp/upsampleplot6000; mkdir /tmp/upsampleplot6001
  #sudo rm /tmp/fft*; sudo rm /tmp/upsampleplot*
  sudo pkill -f transit
  sudo pkill -f producer
  sudo pkill -f consumer
  sudo pkill -f eceiproc
  sudo pkill python
elif [ $1  = 'den' ]; then
  g++ deneme.c -o deneme
  ./deneme
  #echo "denememe" | ./deneme
  #dd if=/dev/zero of=stdout bs=1024 count=1 | ./deneme
  #python deneme.py | ./deneme
elif [ $1  = 'ep' ]; then
  make eceiproc
  #./eceiproc --datafname "/media/portable_large/ecei_data.bp" \
  #           --outdir "/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/companalysis" \
  #           --compfname "fft_1.dat"
elif [ $1  = 'ep2' ]; then
  make eceiproc2
  ./eceiproc2 --stpdst=6000
elif [ $1  = 'ep2m' ]; then
  make eceiproc2
  ./eceiproc2 --stpdst=6000 > logs/eceiproc2.log
else
	echo "Argument did not match !"
fi

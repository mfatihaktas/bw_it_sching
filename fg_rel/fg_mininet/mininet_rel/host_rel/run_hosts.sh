#!/bin/bash
# Port conventions and mappings:
# for transit P t{?} -> l_port:90{?}
# TCPServer running at controller1 -> port: 9999
# TCPServer running at scheduler   -> port: 9998
echo $1

DS=20

if [ $1  = 'p' ]; then
  python producer.py --intf=p-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.0.1 \
                     --proto=tcp --tx_type=file --file_url=ltx.dat --kstardata_url=... --logto=console \
                     --req_dict='{"data_size":1,"slack_metric":1000,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
                     --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
                     --htbdir='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
elif [ $1  = 'p1' ]; then
  #python producer.py --intf=p1-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.1.0 \
  #                   --proto=tcp --tx_type=kstardata --file_url=ltx1.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp --logto=console \
  #                   --req_dict='{"data_size":1,"slack_metric":1000,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}' \
  #                   --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
  #                   --htbdir='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
  python producer.py --intf=p1-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.1.0 \
                     --proto=tcp --tx_type=kstardata --file_url=ltx1.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp --logto=console \
                     --req_dict='{"data_size":20,"slack_metric":25000,"func_list":["fft", "upsampleplot"],"parism_level":1,"par_share":[1]}' \
                     --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
                     --htbdir='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
elif [ $1  = 'p2' ]; then
  python producer.py --intf=p2-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.1.1 \
                     --proto=tcp --tx_type=kstardata --file_url=ltx2.dat --kstardata_url=/home/ubuntu/large_ecei_data.bp --logto=console \
                     --req_dict='{"data_size":1,"slack_metric":1000,"func_list":["fft","upsampleplot"],"parism_level":1,"par_share":[1]}' \
                     --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
                     --htbdir='/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
elif [ $1  = 'c' ]; then
  python consumer.py --intf=lo --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=console
  #python consumer.py --intf=c-eth0 --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
  #                   --proto=tcp --rx_type=dummy --logto=console
elif [ $1  = 'c1' ]; then
  python consumer.py --intf=c1-eth0 --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=console
elif [ $1  = 'c2' ]; then
  python consumer.py --intf=c2-eth0 --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=kstardata --logto=console
elif [ $1  = 't' ]; then
  python transit.py --nodename=mfa --intf=lo --dtsl_ip=127.0.0.1 --dtsl_port=7002 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 't11' ]; then
  python transit.py --nodename=t11 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 't21' ]; then
	python transit.py --nodename=t21 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 't31' ]; then
  python transit.py --nodename=t31 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 's' ]; then
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=file --file_url=ltx.dat --logto=console --kstardata_url=/media/portable_large/large_ecei_data.bp
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/home/ubuntu/large_ecei_data.bp
  python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console  --kstardata_url=/media/portable_large/large_ecei_data.bp
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/media/mehmet/portable_large/large_ecei_data.bp
elif [ $1  = 's6000' ]; then
  python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/home/ubuntu/large_ecei_data.bp
elif [ $1  = 's6001' ]; then
  python sender.py --dst_ip=127.0.0.1 --dst_lport=6001 --datasize=$DS --proto=tcp --tx_type=kstardata --file_url=ltx.dat --logto=console --kstardata_url=/home/ubuntu/large_ecei_data.bp
elif [ $1  = 'r' ]; then
  #python receiver.py --lintf=lo --lport=6000 --proto=tcp --rx_type=dummy --file_url=rx.dat --logto=console
  python receiver.py --lintf=lo --lport=6000 --proto=tcp --rx_type=kstardata --file_url=/home/mehmet/Desktop/rx.dat --logto=console
elif [ $1  = 'glf' ]; then
	dd if=/dev/urandom of=ltx.dat bs=1728 count=10000 #outputs bs x count Bs 
elif [ $1  = 'pexp' ]; then
  #python producer.py --intf=p-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.0.1 \
  #                   --proto=tcp --tx_type=dummy --file_url=ltx.dat --logto=file \
  #                   --req_dict='{"data_size":100,"slack_metric":1050,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
  #                   --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
  #                   --htbdir='/home/mininet/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
  echo "p1"
  sleep 2
  echo "p2"
  sleep 2
  echo "p3"
#eceiprocing
elif [ $1  = 'den' ]; then
  g++ deneme.c -o deneme
  ./deneme
  #echo "denememe" | ./deneme
  #dd if=/dev/zero of=stdout bs=1024 count=1 | ./deneme
  #python deneme.py | ./deneme
elif [ $1  = 'ep' ]; then
  make eceiproc
  ./eceiproc --datafname "/media/portable_large/ecei_data.bp" \
             --outdir "/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/companalysis" \
             --compfname "fft_1.dat"
elif [ $1  = 'ep2' ]; then
  make eceiproc2
  ./eceiproc2 --stpdst=6000
  
else
	echo "Argument did not match !"
fi

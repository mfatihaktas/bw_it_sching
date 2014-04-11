#!/bin/bash
# Port conventions and mappings:
# for transit P t{?} -> l_port:90{?}
# TCPServer running at controller1 -> port: 9999
# TCPServer running at scheduler   -> port: 9998
echo $1

if [ $1  = 'p' ]; then
  #python producer.py --intf=lo --dtst_port=7000 --dtsl_ip=127.0.0.1 --dtsl_port=7000 --cl_ip=127.0.0.1 \
  #                   --proto=udp --tx_type=dummy --file_url=ltx.dat --logto=console \
  #                   --req_dict='{"data_size":1,"slack_metric":24,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
  #                   --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
  #                   --htbdir='/home/mehmet/Dropbox/sim_rel/net_config/mininet_rel/host_rel/tc_rel/htb_rel'
  
  python producer.py --intf=p-eth0 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 --cl_ip=10.0.0.1 \
                     --proto=tcp --tx_type=dummy --file_url=ltx.dat --logto=file \
                     --req_dict='{"data_size":100,"slack_metric":1050,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
                     --app_pref_dict='{"m_p":1,"m_u":1,"x_p":0,"x_u":0}' \
                     --htbdir='/home/mininet/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
                     #--req_dict='{"data_size":4,"slack_metric":24,"func_list":["f1","f2","f3"],"parism_level":1,"par_share":[1]}' \
elif [ $1  = 'c' ]; then
  #python consumer.py --intf=lo --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
  #                   --proto=udp --rx_type=dummy --logto=console
  python consumer.py --intf=c-eth0 --cl_port_list=6000,6001,6002 --dtst_port=7000 --dtsl_ip=10.0.0.255 --dtsl_port=7000 \
                     --proto=tcp --rx_type=dummy --logto=console
elif [ $1  = 't' ]; then
  python transit.py --nodename=mfa --intf=lo --dtsl_ip=127.0.0.1 --dtsl_port=7002 --dtst_port=7001 --logto=file --trans_type=file
elif [ $1  = 't11' ]; then
  python transit.py --nodename=t11 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file
elif [ $1  = 't21' ]; then
	python transit.py --nodename=t21 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file
elif [ $1  = 't31' ]; then
  python transit.py --nodename=t31 --intf=eth0 --dtsl_ip=10.0.0.255 --dtsl_port=7001 --dtst_port=7001 --logto=file
elif [ $1  = 's' ]; then
  #python sender.py --dst_ip=127.0.0.1 --dst_lport=7001 --datasize=1 --proto=udp --tx_type=dummy --file_url=ltx.dat --logto=console
  python sender.py --dst_ip=127.0.0.1 --dst_lport=6000 --datasize=20 --proto=tcp --tx_type=file --file_url=ltx.dat --logto=console
elif [ $1  = 'r' ]; then
  #python receiver.py --lintf=t11-eth0 --lport=6000 --proto=tcp --rx_type=dummy --file_url=rx.dat
  python receiver.py --lintf=lo --lport=6000 --proto=tcp --rx_type=file --file_url=rx.dat --logto=console
elif [ $1  = 'sp' ]; then
  #python sender.py --dst_ip=10.0.0.111 --dst_lport=6000 --datasize=100 --proto=tcp --tx_type=dummy --file_url=ltx.dat --logto=console
  python sender.py --dst_ip=10.0.0.111 --dst_lport=6000 --datasize=100 --proto=tcp --tx_type=file --file_url=ltx.dat --logto=console
elif [ $1  = 'rd' ]; then
  #python receiver.py --lintf=d-eth0 --lport=6000 --proto=tcp --rx_type=dummy --file_url=rx.dat --logto=console
  python receiver.py --lintf=d-eth0 --lport=6000 --proto=tcp --rx_type=file --file_url=rx.dat --logto=console
elif [ $1  = 'rc' ]; then
  python receiver.py --lintf=c-eth0 --lport=6000 --proto=tcp --rx_type=dummy --file_url=rx.dat --logto=console
elif [ $1  = 'glf' ]; then
	dd if=/dev/urandom of=ltx.dat bs=1024 count=100 #1024
elif [ $1  = 'iperf-ts1' ]; then
  iperf -s -p 6000
elif [ $1  = 'iperf-tc1' ]; then
  iperf -c 10.0.0.111 -p 6000 -t 10
elif [ $1  = 'iperf-ts2' ]; then
  iperf -s -p 6001
elif [ $1  = 'iperf-tc2' ]; then
  iperf -c 10.0.0.111 -p 6001 -t 10
elif [ $1  = 'iperf-us' ]; then
  iperf -u -s -B 10.0.0.111 -p 6000
elif [ $1  = 'iperf-uc' ]; then
  iperf -u -c 10.0.0.111 -p 6000 -n 100000
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

else
	echo "Argument did not match !"
fi

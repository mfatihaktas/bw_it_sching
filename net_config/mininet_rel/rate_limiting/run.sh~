#!/bin/bash
echo $1
SW="s11"
DEV="eth3"
if [ $1  = 'show' ]
then
  sudo ovs-vsctl show
elif [ $1  = 'cq' ]
then
  sudo ovs-vsctl -- set Port $SW-$DEV qos=@newqos \
            -- --id=@newqos create QoS type=linux-htb other-config:max-rate=500 queues=0=@q0,1=@q1 \
            -- --id=@q0 create Queue other-config:min-rate=100 other-config:max-rate=100 \
            -- --id=@q1 create Queue other-config:min-rate=400 other-config:max-rate=400
  #rate=<>Kbps
  #other-config:min-rate=50 
elif [ $1  = 'dcq' ]
then
  #sudo ovs-vsctl clear Port $SW-$DEV qos
  #disconnection mentioned in mailing_list
  #sudo ovs-vsctl clear qos $SW-$DEV queues
  sudo ovs-vsctl -- destroy QoS $SW-$DEV -- clear Port $SW-$DEV qos
  #sudo ovs-vsctl clear Port $SW-$DEV qos
elif [ $1  = 'killall' ] #as last hope...
then
  sudo ovs-vsctl -- --all destroy Port
  sudo ovs-vsctl -- --all destroy QoS
  sudo ovs-vsctl -- --all destroy Queue
elif [ $1  = 'lsq' ]
then
  sudo ovs-vsctl list Queue
  sudo ovs-ofctl queue-stats $SW
elif [ $1  = 'afq' ]
then
  sudo ovs-ofctl add-flow $SW "in_port=1 dl_type=0x0800 nw_proto=17 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6000 idle_timeout=0 actions=enqueue:3:0,output:3"
  sudo ovs-ofctl add-flow $SW "in_port=3 dl_type=0x0800 nw_proto=17 nw_src=10.0.0.111 nw_dst=10.0.0.2 tp_dst=6000 idle_timeout=0 actions=output:1"
  
  sudo ovs-ofctl add-flow $SW "in_port=1 dl_type=0x0800 nw_proto=17 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6001 idle_timeout=0 actions=enqueue:3:1,output:3"
  sudo ovs-ofctl add-flow $SW "in_port=3 dl_type=0x0800 nw_proto=17 nw_src=10.0.0.111 nw_dst=10.0.0.2 tp_dst=6001 idle_timeout=0 actions=output:1"
elif [ $1  = 'af' ]
then
  #sudo ovs-ofctl add-flow $SW "in_port=1 dl_type=0x0800 nw_proto=6 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6000 idle_timeout=0 actions=enqueue:3:0,output:3"
  #sudo ovs-ofctl add-flow $SW "in_port=3 dl_type=0x0800 nw_proto=6 nw_src=10.0.0.111 nw_dst=10.0.0.2 tp_dst=6000 idle_timeout=0 actions=output:1"
  #sudo ovs-ofctl add-flow $SW "in_port=1 dl_type=0x0800 nw_proto=6 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6001 idle_timeout=0 actions=enqueue:3:1,output:3"
  #sudo ovs-ofctl add-flow $SW "in_port=3 dl_type=0x0800 nw_proto=6 nw_src=10.0.0.111 nw_dst=10.0.0.2 tp_dst=6001 idle_timeout=0 actions=output:1"
  
  #sudo ovs-ofctl add-flow $SW "in_port=1 ip nw_proto=6 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6000 idle_timeout=0 actions=enqueue:3:0,output:3"
  #sudo ovs-ofctl add-flow $SW "in_port=1 ip nw_proto=6 nw_src=10.0.0.2 nw_dst=10.0.0.111 tp_dst=6001 idle_timeout=0 actions=enqueue:3:1,output:3"
  #sudo ovs-ofctl add-flow $SW "in_port=3 ip idle_timeout=0 actions=output:1"
  #sudo ovs-ofctl add-flow $SW "in_port=1 ip idle_timeout=0 actions=output:3"
  
  sudo ovs-ofctl add-flow $SW "in_port=1 idle_timeout=0 actions=output:3"
  sudo ovs-ofctl add-flow $SW "in_port=3 idle_timeout=0 actions=output:1"
elif [ $1  = 'rf' ]
then
  sudo ovs-ofctl del-flows $SW "ip"
elif [ $1  = 'ct' ]
then
  sudo ovs-ofctl del-flows $SW
elif [ $1  = 'df' ]
then
  sudo ovs-ofctl dump-flows $SW
else
  echo "Argument did not match !"
fi

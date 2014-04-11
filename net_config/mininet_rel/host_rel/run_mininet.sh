echo $1

SW=$2 #s11
GRE_PORT=3

echo "for SW=$SW"

if [ $1  = 'init' ]; then
  sudo python net_2p_stwithsingleitr.py
  #mn --custom ~/mininet/custom/topo-2sw-2host.py --topo mytopo
elif [ $1 = 'dp' ]; then
  sudo ovs-ofctl dump-ports-desc $SW
elif [ $1 = 'af' ]; then
  #flow btw n01-n02
  #sudo ovs-ofctl add-flow $SW "in_port=$GRE_PORT ip idle_timeout=0 actions=output:1"
  #sudo ovs-ofctl add-flow $SW "in_port=1 ip idle_timeout=0 actions=output:$GRE_PORT"

  #sudo ovs-ofctl add-flow $SW "in_port=$GRE_PORT ip idle_timeout=0 actions=output:2"
  #sudo ovs-ofctl add-flow $SW "in_port=2 ip idle_timeout=0 actions=output:$GRE_PORT"
  #dummy flow btw mininet hosts
  sudo ovs-ofctl add-flow $SW "in_port=1 ip idle_timeout=0 actions=output:3"
  sudo ovs-ofctl add-flow $SW "in_port=3 ip idle_timeout=0 actions=output:1"
  #6:tcp, 17:udp
  #sudo ovs-ofctl add-flow $SW "in_port=1 dl_type=0x0800 nw_src=10.0.0.2 nw_dst=10.0.0.1 nw_proto=6 tp_dst=6000 idle_timeout=0 actions=mod_dl_dst:00:00:00:00:11:01,mod_nw_dst:10.0.0.111,output:3"
  #sudo ovs-ofctl add-flow $SW "in_port=3 dl_type=0x0800 nw_src=10.0.0.111 nw_dst=10.0.0.2 nw_proto=6 tp_src=6000 idle_timeout=0 actions=mod_dl_src:00:00:00:01:00:01,mod_nw_src:10.0.0.1,output:1"

elif [ $1  = 'df' ]
then
  sudo ovs-ofctl dump-flows $SW
elif [ $1  = 'rf' ]
then
  sudo ovs-ofctl del-flows $SW "ip"
elif [ $1  = 'ct' ]
then
  sudo ovs-ofctl del-flows $SW
elif [ $1 = 'show' ]; then
  sudo ovs-vsctl show
elif [ $1  = 'makegre' ]; then
  sudo ovs-vsctl add-port $SW $SW-gre1 -- set interface $SW-gre1 type=gre options:remote_ip=$N02_IP
elif [ $1  = 'delgre' ]; then
  sudo ovs-vctl del-port $SW $SW-gre1
else
  echo "Argument did not match !"
fi


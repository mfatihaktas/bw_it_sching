#!/bin/bash

MFADEV='lo'
MFADIR='/home/mehmet/Dropbox/sim_rel/net_config/mininet_rel/host_rel/tc_rel/htb_rel/lo_'
#

PDEV='p-eth0'
PDIR='/home/mininet/mininet/mininet_rel/host_rel/tc_rel/htb_rel/p-eth0_'

CDEV='c-$DEV'
CDIR='/home/mininet/mininet/mininet_rel/host_rel/tc_rel/htb_rel'

if [ $2  = 'p' ]; then
  DIR=$PDIR
  DEV=$PDEV
  OPT='not_add_root'
elif [ $2  = 'c' ]; then
  DIR=$CDIR
  DEV=$CDEV
  OPT='not_add_root'
elif [ $2  = 'm' ]; then
  DIR=$MFADIR
  DEV=$MFADEV
  OPT='add_root'
else
  echo "unexpected nodeid=$2"
  exit
fi

echo "operating on $2"
ROOTID=5

if [ $1  = 'conf' ]; then
    sudo ./htb.init.sh start invalidate $DEV $DIR $OPT
    #somehow! netem qdisc as root_class_leaf is disappearing after adding other classes
    # adding netem qdisc...
    #sudo tc qdisc add dev $DEV parent $ROOTID:1 handle 10 netem delay 100ms

elif [ $1  = 'dconf' ]; then
    #sudo tc filter del dev $DEV parent 1: protocol ip prio 100 u32
    #sudo tc class del dev $DEV parent 1:2 classid 1:10
    #sudo tc class del dev $DEV parent 1:2 classid 1:20
    #sudo tc class del dev $DEV parent 1: classid 1:2
    
    sudo tc qdisc del dev $DEV root
elif [ $1  = 'show' ]; then
  #sudo ./htb.init.sh stats
  echo "> qdiscs:"
  tc -s -p qdisc show dev $DEV
  echo "> classes:"
  tc -s -p class show dev $DEV
  echo "> filters:"
  tc -s -p filter show dev $DEV
elif [ $1  = 'minstop' ]; then
  sudo ./htb.init.sh minstop ... $DEV $DIR
elif [ $1  = 'root' ]; then
  sudo ./htb.init.sh start invalidate $DEV $DIR $OPT
  sudo ./htb.init.sh minstop ... $DEV $DIR
  #sudo tc class del dev $DEV parent 1:1 classid 1:2
elif [ $1  = 'exp' ]; then
  #sudo tc qdisc add dev $DEV root handle 1: prio
  #sudo tc qdisc add dev $DEV parent 1:3 handle 30: \
  #  tbf rate 20kbit buffer 1600 limit  3000
  #sudo tc qdisc add dev $DEV parent 30:1 handle 31: \
  #  netem  delay 200ms 10ms distribution normal
  #sudo tc filter add dev $DEV protocol ip parent 1:0 prio 3 u32 \
  #   match ip dst 65.172.181.4/32 flowid 1:3
  
  sudo tc qdisc add dev $DEV parent 5:20 handle 20 netem delay 100ms
  #working below
  #sudo tc qdisc add dev $DEV parent 5:10 handle 30 netem delay 100ms
    
else
  echo "1st arg did not match !"
fi

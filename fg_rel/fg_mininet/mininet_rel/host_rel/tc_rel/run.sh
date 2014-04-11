#!/bin/bash
#for classless qdisc conf
echo $1
DEV="lo"

if [ $1  = 'conf' ]
then
  sudo tc qdisc add dev $DEV root tbf rate 1mbit \
                                  burst 5kb \
                                  peakrate 2mbit \
                                  minburst 1540 \
                                  latency 100ms
elif [ $1  = 'dconf' ]
then
  sudo tc qdisc del dev $DEV root
elif [ $1  = 'show' ]
then
  echo "> qdiscs:"
  tc -s -p qdisc show dev $DEV
  echo "> classes:"
  tc -s -p class show dev $DEV
  echo "> filters:"
  tc -s -p filter show dev $DEV
else
  echo "Argument did not match !"
fi

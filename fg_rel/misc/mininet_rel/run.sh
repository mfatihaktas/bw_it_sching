#!/bin/bash

#basic commands to run mininet_vm in openstack_india

echo $1

KEY=mfa51-key
VMNAME=mininet
VMIMG_FILE=mininet-ops-vm.img
FLV=m1.small
VMUSERNAME=mininet

PIVVMIP=10.39.1.46
PUBVMIP=149.165.159.16

if [ $1  = 'init' ]; then
  module load euca2ools
  source ~/.futuregrid/openstack_havana/novarc
elif [ $1  = 'ui' ]; then
  #upload img
  euca-bundle-image -i $VMIMG_FILE
else
	echo "Argument did not match !"
fi

#!/bin/bash

#basic commands to run vm in openstack_india
echo "1="$1 "2="$2

KEYDIR=~/.ssh/mininet-key #mfa51-key
KEY=mininet-key #mfa51-key
FLV=m1.xlarge #m1.xlarge medium

VMNAME=mfa51-001
VMUSERNAME=ubuntu
VMIMG=futuregrid/ubuntu-12.04
VM_PIVIP=10.39.1.46
VM_PUBIP=149.165.159.16

EXPCONT_VMNAME=exp_controller
EXPCONT_VMIMG=controller
EXPCONT_VMUSERNAME=ubuntu
EXPCONT_VMPIVIP=10.39.1.46
EXPCONT_VMPUBIP=149.165.159.47

#mininet_(1 2 3 4 5) -> net_s_(1 2 3 11 12)
#mininet_(1 2 3) -> net_s_(1)
VM_NAMES=( controller mininet1 mininet2 mininet3 mininet4 mininet5 )
VM_USRNAMES=( ubuntu ubuntu ubuntu ubuntu ubuntu ubuntu )
VM_PIVIPS=( 10.39.1.18 10.39.1.14 10.39.1.26 10.39.1.52 10.39.1.63 10.39.1.65 )
VM_PUBIPS=( 149.165.159.11 149.165.159.15 149.165.159.31 149.165.159.37 149.165.159.38 149.165.159.39 )

if [ $1  = 'init' ]; then
  module load novaclient
  source ~/.futuregrid/openstack_havana/novarc
elif [ $1  = 'lsf' ]; then
  nova flavor-list
elif [ $1  = 'lsi' ]; then
  nova image-list
elif [ $1  = 'lsvms' ]; then
  #ls running vms
  nova list
#cmds for vm
elif [ $1  = 'snapvm' ]; then
  #$3 = instance id
  echo "instance: $3"
  nova image-create $3 ${VM_NAMES[$2]}
elif [ $1  = 'uvmi' ]; then
  if [ $2  = -1 ]; then
    nova image-delete $EXPCONT_VMNAME
    nova image-create $EXPCONT_VMNAME $EXPCONT_VMNAME
    # nova image-delete $VMNAME
    # nova image-create $VMNAME $VMNAME
  else
    nova image-delete ${VM_NAMES[$2]}
    nova image-create ${VM_NAMES[$2]} ${VM_NAMES[$2]}
  fi
elif [ $1  = 'rmvmi' ]; then
  nova image-delete ${VM_NAMES[$2]}
elif [ $1  = 'bvm' ]; then
  if [ $2 -eq -1 ]; then
    nova boot --flavor $FLV \
              --image $EXPCONT_VMIMG \
              --key_name $KEY $EXPCONT_VMNAME
    # nova boot --flavor $FLV \
    #           --image $VMIMG \
    #           --key_name $KEY $VMNAME
  else
    nova boot --flavor $FLV \
              --image ${VM_NAMES[$2]} \
              --key_name $KEY ${VM_NAMES[$2]}
  fi
elif [ $1  = 'eavm' ]; then
  if [ $2 -eq -1 ]; then
    nova add-floating-ip $EXPCONT_VMNAME $EXPCONT_PUBIP
  else
    nova add-floating-ip ${VM_NAMES[$2]} ${VM_PUBIPS[$2]}
  fi
  nova floating-ip-list
elif [ $1  = 'rmvm' ]; then
  if [ $2 -eq -1 ]; then
    nova delete $EXPCONT_VMNAME
  else  
    nova delete ${VM_NAMES[$2]}
  fi
elif [ $1  = 'sshvm' ]; then
  if [ $2 -eq -1 ]; then
    ssh -v -l $EXPCONT_VMUSERNAME -i $KEYDIR $EXPCONT_PUBIP
  else
    ssh -v -l ${VM_USRNAMES[$2]} -i $KEYDIR ${VM_PIVIPS[$2]}
  fi
elif [ $1  = 'scprsa' ]; then
  cat ~/.ssh/id_rsa.pub | ssh -l ${VM_USRNAMES[$2]} -i $KEYDIR ${VM_PIVIPS[$2]} 'cat >> ~/.ssh/authorized_keys'
#cmds for vm bundle
elif [ $1  = 'bvms' ]; then
  for i in `seq 0 5`;
  do
    echo "vm_id=$i::"
    echo "booting..."
    nova boot --flavor $FLV \
              --image ${VM_NAMES[$i]} \
              --key_name $KEY ${VM_NAMES[$i]}
  done
elif [ $1  = 'eavms' ]; then
  for i in `seq 0 5`;
  do
    echo "vm_id=$i::"
    echo "external access..."
    nova add-floating-ip ${VM_NAMES[$i]} ${VM_PUBIPS[$i]}
  done

elif [ $1  = 'uvmis' ]; then
  for i in `seq 0 5`;
  do
    echo "vm_id=$i::"
    echo "updating..."
    nova image-delete ${VM_NAMES[$i]}
    nova image-create ${VM_NAMES[$i]} ${VM_NAMES[$i]}
  done

elif [ $1  = 'rmvms' ]; then
  for i in `seq 0 5`;
  do
    echo "vm_id=$i::"
    echo "removing..."
    nova delete ${VM_NAMES[$i]}
  done
else
	echo "Argument did not match !"
fi

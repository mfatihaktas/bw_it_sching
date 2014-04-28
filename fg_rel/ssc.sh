#!/bin/bash
echo $1

VMKEYDIR=./keys/mininet-key
VM_NAMES=( controller mininet1 mininet2 mininet3 mininet4 mininet5 )
VM_USRNAMES=( ubuntu ubuntu ubuntu ubuntu ubuntu ubuntu )
VM_PIVIPS=( 10.39.1.2 10.39.1.14 10.39.1.26 10.39.1.52 10.39.1.63 10.39.1.65)
VM_PUBIPS=( 149.165.159.17 149.165.159.35 149.165.159.36 149.165.159.37 149.165.159.38 149.165.159.39)

CVXOPTDIR=~/Desktop/cvxopt
#POXEXTDIR=~/Dropbox/sim_rel/pox/ext
#POXEXTDIR=~/Downloads/cb_sim_rel/ext
#POXEXTDIR=/media/removable/USB\ DISK/cb_sim_rel/ext
#POXEXTDIR=/media/USB\ DISK/cb_sim_rel/ext
POXEXTDIR=./../ext
#FVRELDIR=~/Dropbox/sim_rel/fg_rel/fg_controller/fv_rel
FVRELDIR=./fg_controller/fv_rel
#MINRELDIR=~/Dropbox/sim_rel/net_config/mininet_rel
#MINRELDIR=./../net_config/mininet_rel
MINRELDIR=./fg_mininet/mininet_rel
KSTARDATADIR=./../../large_ecei_data.bp
FFTW3DIR=./fg_mininet/mininet_rel/host_rel/fftw3
FONTDIR=//usr/share/fonts

if [ $1  = 'ssh' ]; then
  ssh mfa51@india.futuregrid.org
elif [ $1  = 'tr' ]; then
  scp -r misc mfa51@india.futuregrid.org:~/
elif [ $1  = 'fr' ]; then
  scp -r mfa51@india.futuregrid.org:~/misc .
elif [ $1 = 'uk' ]; then
  rm ./keys/mininet-key;
  scp -r mfa51@india.futuregrid.org:~/.ssh/mininet-key ./keys
elif [ $1  = 'scpkeys' ]; then
  scp mfa51@india.futuregrid.org:~/.ssh/mininet* ./keys
  scp mfa51@india.futuregrid.org:~/.ssh/mfa* ./keys
#######################################################
elif [ $1  = 'sshvm' ]; then
  ssh -X -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]}
elif [ $1  = 'fvm' ]; then
  if [ $2 = 0 ]; then
	  #scp -i $VMKEYDIR ${VM_USRNAMES[$2]}@${VM_PUBIPS[$2]}:~/cvxpy_test.log .
	  scp -i $VMKEYDIR ${VM_USRNAMES[$2]}@${VM_PUBIPS[$2]}:~/pox/ext/scheduling_optimization_new.py .
	else
	  scp -r -i $VMKEYDIR ${VM_USRNAMES[$2]}@${VM_PUBIPS[$2]}:~/mininet/mininet_rel/host_rel .
	fi
elif [ $1  = 'tvm' ]; then
  #scp -v -r $FGRELDIR -i $VMKEYDIR ${VM_USRNAMES[$2]}@${VM_PUBIPS[$2]}:~/
  if [ $2 = 0 ]; then
    tar czf - $POXEXTDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r ~/ext ~/pox; rm -r ~/ext"
    #tar czf - $MINRELDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r $MINRELDIR ~/; rm -r ~/fg_mininet; cp -r ~/mininet_rel ~/mininet; rm -r ~/mininet_rel"
    #tar czf - $FVRELDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r ~/fg_controller/fv_rel ~/; rm -r ~/fg_controller"
  else
    #tar czf - $MINRELDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r ~$MINRELDIR ~/; rm -r ~/home; cp -r ~/mininet_rel ~/mininet; rm -r ~/mininet_rel"
    tar czf - $MINRELDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r $MINRELDIR ~/; rm -r ~/fg_mininet; cp -r ~/mininet_rel ~/mininet; rm -r ~/mininet_rel"
    #tar czf - $KSTARDATADIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -"
    #tar czf - $FFTW3DIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r $FFTW3DIR ~/; rm -r ~/fg_mininet"
    #tar czf - $FONTDIR | ssh -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -"
  fi
elif [ $1  = 'scpinstalldirs' ]; then
  #only for snap_controller
  BASEDIR=~/Dropbox/sim_rel
  INSTALLDIRS=( networkx cvxopt )
  for DIR in "${INSTALLDIRS[@]}"; do
    tar czf - $BASEDIR/$DIR | ssh -v -l ${VM_USRNAMES[$2]} -i $VMKEYDIR ${VM_PUBIPS[$2]} "tar xzf -; cp -r ~/$BASEDIR/$DIR ~/; rm -r ~/home; cp ~/$DIR/pox_rel/* ~/pox/ext"
  done
#cmds for vm bundle
elif [ $1  = 'tmins' ]; then
  for i in `seq 1 5`;
  do
    echo "vm_mininet_id=$i::"
    echo "txing..."
    tar czf - $MINRELDIR | ssh -l ${VM_USRNAMES[$i]} -i $VMKEYDIR ${VM_PUBIPS[$i]} "tar xzf -; cp -r ~$MINRELDIR ~/; rm -r ~/home; cp -r ~/mininet_rel ~/mininet; rm -r ~/mininet_rel"
  done
#sith rel
elif [ $1  = 'sshsith' ]; then
    ssh mfa@sith.ccs.ornl.gov
elif [ $1  = 'tsith' ]; then
    scp -r ~/Desktop/ecei-adios mfa@sith.ccs.ornl.gov:~/ecei/ecei
elif [ $1  = 'fsith' ]; then
    #scp mfa@sith.ccs.ornl.gov:~/ecei/ecei/ecei-hfs.007131.bp /media/portable_large
    #scp -r mfa@sith.ccs.ornl.gov:~/ecei/ecei/mfa_proc ~/Downloads
    scp mfa@sith.ccs.ornl.gov:~/ecei_data.bp /media/portable_large
else
	echo "Argument did not match !"
fi

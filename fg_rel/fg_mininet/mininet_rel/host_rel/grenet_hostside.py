#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from mininet.link import TCLink

class MyTopo(Topo):
  def __init__(self):
    Topo.__init__( self )
    #
    s3 = self.addSwitch( 's3' )
    t11 = self.addHost( 't11', ip='10.0.0.11' )
    #
    #dsa_linkopts = dict(bw=1000, delay='50ms', loss=0, max_queue_size=1000000, use_htb=True)
    #
    self.addLink( s3, t11 )
    #self.addLink( s3, t11, **dsa_linkopts )
    
def run_tnodes(hosts):
  popens = {}
  for host in hosts:
    popens[host] = {}
    popens[host]['t'] = host.popen('./run_hosts.sh %s' % host.name) #host.popen('./run_hosts.sh t')
    print '%s is ready' % host.name
  #
  print 'itnodes are ready...'
  
if __name__ == '__main__':
  setLogLevel( 'info' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  net.addController('r0' , controller=RemoteController,
                    ip='10.39.1.11',
                    port=6633 )
  #
  t11 = net.getNodeByName('t11')
  #
  t11.setMAC(mac='00:00:00:00:01:01')
  #To fix "network is unreachable"
  t11.setDefaultRoute(intf='t11-eth0')
  #
  net.start()
  #
  s3 = net.getNodeByName('s3')
  s3.cmd('sudo ovs-vsctl add-port s3 s3-eth2 -- set interface s3-eth2 type=gre options:remote_ip=10.39.1.12') #to mininet1
  s3.cmd('sudo ovs-vsctl add-port s3 s3-eth3 -- set interface s3-eth3 type=gre options:remote_ip=10.39.1.66') #to mininet3
  s3.cmdPrint('ovs-vsctl show')
  #s3.cmd('sudo ovs-ofctl add-flow s3 "in_port=1 ip idle_timeout=0 actions=output:2"')
  #s3.cmd('sudo ovs-ofctl add-flow s3 "in_port=2 ip idle_timeout=0 actions=output:1"')
  #
  run_tnodes([t11])
  #
  CLI( net )
  net.stop()



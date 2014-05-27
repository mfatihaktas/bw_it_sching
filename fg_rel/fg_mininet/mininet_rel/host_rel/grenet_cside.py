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
    c1 = self.addHost( 'c1', ip='10.0.1.0' )
    c2 = self.addHost( 'c2', ip='10.0.1.1' )
    c3 = self.addHost( 'c3', ip='10.0.1.2' )
    c4 = self.addHost( 'c4', ip='10.0.1.3' )
    c5 = self.addHost( 'c5', ip='10.0.1.4' )
    c6 = self.addHost( 'c6', ip='10.0.1.5' )
    c7 = self.addHost( 'c7', ip='10.0.1.6' )
    c8 = self.addHost( 'c8', ip='10.0.1.7' )
    c9 = self.addHost( 'c9', ip='10.0.1.8' )
    c10 = self.addHost( 'c10', ip='10.0.1.9' )
    c11 = self.addHost( 'c11', ip='10.0.1.10' )
    
    s2 = self.addSwitch( 's2' )
    #
    #wide_linkopts = dict(bw=11, delay='50ms', loss=0, max_queue_size=1000000, use_htb=True)
    #
    self.addLink( s2, c1 )
    self.addLink( s2, c2 )
    self.addLink( s2, c3 )
    self.addLink( s2, c4 )
    self.addLink( s2, c5 )
    self.addLink( s2, c6 )
    self.addLink( s2, c7 )
    self.addLink( s2, c8 )
    self.addLink( s2, c9 )
    self.addLink( s2, c10 )
    self.addLink( s2, c11 )
    '''
    self.addLink( s2, c1, **wide_linkopts )
    self.addLink( s2, c2, **wide_linkopts )
    self.addLink( s2, c3, **wide_linkopts )
    self.addLink( s2, c4, **wide_linkopts )
    self.addLink( s2, c5, **wide_linkopts )
    self.addLink( s2, c6, **wide_linkopts )
    self.addLink( s2, c7, **wide_linkopts )
    self.addLink( s2, c8, **wide_linkopts )
    self.addLink( s2, c9, **wide_linkopts )
    self.addLink( s2, c10, **wide_linkopts )
    self.addLink( s2, c11, **wide_linkopts )
    '''
  
def run_pcnodes(hosts):
  popens = {}
  for host in hosts:
    popens[host] = host.popen('./run_hosts.sh %s' % host.name )
    print '%s is ready' % host.name
  #
  print 'pcnodes are ready...'

if __name__ == '__main__':
  setLogLevel( 'info' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  net.addController('r0' , controller=RemoteController,
                    ip='10.39.1.11',
                    port=6633 )
  #
  c1,c2,c3 = net.getNodeByName('c1', 'c2', 'c3')
  c4,c5,c6 = net.getNodeByName('c4', 'c5', 'c6')
  c7,c8,c9,c10,c11 = net.getNodeByName('c7', 'c8', 'c9', 'c10', 'c11')
  #
  c1.setMAC(mac='00:00:00:01:01:00')
  c2.setMAC(mac='00:00:00:01:01:01')
  c3.setMAC(mac='00:00:00:01:01:02')
  c4.setMAC(mac='00:00:00:01:01:03')
  c5.setMAC(mac='00:00:00:01:01:04')
  c6.setMAC(mac='00:00:00:01:01:05')
  c7.setMAC(mac='00:00:00:01:01:06')
  c8.setMAC(mac='00:00:00:01:01:07')
  c9.setMAC(mac='00:00:00:01:01:08')
  c10.setMAC(mac='00:00:00:01:01:09')
  c11.setMAC(mac='00:00:00:01:01:10')
  #To fix "network is unreachable"
  c1.setDefaultRoute(intf='c1-eth0')
  c2.setDefaultRoute(intf='c2-eth0')
  c3.setDefaultRoute(intf='c3-eth0')
  c4.setDefaultRoute(intf='c4-eth0')
  c5.setDefaultRoute(intf='c5-eth0')
  c6.setDefaultRoute(intf='c6-eth0')
  c7.setDefaultRoute(intf='c7-eth0')
  c8.setDefaultRoute(intf='c8-eth0')
  c9.setDefaultRoute(intf='c9-eth0')
  c10.setDefaultRoute(intf='c10-eth0')
  c11.setDefaultRoute(intf='c11-eth0')
  #
  net.start()
  #
  s2 = net.getNodeByName('s2')
  s2.cmd('sudo ovs-vsctl add-port s2 s2-eth12 -- set interface s2-eth12 type=gre options:remote_ip=10.39.1.65') #to mininet2
  s2.cmdPrint('ovs-vsctl show')
  #
  run_pcnodes([c1])
  #run_pcnodes([c1, c2, c3])
  #
  CLI( net )
  net.stop()



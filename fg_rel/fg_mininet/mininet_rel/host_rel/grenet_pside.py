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
    p1 = self.addHost( 'p1', ip='10.0.2.0' )
    p2 = self.addHost( 'p2', ip='10.0.2.1' )
    p3 = self.addHost( 'p3', ip='10.0.2.2' )
    p4 = self.addHost( 'p4', ip='10.0.2.3' )
    p5 = self.addHost( 'p5', ip='10.0.2.4' )
    p6 = self.addHost( 'p6', ip='10.0.2.5' )
    p7 = self.addHost( 'p7', ip='10.0.2.6' )
    p8 = self.addHost( 'p8', ip='10.0.2.7' )
    p9 = self.addHost( 'p9', ip='10.0.2.8' )
    p10 = self.addHost( 'p10', ip='10.0.2.9' )
    p11 = self.addHost( 'p11', ip='10.0.2.10' )
        
    s1 = self.addSwitch( 's1' )
    #
    #wide_linkopts = dict(bw=1000, delay='50ms', loss=0, max_queue_size=1000000, use_htb=True)
    #
    self.addLink( p1, s1 )
    self.addLink( p2, s1 )
    self.addLink( p3, s1 )
    self.addLink( p4, s1 )
    self.addLink( p5, s1 )
    self.addLink( p6, s1 )
    self.addLink( p7, s1 )
    self.addLink( p8, s1 )
    self.addLink( p9, s1 )
    self.addLink( p10, s1 )
    self.addLink( p11, s1 )
    '''
    self.addLink( p1, s1, **wide_linkopts )
    self.addLink( p2, s1, **wide_linkopts )
    self.addLink( p3, s1, **wide_linkopts )
    self.addLink( p4, s1, **wide_linkopts )
    self.addLink( p5, s1, **wide_linkopts )
    self.addLink( p6, s1, **wide_linkopts )
    self.addLink( p7, s1, **wide_linkopts )
    self.addLink( p8, s1, **wide_linkopts )
    self.addLink( p9, s1, **wide_linkopts )
    self.addLink( p10, s1, **wide_linkopts )
    self.addLink( p11, s1, **wide_linkopts )
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
  p1,p2,p3 = net.getNodeByName('p1', 'p2', 'p3')
  p4,p5,p6 = net.getNodeByName('p4', 'p5', 'p6')
  p7,p8,p9,p10,p11 = net.getNodeByName('p7', 'p8', 'p9', 'p10', 'p11')
  #
  p1.setMAC(mac='00:00:00:01:02:00')
  p2.setMAC(mac='00:00:00:01:02:01')
  p3.setMAC(mac='00:00:00:01:02:02')
  p4.setMAC(mac='00:00:00:01:02:03')
  p5.setMAC(mac='00:00:00:01:02:04')
  p6.setMAC(mac='00:00:00:01:02:05')
  p7.setMAC(mac='00:00:00:01:02:06')
  p8.setMAC(mac='00:00:00:01:02:07')
  p9.setMAC(mac='00:00:00:01:02:08')
  p10.setMAC(mac='00:00:00:01:02:09')
  p11.setMAC(mac='00:00:00:01:02:10')
  #To fix "network is unreachable"
  p1.setDefaultRoute(intf='p1-eth0')
  p2.setDefaultRoute(intf='p2-eth0')
  p3.setDefaultRoute(intf='p3-eth0')
  p4.setDefaultRoute(intf='p4-eth0')
  p5.setDefaultRoute(intf='p5-eth0')
  p6.setDefaultRoute(intf='p6-eth0')
  p7.setDefaultRoute(intf='p7-eth0')
  p8.setDefaultRoute(intf='p8-eth0')
  p9.setDefaultRoute(intf='p9-eth0')
  p10.setDefaultRoute(intf='p10-eth0')
  p11.setDefaultRoute(intf='p11-eth0')
  #
  net.start()
  #
  s1 = net.getNodeByName('s1')
  s1.cmd('sudo ovs-vsctl add-port s1 s1-eth12 -- set interface s1-eth12 type=gre options:remote_ip=10.39.1.65') #to mininet2
  s1.cmdPrint('ovs-vsctl show')
  #s1.cmd('sudo ovs-ofctl add-flow s1 "in_port=1 ip idle_timeout=0 actions=output:12"')
  #s1.cmd('sudo ovs-ofctl add-flow s1 "in_port=12 ip idle_timeout=0 actions=output:1"')
  #
  #run_pcnodes([p1])
  #run_pcnodes([p1, p2, p3])
  #
  CLI( net )
  net.stop()



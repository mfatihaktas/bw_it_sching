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
    
    c1 = self.addHost( 'c1', ip='10.0.1.0' )
    c2 = self.addHost( 'c2', ip='10.0.1.1' )
    c3 = self.addHost( 'c3', ip='10.0.1.2' )
    c4 = self.addHost( 'c4', ip='10.0.1.3' )
    c5 = self.addHost( 'c5', ip='10.0.1.4' )
    c6 = self.addHost( 'c6', ip='10.0.1.5' )
    
    s1 = self.addSwitch( 's1' )
    s2 = self.addSwitch( 's2' )
    t11 = self.addHost( 't11', ip='10.0.0.11' )
    t21 = self.addHost( 't21', ip='10.0.0.21' )
    #
    wide_linkopts = dict(bw=11, delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    dsa_linkopts = dict(bw=11, delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    #
    self.addLink( s1, t11, **dsa_linkopts )
    self.addLink( s1, s2, **wide_linkopts )
    self.addLink( s2, t21, **dsa_linkopts )
    
    self.addLink( s2, c1, **wide_linkopts )
    self.addLink( s2, c2, **wide_linkopts )
    self.addLink( s2, c3, **wide_linkopts )
    self.addLink( s2, c4, **wide_linkopts )
    self.addLink( s2, c5, **wide_linkopts )
    self.addLink( s2, c6, **wide_linkopts )
    self.addLink( p1, s1, **wide_linkopts )
    self.addLink( p2, s1, **wide_linkopts )
    self.addLink( p3, s1, **wide_linkopts )
    self.addLink( p4, s1, **wide_linkopts )
    self.addLink( p5, s1, **wide_linkopts )
    self.addLink( p6, s1, **wide_linkopts )
  
def run_tnodes(hosts):
  popens = {}
  for host in hosts:
    popens[host] = {}
    #popens[host]['eceiproc'] = host.popen('./run_hosts.sh ep2m')
    popens[host]['t'] = host.popen('./run_hosts.sh %s' % host.name) #host.popen('./run_hosts.sh t')
    print '%s is ready' % host.name
  #
  print 'itnodes are ready...'
  
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
  c1,c2,c3 = net.getNodeByName('c1', 'c2', 'c3')
  c4,c5,c6 = net.getNodeByName('c4', 'c5', 'c6')
  t11, t21 = net.getNodeByName('t11','t21')
  #
  p1.setMAC(mac='00:00:00:01:02:00')
  p2.setMAC(mac='00:00:00:01:02:01')
  p3.setMAC(mac='00:00:00:01:02:02')
  p4.setMAC(mac='00:00:00:01:02:03')
  p5.setMAC(mac='00:00:00:01:02:04')
  p6.setMAC(mac='00:00:00:01:02:05')
  c1.setMAC(mac='00:00:00:01:01:00')
  c2.setMAC(mac='00:00:00:01:01:01')
  c3.setMAC(mac='00:00:00:01:01:02')
  c4.setMAC(mac='00:00:00:01:01:03')
  c5.setMAC(mac='00:00:00:01:01:04')
  c6.setMAC(mac='00:00:00:01:01:05')
  t11.setMAC(mac='00:00:00:00:01:01')
  t21.setMAC(mac='00:00:00:00:02:01')
  #To fix "network is unreachable"
  p1.setDefaultRoute(intf='p1-eth0')
  p2.setDefaultRoute(intf='p2-eth0')
  p3.setDefaultRoute(intf='p3-eth0')
  p4.setDefaultRoute(intf='p4-eth0')
  p5.setDefaultRoute(intf='p5-eth0')
  p6.setDefaultRoute(intf='p6-eth0')
  c1.setDefaultRoute(intf='c1-eth0')
  c2.setDefaultRoute(intf='c2-eth0')
  c3.setDefaultRoute(intf='c3-eth0')
  c4.setDefaultRoute(intf='c4-eth0')
  c5.setDefaultRoute(intf='c5-eth0')
  c6.setDefaultRoute(intf='c6-eth0')
  t11.setDefaultRoute(intf='t11-eth0')
  t21.setDefaultRoute(intf='t21-eth0')
  #
  net.start()
  #
  run_tnodes([t11])
  
  #run_pcnodes([c1, p1, c2, p2])
  #run_pcnodes([c1, p1])
  #run_pcnodes([c1, c2, c3])
  run_pcnodes([c1, p1, c2, p2, c3, p3])
  #run_pcnodes([c1, p1, c2, p2, c3, p3, c4, p4, c5, p5, c6, p6])
  #
  CLI( net )
  net.stop()



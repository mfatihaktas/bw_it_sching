#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from mininet.link import TCLink

class MyTopo( Topo ):
  def __init__( self ):
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
    
    s20 = self.addSwitch( 's20' )
    s21 = self.addSwitch( 's21' )
    s22 = self.addSwitch( 's22' )
    s23 = self.addSwitch( 's23' )
    s10 = self.addSwitch( 's10' )
    s11 = self.addSwitch( 's11' )
    s12 = self.addSwitch( 's12' )
    s13 = self.addSwitch( 's13' )
    s1 = self.addSwitch( 's1' )
    s2 = self.addSwitch( 's2' )
    s3 = self.addSwitch( 's3' )
    s4 = self.addSwitch( 's4' )
    s5 = self.addSwitch( 's5' )
    s6 = self.addSwitch( 's6' )
    s7 = self.addSwitch( 's7' )
    s8 = self.addSwitch( 's8' )
    
    t11 = self.addHost( 't11', ip='10.0.0.11' )
    t21 = self.addHost( 't21', ip='10.0.0.21' )
    t31 = self.addHost( 't31', ip='10.0.0.31' )
    t41 = self.addHost( 't41', ip='10.0.0.41' )
    t51 = self.addHost( 't51', ip='10.0.0.51' )
    t61 = self.addHost( 't61', ip='10.0.0.61' )
    t71 = self.addHost( 't71', ip='10.0.0.71' )
    t81 = self.addHost( 't81', ip='10.0.0.81' )
    #
    # wide_linkopts = dict(bw=11, delay='50ms', loss=0, max_queue_size=1000000, use_htb=True)
    # dsa_linkopts = dict(bw=11, delay='50ms', loss=0, max_queue_size=1000000, use_htb=True)
    wide_linkopts = dict(delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    dsa_linkopts = dict(delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    # 4 paths
    self.addLink( s20,s1, **wide_linkopts )
    self.addLink( s1,s2, **wide_linkopts )
    self.addLink( s2,s10, **wide_linkopts )
    self.addLink( s21,s3, **wide_linkopts )
    self.addLink( s3,s4, **wide_linkopts )
    self.addLink( s4,s11, **wide_linkopts )
    self.addLink( s22,s5, **wide_linkopts )
    self.addLink( s5,s6, **wide_linkopts )
    self.addLink( s6,s12, **wide_linkopts )
    self.addLink( s23,s7, **wide_linkopts )
    self.addLink( s7,s8, **wide_linkopts )
    self.addLink( s8,s13, **wide_linkopts )
    # Inter-path
    self.addLink( s20,s21, **wide_linkopts )
    self.addLink( s21,s22, **wide_linkopts )
    self.addLink( s22,s23, **wide_linkopts )
    self.addLink( s10,s11, **wide_linkopts )
    self.addLink( s11,s12, **wide_linkopts )
    self.addLink( s12,s13, **wide_linkopts )
    # It
    self.addLink( s1,t11, **dsa_linkopts )
    self.addLink( s2,t21, **dsa_linkopts )
    self.addLink( s3,t31, **dsa_linkopts )
    self.addLink( s4,t41, **dsa_linkopts )
    self.addLink( s5,t51, **dsa_linkopts )
    self.addLink( s6,t61, **dsa_linkopts )
    self.addLink( s7,t71, **dsa_linkopts )
    self.addLink( s8,t81, **dsa_linkopts )
    
    self.addLink( s10, c1, **wide_linkopts )
    self.addLink( s11, c2, **wide_linkopts )
    self.addLink( s12, c3, **wide_linkopts )
    self.addLink( s13, c4, **wide_linkopts )
    self.addLink( s10, c5, **wide_linkopts )
    self.addLink( s11, c6, **wide_linkopts )
    self.addLink( s12, c7, **wide_linkopts )
    self.addLink( s13, c8, **wide_linkopts )
    self.addLink( s10, c9, **wide_linkopts )
    self.addLink( s11, c10, **wide_linkopts )
    self.addLink( s12, c11, **wide_linkopts )
    
    self.addLink( p1, s20, **wide_linkopts )
    self.addLink( p2, s21, **wide_linkopts )
    self.addLink( p3, s22, **wide_linkopts )
    self.addLink( p4, s23, **wide_linkopts )
    self.addLink( p5, s20, **wide_linkopts )
    self.addLink( p6, s21, **wide_linkopts )
    self.addLink( p7, s22, **wide_linkopts )
    self.addLink( p8, s23, **wide_linkopts )
    self.addLink( p9, s20, **wide_linkopts )
    self.addLink( p10, s21, **wide_linkopts )
    self.addLink( p11, s22, **wide_linkopts )
    # 
  
def run_tnodes(host_list):
  popens = {}
  for host in host_list:
    popens[host] = {}
    #popens[host]['eceiproc'] = host.popen('./run_hosts.sh ep2m')
    popens[host]['t'] = host.popen('./run_hosts.sh %s' % host.name) #host.popen('./run_hosts.sh t')
    print '%s is ready' % host.name
  #
  print 'itnodes are ready...'

def run_pcnodes(host_list):
  popens = {}
  for host in host_list:
    popens[host] = host.popen('./run_hosts.sh %s' % host.name )
    print '%s is ready' % host.name
  #
  print 'pcnodes are ready...'

if __name__ == '__main__':
  setLogLevel( 'info' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  net.addController('r0', controller=RemoteController, ip='10.39.1.12', port=6633)
  
  p1,p2,p3,p4,p5,p6,p7,p8,p9,p10,p11 = net.getNodeByName('p1','p2','p3','p4','p5','p6','p7','p8','p9','p10','p11')
  c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11 = net.getNodeByName('c1','c2','c3','c4','c5','c6','c7','c8','c9','c10','c11')
  t11,t21,t31,t41,t51,t61,t71,t81 = net.getNodeByName('t11','t21','t31','t41','t51','t61','t71','t81')
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
  
  t11.setMAC(mac='00:00:00:00:01:01')
  t21.setMAC(mac='00:00:00:00:02:01')
  t31.setMAC(mac='00:00:00:00:03:01')
  t41.setMAC(mac='00:00:00:00:04:01')
  t51.setMAC(mac='00:00:00:00:05:01')
  t61.setMAC(mac='00:00:00:00:06:01')
  t71.setMAC(mac='00:00:00:00:07:01')
  t81.setMAC(mac='00:00:00:00:08:01')
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
  
  t11.setDefaultRoute(intf='t11-eth0')
  t21.setDefaultRoute(intf='t21-eth0')
  t31.setDefaultRoute(intf='t31-eth0')
  t41.setDefaultRoute(intf='t41-eth0')
  t51.setDefaultRoute(intf='t51-eth0')
  t61.setDefaultRoute(intf='t61-eth0')
  t71.setDefaultRoute(intf='t71-eth0')
  t81.setDefaultRoute(intf='t81-eth0')
  #
  net.start()
  #
  run_tnodes([t11, t21, t31, t41, t51, t61, t71, t81])
  
  # run_pcnodes([c1, p1])
  # run_pcnodes([c1, p1, c2, p2, c3, p3])
  # run_pcnodes([c1, p1, c2, p2])
  # run_pcnodes([c1, p1, c2, p2, c3, p3, c4, p4])
  # run_pcnodes([c1, p1, c2, p2, c3, p3, c4, p4, c5, p5, c6, p6, c7, p7])
  # run_pcnodes([c1, p1, c2, p2, c3, p3, c4, p4, c5, p5, c6, p6, c7, p7, c8, p8, c9, p9, c10, p10, c11, p11])
  #
  CLI( net )
  net.stop()
  

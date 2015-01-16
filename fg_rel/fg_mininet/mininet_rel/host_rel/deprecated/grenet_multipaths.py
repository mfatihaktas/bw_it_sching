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
    p0 = self.addHost( 'p0', ip='10.0.2.0' )
    p1 = self.addHost( 'p1', ip='10.0.2.1' )
    p2 = self.addHost( 'p2', ip='10.0.2.2' )
    p3 = self.addHost( 'p3', ip='10.0.2.3' )
    p4 = self.addHost( 'p4', ip='10.0.2.4' )
    p5 = self.addHost( 'p5', ip='10.0.2.5' )
    p6 = self.addHost( 'p6', ip='10.0.2.6' )
    p7 = self.addHost( 'p7', ip='10.0.2.7' )
    p8 = self.addHost( 'p8', ip='10.0.2.8' )
    p9 = self.addHost( 'p9', ip='10.0.2.9' )
    
    c0 = self.addHost( 'c0', ip='10.0.1.0' )
    c1 = self.addHost( 'c1', ip='10.0.1.1' )
    c2 = self.addHost( 'c2', ip='10.0.1.2' )
    c3 = self.addHost( 'c3', ip='10.0.1.3' )
    c4 = self.addHost( 'c4', ip='10.0.1.4' )
    c5 = self.addHost( 'c5', ip='10.0.1.5' )
    c6 = self.addHost( 'c6', ip='10.0.1.6' )
    c7 = self.addHost( 'c7', ip='10.0.1.7' )
    c8 = self.addHost( 'c8', ip='10.0.1.8' )
    c9 = self.addHost( 'c9', ip='10.0.1.9' )
    
    #gateways
    s1 = self.addSwitch( 's1' )
    s2 = self.addSwitch( 's2' )
    s11 = self.addSwitch( 's11' )
    s21 = self.addSwitch( 's21' )
    #intermediates
    s3 = self.addSwitch( 's3' )
    s4 = self.addSwitch( 's4' )
    s5 = self.addSwitch( 's5' )
    #itrs
    t31 = self.addHost( 't31', ip='10.0.0.31' )
    t41 = self.addHost( 't41', ip='10.0.0.41' )
    t51 = self.addHost( 't51', ip='10.0.0.51' )
    #extra <down path>
    p20 = self.addHost( 'p20', ip='10.0.2.20' )
    p21 = self.addHost( 'p21', ip='10.0.2.21' )
    p22 = self.addHost( 'p22', ip='10.0.2.22' )
    p23 = self.addHost( 'p23', ip='10.0.2.23' )
    p24 = self.addHost( 'p24', ip='10.0.2.24' )
    p25 = self.addHost( 'p25', ip='10.0.2.25' )
    p26 = self.addHost( 'p26', ip='10.0.2.26' )
    p27 = self.addHost( 'p27', ip='10.0.2.27' )
    p28 = self.addHost( 'p28', ip='10.0.2.28' )
    p29 = self.addHost( 'p29', ip='10.0.2.29' )
    
    c20 = self.addHost( 'c20', ip='10.0.1.20' )
    c21 = self.addHost( 'c21', ip='10.0.1.21' )
    c22 = self.addHost( 'c22', ip='10.0.1.22' )
    c23 = self.addHost( 'c23', ip='10.0.1.23' )
    c24 = self.addHost( 'c24', ip='10.0.1.24' )
    c25 = self.addHost( 'c25', ip='10.0.1.25' )
    c26 = self.addHost( 'c26', ip='10.0.1.26' )
    c27 = self.addHost( 'c27', ip='10.0.1.27' )
    c28 = self.addHost( 'c28', ip='10.0.1.28' )
    c29 = self.addHost( 'c29', ip='10.0.1.29' )
    #interconns
    self.addLink( s1, s3 )
    self.addLink( s3, s4 )
    self.addLink( s3, s5 )
    self.addLink( s5, s4 )
    self.addLink( s4, s2 )
    self.addLink( s11, s5 )
    self.addLink( s5, s21 )
    
    self.addLink( s3, t31 )
    self.addLink( s4, t41 )
    self.addLink( s5, t51 )
    
    self.addLink( c0, s2 )
    self.addLink( c1, s2 )
    self.addLink( c2, s2 )
    self.addLink( c3, s2 )
    self.addLink( c4, s2 )
    self.addLink( c5, s2 )
    self.addLink( c6, s2 )
    self.addLink( c7, s2 )
    self.addLink( c8, s2 )
    self.addLink( c9, s2 )
    
    self.addLink( p0, s1 )
    self.addLink( p1, s1 )
    self.addLink( p2, s1 )
    self.addLink( p3, s1 )
    self.addLink( p4, s1 )
    self.addLink( p5, s1 )
    self.addLink( p6, s1 )
    self.addLink( p7, s1 )
    self.addLink( p8, s1 )
    self.addLink( p9, s1 )
    
    #extra <down path>
    self.addLink( p20, s11 )
    self.addLink( p21, s11 )
    self.addLink( p22, s11 )
    self.addLink( p23, s11 )
    self.addLink( p24, s11 )
    self.addLink( p25, s11 )
    self.addLink( p26, s11 )
    self.addLink( p27, s11 )
    self.addLink( p28, s11 )
    self.addLink( p29, s11 )
    
    self.addLink( c20, s21 )
    self.addLink( c21, s21 )
    self.addLink( c22, s21 )
    self.addLink( c23, s21 )
    self.addLink( c24, s21 )
    self.addLink( c25, s21 )
    self.addLink( c26, s21 )
    self.addLink( c27, s21 )
    self.addLink( c28, s21 )
    self.addLink( c29, s21 )
    
def run_tnodes(hosts):
  popens = {}
  for host in hosts:
    popens[host] = {}
    popens[host]['t'] = host.popen('./run_hosts2.sh %s' % host.name)
    print '%s is ready' % host.name
  #
  print 'itnodes are ready...'
  
def run_pcnodes(hosts):
  popens = {}
  for host in hosts:
    popens[host] = host.popen('./run_hosts2.sh %s' % host.name )
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
  p0,p1,p2,p3,p4,p5,p6,p7,p8,p9 = net.getNodeByName('p0','p1','p2','p3','p4','p5','p6','p7','p8','p9')
  c0,c1,c2,c3,c4,c5,c6,c7,c8,c9 = net.getNodeByName('c0','c1','c2','c3','c4','c5','c6','c7','c8','c9')
  t31,t41,t51 = net.getNodeByName('t31','t41','t51')
  p20,p21,p22,p23,p24,p25,p26,p27,p28,p29 = net.getNodeByName('p20','p21','p22','p23','p24','p25','p26','p27','p28','p29')
  c20,c21,c22,c23,c24,c25,c26,c27,c28,c29 = net.getNodeByName('c20','c21','c22','c23','c24','c25','c26','c27','c28','c29')
  #
  p0.setMAC(mac='00:00:00:01:02:00')
  p1.setMAC(mac='00:00:00:01:02:01')
  p2.setMAC(mac='00:00:00:01:02:02')
  p3.setMAC(mac='00:00:00:01:02:03')
  p4.setMAC(mac='00:00:00:01:02:04')
  p5.setMAC(mac='00:00:00:01:02:05')
  p6.setMAC(mac='00:00:00:01:02:06')
  p7.setMAC(mac='00:00:00:01:02:07')
  p8.setMAC(mac='00:00:00:01:02:08')
  p9.setMAC(mac='00:00:00:01:02:09')
  
  c0.setMAC(mac='00:00:00:01:01:00')
  c1.setMAC(mac='00:00:00:01:01:01')
  c2.setMAC(mac='00:00:00:01:01:02')
  c3.setMAC(mac='00:00:00:01:01:03')
  c4.setMAC(mac='00:00:00:01:01:04')
  c5.setMAC(mac='00:00:00:01:01:05')
  c6.setMAC(mac='00:00:00:01:01:06')
  c7.setMAC(mac='00:00:00:01:01:07')
  c8.setMAC(mac='00:00:00:01:01:08')
  c9.setMAC(mac='00:00:00:01:01:09')
  
  t31.setMAC(mac='00:00:00:00:03:01')
  t41.setMAC(mac='00:00:00:00:04:01')
  t51.setMAC(mac='00:00:00:00:05:01')
  #extra <down path>
  p20.setMAC(mac='00:00:00:01:02:20')
  p21.setMAC(mac='00:00:00:01:02:21')
  p22.setMAC(mac='00:00:00:01:02:22')
  p23.setMAC(mac='00:00:00:01:02:23')
  p24.setMAC(mac='00:00:00:01:02:24')
  p25.setMAC(mac='00:00:00:01:02:25')
  p26.setMAC(mac='00:00:00:01:02:26')
  p27.setMAC(mac='00:00:00:01:02:27')
  p28.setMAC(mac='00:00:00:01:02:28')
  p29.setMAC(mac='00:00:00:01:02:29')
  
  c20.setMAC(mac='00:00:00:01:01:20')
  c21.setMAC(mac='00:00:00:01:01:21')
  c22.setMAC(mac='00:00:00:01:01:22')
  c23.setMAC(mac='00:00:00:01:01:23')
  c24.setMAC(mac='00:00:00:01:01:24')
  c25.setMAC(mac='00:00:00:01:01:25')
  c26.setMAC(mac='00:00:00:01:01:26')
  c27.setMAC(mac='00:00:00:01:01:27')
  c28.setMAC(mac='00:00:00:01:01:28')
  c29.setMAC(mac='00:00:00:01:01:29')
  #To fix "network is unreachable"
  p0.setDefaultRoute(intf='p0-eth0')
  p1.setDefaultRoute(intf='p1-eth0')
  p2.setDefaultRoute(intf='p2-eth0')
  p3.setDefaultRoute(intf='p3-eth0')
  p4.setDefaultRoute(intf='p4-eth0')
  p5.setDefaultRoute(intf='p5-eth0')
  p6.setDefaultRoute(intf='p6-eth0')
  p7.setDefaultRoute(intf='p7-eth0')
  p8.setDefaultRoute(intf='p8-eth0')
  p9.setDefaultRoute(intf='p9-eth0')
  
  c0.setDefaultRoute(intf='c0-eth0')
  c1.setDefaultRoute(intf='c1-eth0')
  c2.setDefaultRoute(intf='c2-eth0')
  c3.setDefaultRoute(intf='c3-eth0')
  c4.setDefaultRoute(intf='c4-eth0')
  c5.setDefaultRoute(intf='c5-eth0')
  c6.setDefaultRoute(intf='c6-eth0')
  c7.setDefaultRoute(intf='c7-eth0')
  c8.setDefaultRoute(intf='c8-eth0')
  c9.setDefaultRoute(intf='c9-eth0')
  
  t31.setDefaultRoute(intf='t31-eth0')
  t41.setDefaultRoute(intf='t41-eth0')
  t51.setDefaultRoute(intf='t51-eth0')
  #extra <down path>
  p20.setDefaultRoute(intf='p20-eth0')
  p21.setDefaultRoute(intf='p21-eth0')
  p22.setDefaultRoute(intf='p22-eth0')
  p23.setDefaultRoute(intf='p23-eth0')
  p24.setDefaultRoute(intf='p24-eth0')
  p25.setDefaultRoute(intf='p25-eth0')
  p26.setDefaultRoute(intf='p26-eth0')
  p27.setDefaultRoute(intf='p27-eth0')
  p28.setDefaultRoute(intf='p28-eth0')
  p29.setDefaultRoute(intf='p29-eth0')
  
  c20.setDefaultRoute(intf='c20-eth0')
  c21.setDefaultRoute(intf='c21-eth0')
  c22.setDefaultRoute(intf='c22-eth0')
  c23.setDefaultRoute(intf='c23-eth0')
  c24.setDefaultRoute(intf='c24-eth0')
  c25.setDefaultRoute(intf='c25-eth0')
  c26.setDefaultRoute(intf='c26-eth0')
  c27.setDefaultRoute(intf='c27-eth0')
  c28.setDefaultRoute(intf='c28-eth0')
  c29.setDefaultRoute(intf='c29-eth0')
  #
  net.start()
  #
  #run_tnodes([t51])
  #run_tnodes([t31, t41, t51])
  
  run_pcnodes([c0,c1,c2,c3,c4,c5,c6,c7,c8,c9])
  #run_pcnodes([c20,c21,c22,c23,c24,c25,c26,c27,c28,c29])
  run_pcnodes([p0,p1,p2,p3,p4,p5,p6,p7,p8,p9])
  #run_pcnodes([p20,p21,p22,p23,p24,p25,p26,p27,p28,p29])
  #
  CLI( net )
  net.stop()



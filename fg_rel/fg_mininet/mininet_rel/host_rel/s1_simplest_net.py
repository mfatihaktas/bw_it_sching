#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def run_tnodes(hosts):
  popens = {}
  for host in hosts:
    host.cmdPrint('pwd')
    popens[host] = host.popen('./run_hosts.sh %s' % host.name)
  #
  print 'itnodes are ready...'

def dummyNet():
  net = Mininet( controller=RemoteController )
  net.addController( 'r0' , controller=RemoteController,
                   ip='10.39.1.18',
                   port=6633)

  p = net.addHost( 'p', ip='10.0.0.2' )
  c = net.addHost( 'c', ip='10.0.0.1' )
  t11 = net.addHost( 't11', ip='10.0.0.11' )
  #
  s1 = net.addSwitch( 's1' )
  #
  net.addLink( p, s1 )
  net.addLink( s1, t11 )
  net.addLink( s1, c )
  #
  p.setMAC(mac='00:00:00:01:00:02')
  c.setMAC(mac='00:00:00:01:00:01')
  t11.setMAC(mac='00:00:00:00:01:01')
  #To fix "network is unreachable"
  p.setDefaultRoute(intf='p-eth0')
  c.setDefaultRoute(intf='c-eth0')
  t11.setDefaultRoute(intf='t11-eth0')
  #
  net.start()
  #
  run_tnodes([t11])
  #
  CLI( net )
  net.stop()

if __name__ == '__main__':
  setLogLevel( 'info' )
  dummyNet()


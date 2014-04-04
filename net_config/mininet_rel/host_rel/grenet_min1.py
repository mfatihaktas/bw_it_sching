#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def dummyNet():
  net = Mininet( controller=RemoteController )
  net.addController( 'r0' , controller=RemoteController,
                   ip='10.39.1.2',
                   port=6633)

  h11 = net.addHost( 'h11', ip='10.0.0.11' )
  h12 = net.addHost( 'h12', ip='10.0.0.12' )
  s1 = net.addSwitch( 's1' )
  net.addLink( h11, s1 )
  net.addLink( h12, s1 )
  #
  h11.setMAC('00:00:00:00:01:01')
  h12.setMAC('00:00:00:00:01:02')
  #
  net.start()
  CLI( net )
  net.stop()

if __name__ == '__main__':
  setLogLevel( 'info' )
  dummyNet()

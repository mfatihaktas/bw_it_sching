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

  h21 = net.addHost( 'h21', ip='10.0.0.21' )
  h22 = net.addHost( 'h22', ip='10.0.0.22' )
  s2 = net.addSwitch( 's2' )
  net.addLink( h21, s2 )
  net.addLink( h22, s2 )
  #
  h21.setMAC('00:00:00:00:02:01')
  h22.setMAC('00:00:00:00:02:02')
  #
  net.start()
  CLI( net )
  net.stop()

if __name__ == '__main__':
  setLogLevel( 'info' )
  dummyNet()

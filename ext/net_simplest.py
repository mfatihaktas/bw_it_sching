#!/usr/bin/python

from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.link import TCLink

class MyTopo( Topo ):
  def __init__( self ):
    "Create custom topo."
    # Initialize topology
    Topo.__init__( self )
    # Add hosts and switches
    p = self.addHost( 'p' )
    c = self.addHost( 'c' )
    t11 = self.addHost( 't11' )

    s1 = self.addSwitch( 's1' )
    #link opts
    local_linkopts = dict(bw=10, delay='5ms', loss=0, max_queue_size=1000, use_htb=True)
    wide_linkopts = dict(bw=10, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
    dsa_linkopts = dict(bw=1000, delay='1ms', loss=0, max_queue_size=10000, use_htb=True)
    # Add links
    self.addLink( p,s1, **wide_linkopts )
    self.addLink( s1,t11, **dsa_linkopts )
    self.addLink( s1,c, **wide_linkopts )

def run_tnodes(hosts):
  #Start
  popens = {}
  for host in hosts:
    popens[host] = host.popen('cd host_rel; ./run.sh %s' % host.name)
  #Monitor them and print output
  for host,popen in popens.items():
    out, err = popen.communicate()
    print '%s; out=%s, err=%s' % (host.name,out,err)
  #
  print 'itnodes are ready...'
  
if __name__ == '__main__':
  setLogLevel( 'info' )
  info( '# Creating network\n' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  cont=net.addController('r1', controller=RemoteController, ip='192.168.56.1',port=6633)
  cont.start()
  
  p, c = net.getNodeByName('p', 'c')
  t11 = net.getNodeByName('t11')
  
  p.setIP(ip='10.0.0.2', prefixLen=32) #, intf='eth0')
  c.setIP(ip='10.0.0.1', prefixLen=32) #, intf='eth0')
  
  t11.setIP(ip='10.0.0.11', prefixLen=32)
  
  p.setMAC(mac='00:00:00:01:00:02')
  c.setMAC(mac='00:00:00:01:00:01')
  
  t11.setMAC(mac='00:00:00:00:01:01')
  #To fix "network is unreachable"
  p.setDefaultRoute(intf='p-eth0')
  c.setDefaultRoute(intf='c-eth0')
  #
  net.start()
  #
  run_tnodes([t11])
  #
  CLI( net )
  net.stop()
  

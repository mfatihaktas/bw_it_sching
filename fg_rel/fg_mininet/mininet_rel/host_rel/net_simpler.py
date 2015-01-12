#!/usr/bin/python
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController
from mininet.link import TCLink

class MyTopo( Topo ):
  def __init__( self ):
    Topo.__init__( self )
    #
    s1 = self.addSwitch( 's1' )
    s2 = self.addSwitch( 's2' )
    
    p1 = self.addHost( 'p1', ip='10.0.2.0' )
    c1 = self.addHost( 'c1', ip='10.0.1.0' )
    t11 = self.addHost( 't11', ip='10.0.0.11' )
    t21 = self.addHost( 't21', ip='10.0.0.21' )

    # Link opts
    wide_linkopts = dict(delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    dsa_linkopts = dict(delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    # Add links
    self.addLink( s1, s2, **wide_linkopts )
    
    self.addLink( s1, t11, **dsa_linkopts )
    self.addLink( s2, t21, **dsa_linkopts )
    
    self.addLink( s1, p1, **wide_linkopts )
    self.addLink( s2, c1, **wide_linkopts )

def run_tnodes(host_list):
  popens = {}
  for host in host_list:
    popens[host] = {}
    # popens[host]['eceiproc'] = host.popen('./run_hosts.sh ep2m')
    popens[host]['t'] = host.popen('./run_hosts.sh %s' % host.name) #host.popen('./run_hosts.sh t')
    print '%s is ready' % host.name
  #
  print 'itnodes are ready...'
  
if __name__ == '__main__':
  setLogLevel( 'info' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  cont=net.addController('r0', controller=RemoteController, ip='10.39.1.172', port=6633)
  cont.start()
  
  p1, c1 = net.getNodeByName('p1', 'c1')
  t11, t21 = net.getNodeByName('t11', 't21')
  
  p1.setMAC(mac='00:00:00:01:02:00')
  c1.setMAC(mac='00:00:00:01:01:00')
  t11.setMAC(mac='00:00:00:00:01:01')
  t21.setMAC(mac='00:00:00:00:02:01')
  # To fix "network is unreachable"
  p1.setDefaultRoute(intf='p1-eth0')
  c1.setDefaultRoute(intf='c1-eth0')
  t11.setDefaultRoute(intf='t11-eth0')
  t21.setDefaultRoute(intf='t21-eth0')
  #
  net.start()
  #
  run_tnodes([t11, t21])
  #
  CLI( net )
  net.stop()
  

#!/usr/bin/python

from mininet.cli import CLI
from mininet.log import setLogLevel, info #, error
from mininet.net import Mininet
#from mininet.link import Intf
#from mininet.topolib import TreeTopo
from mininet.topo import Topo
#from mininet.node import CPULimitedHost
from mininet.node import RemoteController
from mininet.link import TCLink
#from mininet.util import dumpNodeConnections
#from mininet.util import quietRun
#from mininet.util import pmonitor
#import thread

class MyTopo( Topo ):
  def __init__( self ):
    "Create custom topo."
    # Initialize topology
    Topo.__init__( self )
    # Add hosts and switches
    p = self.addHost( 'p' )
    c = self.addHost( 'c' )
    #dummy node
    d = self.addHost( 'd' )
    t11 = self.addHost( 't11' )
    t21 = self.addHost( 't21' )
    t31 = self.addHost( 't31' )

    s1 = self.addSwitch( 's1' )
    s2 = self.addSwitch( 's2' )
    s3 = self.addSwitch( 's3' )
    s11 = self.addSwitch( 's11' )
    s12 = self.addSwitch( 's12' )
    #link opts
    #local_linkopts = dict(bw=100, delay='5ms', loss=0, max_queue_size=1000, use_htb=True)
    #wide_linkopts = dict(bw=100, delay='50ms', loss=0, max_queue_size=1000, use_htb=True)
    local_linkopts = dict(bw=1000, delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    wide_linkopts = dict(bw=1000, delay='0ms', loss=0, max_queue_size=1000000, use_htb=True)
    dsa_linkopts = dict(bw=1000, delay='0ms', loss=0, max_queue_size=10000, use_htb=True)
    # Add links
    self.addLink( p,s11, **wide_linkopts )
    self.addLink( s11,s1, **local_linkopts )
    self.addLink( s1,s2, **local_linkopts )
    self.addLink( s1,s3, **local_linkopts )
    self.addLink( s3,s2, **local_linkopts )
    self.addLink( s2,s12, **local_linkopts )
    self.addLink( s12,c, **wide_linkopts )
    #for DSA 1
    self.addLink( s1,t11, **dsa_linkopts )
    #for DSA 2
    self.addLink( s2,t21, **dsa_linkopts )
    #for DSA 3
    self.addLink( s3,t31, **dsa_linkopts )
    #dummy link
    self.addLink( d,s11, **local_linkopts )
  
def run_tnodes(hosts):
  #Start
  """
  for host in hosts:
    host.cmdPrint('pwd')
    host.sendCmd('./run.sh %s &' % host.name)
  """
  popens = {}
  for host in hosts:
    host.cmdPrint('pwd')
    popens[host] = host.popen('./run_hosts.sh %s' % host.name)
  """
  #Monitor them and print output
  for host,popen in popens.items():
    out, err = popen.communicate()
    print '%s; out=%s, err=%s' % (host.name,out,err)
  """
  """
  for host, line in pmonitor( popens ):
    if host:
      print "<%s>: %s" % ( host.name, line.strip() )
  """
  print 'itnodes are ready...'

if __name__ == '__main__':
  setLogLevel( 'info' )
  info( '# Creating network\n' )
  net = Mininet( topo=MyTopo(), link=TCLink, controller=RemoteController)
  #cont=net.addController('r1', controller=RemoteController, ip='10.0.0.7',port=6633)
  cont=net.addController('r1', controller=RemoteController, ip='192.168.56.1',port=6633)
  cont.start()
  
  p, c = net.getNodeByName('p', 'c')
  t11, t21, t31 = net.getNodeByName('t11','t21','t31')
  
  p.setIP(ip='10.0.0.2', prefixLen=32) #, intf='eth0')
  c.setIP(ip='10.0.0.1', prefixLen=32) #, intf='eth0')
  
  t11.setIP(ip='10.0.0.11', prefixLen=32)
  t21.setIP(ip='10.0.0.21', prefixLen=32)
  t31.setIP(ip='10.0.0.31', prefixLen=32)
  
  p.setMAC(mac='00:00:00:01:00:02')
  c.setMAC(mac='00:00:00:01:00:01')
  
  t11.setMAC(mac='00:00:00:00:01:01')
  t21.setMAC(mac='00:00:00:00:02:01')
  t31.setMAC(mac='00:00:00:00:03:01')
  
  #To fix "network is unreachable"
  p.setDefaultRoute(intf='p-eth0')
  c.setDefaultRoute(intf='c-eth0')
  t11.setDefaultRoute(intf='t11-eth0')
  t21.setDefaultRoute(intf='t21-eth0')
  t31.setDefaultRoute(intf='t31-eth0')
  #dummy node conf
  d = net.getNodeByName('d')
  d.setIP(ip='10.0.0.111', prefixLen=32)
  d.setMAC(mac='00:00:00:00:11:01')
  d.setDefaultRoute(intf='d-eth0')
  #
  net.start()
  #
  run_tnodes([t11, t21, t31])
  #
  CLI( net )
  net.stop()
  

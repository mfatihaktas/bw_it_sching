"""Custom topology example

Two directly connected switches plus a host for each switch:

   host --- switch --- switch --- host

Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        c1 = self.addHost( 'c1' )
        c2 = self.addHost( 'c2' )
        p = self.addHost( 'p' )
	
        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )
        s4 = self.addSwitch( 's4' )
        s3 = self.addSwitch( 's3' )
	
	#link opts
	local_linkopts = dict(bw=10, delay='5ms', loss=1, max_queue_size=1000, use_htb=True)
	wide_linkopts = dict(bw=10, delay='50ms', loss=1, max_queue_size=1000, use_htb=True)
        # Add links
        self.addLink( c1,s1, **local_linkopts )
        self.addLink( s1,s4, **wide_linkopts )
        self.addLink( s4,s2, **wide_linkopts )
        self.addLink( s2,c2, **local_linkopts )
        self.addLink( s4,s3, **wide_linkopts )
        self.addLink( s3,p, **local_linkopts )

topos = { 'newtopo': ( lambda: MyTopo() ) }

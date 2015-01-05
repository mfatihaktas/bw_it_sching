from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import str_to_bool, dpid_to_str
from pox.lib.addresses import IPAddr
import pox.lib.packet as pkt
import time
from pox.openflow.of_json import *

import os, sys, inspect, threading, json

log = core.getLogger()


class SimpleController (object):
  def __init__ (self):
    core.openflow.addListenerByName("ConnectionUp", self._handle_ConnectionUp)
    core.openflow.addListenerByName("PacketIn", self._handle_PacketIn  )
    
  def _handle_PacketIn (self, event):
    packet = event.parsed
    ip_packet = packet.find('ipv4')
    print 'a packet is rxed by controller'
    if ip_packet is None:
      print "packet", packet," isn't IP!"
      return
    print "Rxed packet: ", packet, "from sw", event.connection.dpid
    print "Src IP:%s, Dst IP: %s" %(ip_packet.srcip, ip_packet.dstip)
    
  def install_default_fm (self, event):
    fm = of.ofp_flow_mod()
    fm.priority = 0x0001 # Pretty low
    fm.match.dl_type = ethernet.IP_TYPE
    fm.idle_timeout = 0
    fm.hard_timeout = 0
    fm.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
    #to workaround problem of not being able to disable broadcast when
    #adding rule for only sending to controller
    #fm.actions.append(of.ofp_action_output(port=dummy_port))
    event.connection.send(fm)
    print "install_default_fm is done for ", event.connection
  
  def _handle_ConnectionUp (self, event):
    conn = event.connection
    print "Connection %s" % (conn)
    #self.install_default_fm(event)
    # Proactive-Permanent rules for sw1: p-s1-c
    # p --> c
    self.send_ofmod_forward('conn_up',conn,'10.0.0.2','10.0.0.1',None, 2, [0,0])
    # c --> p
    self.send_ofmod_forward('conn_up',conn,'10.0.0.1','10.0.0.2',None, 1, [0,0])
    
  def send_ofmod_forward (self, _called_from, conn, nw_src, nw_dst, tp_dst, o_port, duration):
    msg = of.ofp_flow_mod()
    #msg.match = of.ofp_match.from_packet(packet)
    msg.priority = 0x7000
    #msg.match = of.ofp_match(dl_type = pkt.ethernet.IP_TYPE, nw_proto = pkt.ipv4.UDP_PROTOCOL, nw_dst=IPAddr(nw_dst))
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    if tp_dst != None:
      msg.match.nw_proto = 17 #UDP
      msg.match.tp_dst = int(tp_dst)
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    #print "event.ofp.buffer_id: ", event.ofp.buffer_id
    if _called_from == 'packet_in':
      msg.buffer_id = event.ofp.buffer_id
    msg.actions.append(of.ofp_action_output(port = o_port))
    conn.send(msg)
    print "\nFrom dpid: ", conn.dpid, "send_ofmod_forward ", "src_ip: ", nw_src
    print " dst_ip: ",nw_dst,"fport: ",o_port," is sent\n"

  def send_ofmod_modify_forward (self, _called_from, conn, nw_src, nw_dst,
                                 tp_dst, new_dst, new_dl_dst, o_port, duration):
    msg = of.ofp_flow_mod()
    msg.priority = 0x7000
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    if tp_dst != None:
      msg.match.nw_proto = 17 #UDP
      msg.match.tp_dst = int(tp_dst)
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    if _called_from == 'packet_in':
      msg.buffer_id = event.ofp.buffer_id
    msg.actions.append(of.ofp_action_nw_addr(nw_addr = IPAddr(new_dst), type=7))
    msg.actions.append(of.ofp_action_dl_addr(dl_addr = EthAddr(new_dl_dst), type=5))
    msg.actions.append(of.ofp_action_output(port = o_port))
    conn.send(msg)
    print "\nFrom dpid: ", conn.dpid, "send_ofmod_modify_forward", "src_ip: ", \
          nw_src," dst_ip: ",nw_dst," tp_dst: ",tp_dst," new_dst_ip: ",new_dst, \
          " new_dst_mac: ", new_dl_dst, " fport: ", o_port, " is sent\n"

def launch ():
  core.registerNew(SimpleController)
  

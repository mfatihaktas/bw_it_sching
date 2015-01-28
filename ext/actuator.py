"""
Realizing Sching decisions.
(Acting on sching_decs)
"""
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import str_to_bool, dpid_to_str
from pox.lib.addresses import IPAddr
import pox.lib.packet as pkt
from pox.openflow.of_json import *
import os, sys, inspect, json, pprint
  
cmd_subfolder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0],"ext")))
if cmd_subfolder not in sys.path:
   sys.path.insert(0, cmd_subfolder)
  
from ruleparser import RuleParser
from errors import *
from control_comm_intf import ControlCommIntf
from dtsitr_comm_intf import DTSItrCommIntf
import threading,signal, logging

log = core.getLogger()
#
info_dict = {'lscher_addr':('127.0.0.1', 7999),
             'scherl_addr':('127.0.0.1', 7998),
             'lsensor_addr':'...',
             'sensorl_addr':'...',
             'acter_vip': '10.0.0.255',
             'acter_vmac': '00:00:00:00:00:00',
             'scherl_tp': 7001,
             'schert_tp': 7001,
             's_entry_dur': [0, 0] }

rule_parser = RuleParser('ext/schedwalks.xml', 'ext/scheditjobs.xml')

'''
class Actuator (object):
  def __init__ (self)
  def signal_handler(self, signal, frame)
###  _handle_*** methods
  def _handle_recvfromscher(self, msg)
  def _handle_PacketIn (self, event)
  def _handle_ConnectionUp(self, event)
  def _handle_FlowStatsReceived (self, event)
  def dev_name_to_port(self, dev_name)
  def _handle_sendtoitr(self, walk_to_itr_info, msg_str)
  def _handle_recvfromitr(self, msg)
###  install_*** methods
  def install_proactive_scheditjob(self, type_toitr, s_id)
  def install_proactive_schedwalk(self, s_id)
###  send_*** methods
  def send_udp_packet_out(self, conn, payload, tp_src, tp_dst,src_ip, dst_ip,
## #Basic send functions for communicating with SWs
  def send_clear_swtable(self, conn)
  def send_stat_req(self, conn)
  def send_ofmod_delete(self, conn, nw_src, nw_dst, nw_proto, tp_src, tp_dst, duration)
  def send_ofmod_forward(self, _called_from, conn, nw_src, nw_dst, nw_proto, tp_src,
  def send_ofmod_mod_nw_src__forward(self, _called_from, conn, nw_src, nw_dst, nw_proto, 
  def send_ofmod_mod_nw_dst__forward(self, _called_from, conn, nw_src, nw_dst, nw_proto,
  ###
  def launch (proactive_install=True, deneme_flow=False)
'''

class Actuator (object):
  def __init__ (self):
    # For control comm with scher, ...
    self.cci = ControlCommIntf()
    self.cci.reg_commpair(sctag = 'acter-scher',
                          proto = 'tcp',
                          _recv_callback = self._handle_recvfromscher,
                          s_addr = info_dict['lscher_addr'],
                          c_addr = info_dict['scherl_addr'] )
    self.dtsitr_intf = DTSItrCommIntf()
    #
    self.dpid_conn_dict = {}
    core.openflow.addListenerByName("ConnectionUp", self._handle_ConnectionUp)
    core.openflow.addListenerByName("FlowStatsReceived", self._handle_FlowStatsReceived)
    core.openflow.addListenerByName("PacketIn", self._handle_PacketIn  )
    # T be able close dtsitr threads
    # self.worker_threads = []
    
    # To handle ctrl-c for doing cleanup
    signal.signal(signal.SIGINT, self.signal_handler)
    
  def signal_handler(self, signal, frame):
    print('signal_handler:: ctrl+c !')
    self.dtsitr_intf.close()
    # for t in self.worker_threads:
    #   t.join()
    
    # print('signal_handler:: all worker_threads joined.')
    
    # To transit sigint to pox.py
    os.kill(os.getpid(), signal.SIGINT)
    
  ######################################  _handle_*** methods  #####################################
  def _handle_recvfromscher(self, msg):
    [type_, data_] = msg
    if type_ == 's_sching_req' or type_ == 'res_sching_req':
      s_id = int(data_['s_id'])
      walk_rule_list = data_['walk_rule_list']
      itjob_rule_dict = data_['itjob_rule_dict']
      
      print '_handle_recvfromscher:: walk_rule_list= \n%s' % pprint.pformat(walk_rule_list)
      print '_handle_recvfromscher:: itjob_rule_dict= \n%s' % pprint.pformat(itjob_rule_dict)
      #
      rule_parser.modify_schedwalkxmlfile_by_walkrule(str(s_id), walk_rule_list)
      rule_parser.modify_scheditjobxmlfile_by_itjobrule(str(s_id), itjob_rule_dict)
      if _install_schrules_proactively:
        if type_ == 's_sching_req':
          self.install_proactive_schedwalk(s_id)
          self.install_proactive_scheditjob(type_toitr = 'itjob_rule',
                                            s_id = s_id )
        elif type_ == 'res_sching_req':
          self.install_proactive_scheditjob(type_toitr = 'reitjob_rule',
                                            s_id = s_id )
        #
      #
      print '_handle_recvfromscher:: sending sching_realization_done for s_id= %s to scher...' % s_id
      type_toscher = None
      if type_ == 's_sching_req':
        type_toscher = 's_sching_reply'
      elif type_ == 'res_sching_req':
        type_toscher = 'res_sching_reply'
      #
      msg = json.dumps({'type':type_toscher,
                        'data':{'s_id':s_id,
                                'reply':'done'} })
      self.cci.send_to_client('acter-scher', msg)
    #
  
  # Since the SW rules are set proactively, only acks are expected
  def _handle_PacketIn (self, event):
    eth_packet = event.parsed
    ip_packet = eth_packet.find('ipv4')
    if ip_packet is None:
      print '_handle_PacketIn:: doesnt have ip_payload; eth_packet=%s' % eth_packet
      return
    #
    srcip = (ip_packet.srcip).toStr()
    dstip = (ip_packet.dstip).toStr()
    protocol = ip_packet.protocol
    print '_handle_PacketIn:: rxed from sw_dpid=%s; srcip=%s, dstip=%s, protocol=%s' % (event.connection.dpid,srcip,dstip,protocol)
    if protocol == 1: #icmp
      print 'rxed icmp_packet=%s' % ip_packet.payload
      self.send_ofmod_forward(_called_from = 'packet_in',
                              conn = event.connection,
                              nw_src = srcip,
                              nw_dst = dstip,
                              nw_proto = protocol,
                              tp_src = '-1',
                              tp_dst = '-1',
                              fport = of.OFPP_ALL,
                              duration = [0, 0],
                              buffer_id = event.ofp.buffer_id )
      print 'icmp rule is inserted!'
      return
    #
    msg = (ip_packet.payload).payload
    self.dtsitr_intf.pass_to_dts(itr_ip = srcip,
                                 msg =  msg )
    
  def _handle_ConnectionUp(self, event):
    print "_handle_ConnectionUp:: %s" % (event.connection)
    self.dpid_conn_dict[str(event.connection.dpid)] = event.connection
    
  def _handle_FlowStatsReceived (self, event):
    print '_handle_FlowStatsReceived::'
    stats = flow_stats_to_list(event.stats)
    print "FlowStatsReceived from ",dpidToStr(event.connection.dpid), ": ",stats
  
  # Of course works only for mininet networks
  def dev_name_to_port(self, dev_name):
    eth_part = dev_name.split('-', 1)[1]
    return int(eth_part.strip('eth'))
  
  def _handle_sendtoitr(self, walk_to_itr_info, msg_str):
    sw_dpid = walk_to_itr_info['sw_dpid']
    # print '_handle_sendtoitr:: dpid_conn_dict= \n%s' % pprint.pprint(self.dpid_conn_dict)
    conn = self.dpid_conn_dict[sw_dpid]
    self.send_udp_packet_out(conn = conn,
                             fw_port = self.dev_name_to_port(str(walk_to_itr_info['swdev_to_itr']) ),
                             payload = msg_str,
                             tp_src = info_dict['scherl_tp'],
                             tp_dst = info_dict['schert_tp'],
                             src_ip = info_dict['acter_vip'],
                             dst_ip = walk_to_itr_info['itr_ip'],
                             src_mac = info_dict['acter_vmac'],
                             dst_mac = walk_to_itr_info['itr_mac'] )
    
  # Now; itres does not send to dts in the current setting
  def _handle_recvfromitr(self, msg):
    # [type_, data_] = msg
    pass
  
  #########################  install_*** methods  #######################
  def install_proactive_scheditjob(self, type_toitr, s_id):
    itjob_rule_dict = rule_parser.get_itjobruledict_forsession(str(s_id))
    # print 'itjob_rule_dict= \n%s' % pprint.pformat(itjob_rule_dict)
    for dpid in itjob_rule_dict:
      itr_info_list = itjob_rule_dict[dpid]
      for itr_info in itr_info_list:
        job_info = itr_info['job_info']
        walk_to_itr_info = itr_info['walk_info']
        itr_ip = walk_to_itr_info['itr_ip'].encode('ascii','ignore')
        walk_to_itr_info.update({'sw_dpid': str(dpid) })
        #
        self.dtsitr_intf.reg_itr(itr_ip = itr_ip,
                                 walk_to_itr_info = walk_to_itr_info,
                                 _recv_callback = self._handle_recvfromitr,
                                 _send_callback = self._handle_sendtoitr )
        self.dtsitr_intf.relsend_to_itr(itr_ip = itr_ip,
                                        msg = {'type': type_toitr,
                                               'data': job_info} )
        '''
        t = threading.Thread(name = 'relsend_to_itr;itr_ip='+itr_ip,
                             target = self.dtsitr_intf.relsend_to_itr,
                             kwargs = {'itr_ip': itr_ip,
                                       'msg': {'type':'itjob_rule_dict',
                                               'data': job_info} } )
        self.worker_threads.append(t)
        t.start()
        '''
    #
    print 'install_proactive_scheditjob:: installed for s_id=%s; type_toitr=%s' % (s_id, type_toitr)
  
  def install_proactive_schedwalk(self, s_id):
    [walk_rule_dict, hmfromdpid_dict] = rule_parser.get_walkruledict_forsession(str(s_id))
    # print 'walkruledict= \n%s' % pprint.pformat(walk_rule_dict)
    #print 'hmfromdpid_dict= \n%s' % pprint.pformat(hmfromdpid_dict)
    
    for conn in core.openflow.connections:
      dpid = str(conn.dpid) #str(event.connection.dpid)
      try:
        hm = hmfromdpid_dict[dpid]
      except (KeyError):
        print '\n# No entry in hm_from_dpid for dpid=%s' % dpid
        continue
      l_dict = None
      counter = 0
      while (counter <= hm):
        l_dict = walk_rule_dict[dpid, counter]
        typ = l_dict['typ']
        rule_dict = l_dict['rule_dict']
        wc_dict = l_dict['wc_dict']

        if typ == 'forward':
          self.send_ofmod_forward(_called_from = 'install_proactive_schedwalk',
                                   conn = conn,
                                   nw_src = wc_dict['src_ip'],
                                   nw_dst = wc_dict['dst_ip'],
                                   nw_proto = wc_dict['nw_proto'],
                                   tp_src = wc_dict['tp_src'],
                                   tp_dst = wc_dict['tp_dst'],
                                   fport = self.dev_name_to_port(rule_dict['fport']),
                                   duration = info_dict['s_entry_dur'] )
          #self.send_stat_req(conn)
        elif typ == 'mod_nw_src__forward':
          self.send_ofmod_mod_nw_src__forward(_called_from = 'install_proactive_schedwalk',
                                              conn = conn,
                                              nw_src = wc_dict['src_ip'],
                                              nw_dst = wc_dict['dst_ip'],
                                              nw_proto = wc_dict['nw_proto'],
                                              tp_src = wc_dict['tp_src'],
                                              tp_dst = wc_dict['tp_dst'],
                                              new_src = rule_dict['new_src_ip'],
                                              new_dl_src = rule_dict['new_src_mac'],
                                              fport = self.dev_name_to_port(rule_dict['fport']),
                                              duration = info_dict['s_entry_dur'] )
          #self.send_stat_req(conn)
        elif typ == 'mod_nw_dst__forward':
          self.send_ofmod_mod_nw_dst__forward(_called_from = 'install_proactive_schedwalk',
                                              conn = conn,
                                              nw_src = wc_dict['src_ip'],
                                              nw_dst = wc_dict['dst_ip'],
                                              nw_proto = wc_dict['nw_proto'],
                                              tp_src = wc_dict['tp_src'],
                                              tp_dst = wc_dict['tp_dst'],
                                              new_dst = rule_dict['new_dst_ip'],
                                              new_dl_dst = rule_dict['new_dst_mac'],
                                              fport = self.dev_name_to_port(rule_dict['fport']),
                                              duration = info_dict['s_entry_dur'] )
        counter += 1
      #
    #
    print 'install_proactive_schedwalk::installed for s_id=%s' % s_id
  #######################  send_*** methods  ###################################
  # Method for just sending a UDP packet over any sw_port (broadcast by default)
  def send_udp_packet_out(self, conn, payload, tp_src, tp_dst,src_ip, dst_ip,
                          src_mac, dst_mac, fw_port = of.OFPP_ALL):
    msg = of.ofp_packet_out(in_port=of.OFPP_NONE)
    msg.buffer_id = None
    # Make the udp packet
    udpp = pkt.udp()
    udpp.srcport = tp_src
    udpp.dstport = tp_dst
    udpp.payload = payload
    # Make the IP packet around it
    ipp = pkt.ipv4()
    ipp.protocol = ipp.UDP_PROTOCOL
    ipp.srcip = IPAddr(src_ip)
    ipp.dstip = IPAddr(dst_ip)
    # Ethernet around that...
    ethp = pkt.ethernet()
    ethp.src = EthAddr(src_mac)
    ethp.dst = EthAddr(dst_mac)
    ethp.type = ethp.IP_TYPE
    # Hook them up...
    ipp.payload = udpp
    ethp.payload = ipp
    # Send it to the sw
    msg.actions.append(of.ofp_action_output(port = fw_port))
    msg.data = ethp.pack()
    # Show msg before sending
    """
    print '*******************'
    print 'msg.show(): ',msg.show()
    print '*******************'
    """
    # print "send_udp_packet_out:: sw%s and fw_port:%s" %(conn.dpid, fw_port)
    conn.send(msg)
  
  # Basic send functions for communicating with SWs
  def send_clear_swtable(self, conn):
    msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
    conn.send(msg)
    print 'clearing flows from %s.' % dpid_to_str(event.connection.dpid)
  
  def send_stat_req(self, conn):
    conn.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
    print "\nsend_stat_req to sw_dpid=%s\n" % conn.dpid
  
  def send_ofmod_delete(self, conn, nw_src, nw_dst, nw_proto, tp_src, tp_dst, duration):
    msg = of.ofp_flow_mod()
    msg.command = OFPFC_DELETE
    #wcs
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    msg.match.nw_proto = nw_proto #17:UDP, 6:TCP
    if tp_src != '-1':
      msg.match.tp_src = int(tp_src)
    if tp_dst != '-1':
      msg.match.tp_dst = int(tp_dst)
    #
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    conn.send(msg)
    print '\nsend_ofmod_delete to sw_dpid=%s' % conn.dpid
    print 'wcs: src_ip=%s, dst_ip=%s, nw_proto=%s, tp_src=%s, tp_dst=%s\n' % (nw_src,nw_dst,nw_proto,tp_src,tp_dst)
  
  def send_ofmod_forward(self, _called_from, conn, nw_src, nw_dst, nw_proto, tp_src,
                         tp_dst, fport, duration, buffer_id = None):
    msg = of.ofp_flow_mod()
    # msg.match = of.ofp_match.from_packet(packet)
    msg.priority = 0x7000
    # msg.match = of.ofp_match(dl_type = pkt.ethernet.IP_TYPE, nw_proto = pkt.ipv4.UDP_PROTOCOL, nw_dst=IPAddr(nw_dst))
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    msg.match.nw_proto = int(nw_proto) #17:UDP, 6:TCP
    if tp_src != '-1':
      msg.match.tp_src = int(tp_src)
    if tp_dst != '-1':
      msg.match.tp_dst = int(tp_dst)
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    # print "event.ofp.buffer_id: ", event.ofp.buffer_id
    if _called_from == 'packet_in':
      msg.buffer_id = buffer_id
    msg.actions.append(of.ofp_action_output(port = fport))
    conn.send(msg)
    print '\nsend_ofmod_forward to sw_dpid=%s' % conn.dpid
    print 'wcs: src_ip=%s, dst_ip=%s, nw_proto=%s, tp_src=%s, tp_dst=%s' % (nw_src,nw_dst,nw_proto,tp_src,tp_dst)
    print 'acts: fport=%s\n' % fport
    
  def send_ofmod_mod_nw_src__forward(self, _called_from, conn, nw_src, nw_dst, nw_proto, 
                                     tp_src, tp_dst, new_src, new_dl_src,fport, duration):
    msg = of.ofp_flow_mod()
    msg.priority = 0x7000
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    msg.match.nw_proto = int(nw_proto) #17:UDP, 6:TCP
    if tp_src != '-1':
      msg.match.tp_src = int(tp_src)
    if tp_dst != '-1':
      msg.match.tp_dst = int(tp_dst)
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    if _called_from == 'packet_in':
      msg.buffer_id = event.ofp.buffer_id
    msg.actions.append(of.ofp_action_nw_addr(nw_addr = IPAddr(new_src), type=6)) #type={6:mod_nw_src, 7:mod_nw_dst}
    msg.actions.append(of.ofp_action_dl_addr(dl_addr = EthAddr(new_dl_src), type=4)) #type={4:mod_dl_src, 5:mod_dl_dst}
    msg.actions.append(of.ofp_action_output(port = fport))
    conn.send(msg)
    print '\nsend_ofmod_mod_nw_src__forward to sw_dpid=%s' % conn.dpid
    print 'wcs: src_ip=%s, dst_ip=%s, nw_proto=%s, tp_src=%s, tp_dst=%s' % (nw_src,nw_dst,nw_proto,tp_src,tp_dst)
    print 'acts: new_src=%s, new_dl_src=%s, fport=%s\n' % (new_src, new_dl_src, fport)

  def send_ofmod_mod_nw_dst__forward(self, _called_from, conn, nw_src, nw_dst, nw_proto,
                                     tp_src, tp_dst, new_dst, new_dl_dst,fport, duration):
    msg = of.ofp_flow_mod()
    msg.priority = 0x7000
    msg.match.dl_type = 0x800 # Ethertype / length (e.g. 0x0800 = IPv4)
    msg.match.nw_src = IPAddr(nw_src)
    msg.match.nw_dst = IPAddr(nw_dst)
    msg.match.nw_proto = int(nw_proto) #17:UDP, 6:TCP
    if tp_src != '-1':
      msg.match.tp_src = int(tp_src)
    if tp_dst != '-1':
      msg.match.tp_dst = int(tp_dst)
    msg.idle_timeout = duration[0]
    msg.hard_timeout = duration[1]
    if _called_from == 'packet_in':
      msg.buffer_id = event.ofp.buffer_id
    msg.actions.append(of.ofp_action_nw_addr(nw_addr = IPAddr(new_dst), type=7)) #type={6:mod_nw_src, 7:mod_nw_dst}
    msg.actions.append(of.ofp_action_dl_addr(dl_addr = EthAddr(new_dl_dst), type=5)) #type={4:mod_dl_src, 5:mod_dl_dst}
    msg.actions.append(of.ofp_action_output(port = fport))
    conn.send(msg)
    print '\nsend_ofmod_mod_nw_dst__forward to sw_dpid=%s' % conn.dpid
    print 'wcs: src_ip=%s, dst_ip=%s, nw_proto=%s, tp_src=%s, tp_dst=%s' % (nw_src,nw_dst,nw_proto,tp_src,tp_dst)
    print 'acts: new_dst=%s, new_dl_dst=%s, fport=%s\n' % (new_dst, new_dl_dst, fport)
  ##############################################################################
_install_schrules_proactively = None
_install_deneme_flow = None

def launch (proactive_install=True, deneme_flow=False):
  global _install_schrules_proactively, _install_deneme_flow
  
  _install_schrules_proactively = str_to_bool(proactive_install)
  _install_deneme_flow = str_to_bool(deneme_flow)
  #
  core.registerNew(Actuator)

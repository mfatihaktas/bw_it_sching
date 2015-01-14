from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr
import pox.lib.packet as pkt
from pox.openflow.of_json import *
from scheduler import Scheduler
from exp_plot import ExpPlotter
import pprint,logging,signal,threading

info_dict = {'scher_vip': '10.0.0.255',
             'scher_vmac': '00:00:00:00:00:00',
             'sching_port': 7000 }

'''
class SchController(object):
  def __init__(self)
  def waitforenter(self)
###  _handle_*** methods
  def _handle_SendMsgToUser(self, event)
  def _handle_PacketIn(self, event)
  def _handle_ConnectionUp(self, event)
  def _handle_FlowStatsReceived (self, event)
###  send_*** methods
  def send_udp_packet_out(self, conn, payload, tp_src, tp_dst,src_ip, dst_ip, src_mac, dst_mac, fw_port = of.OFPP_ALL)
  def send_stat_req(self, event)
###  install_*** methods
  def install_drop_sch_response(self, event)
  def install_default_to_controller(self, event, proto)
###
  def launch ()
'''

class SchController(object):
  def __init__(self):
    #logging.basicConfig(filename='logs/schcontlog',filemode='w',level=logging.DEBUG)
    self.exp_plotter = ExpPlotter()
    #
    threading.Thread(target=self.waitforenter).start()
    #
    self.scheduler = Scheduler(xml_net_num = 1,
                               sching_logto = 'console',
                               data_over_tp = 'tcp')
    #
    self.scheduler.event_chief.addListenerByName("SendMsgToUser",
                                                 self._handle_SendMsgToUser)
    #
    self.dpid_conn_dict = {}
    core.openflow.addListenerByName("ConnectionUp", self._handle_ConnectionUp)
    core.openflow.addListenerByName("FlowStatsReceived", self._handle_FlowStatsReceived)
    core.openflow.addListenerByName("PacketIn", self._handle_PacketIn  )
  
  def waitforenter(self):
    raw_input('Enter\n')
    
    couplingdoneinfo_dict = self.scheduler.get_couplingdoneinfo_dict()
    sessionspreserved_dict = self.scheduler.get_sessionspreserved_dict()
    print 'sessionspreserved_dict=\n%s' % pprint.pformat(sessionspreserved_dict)
    # 1
    for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items():
      coupling_done = couplingdoneinfo['coupling_done']
      session_done = couplingdoneinfo['session_done']
      
      sessionpreserved = sessionspreserved_dict[sch_req_id]
      
      coupling_dur = coupling_done['recvend_time'] - session_done['sendstart_time']
      onthefly_dur = session_done['sendstop_time'] - coupling_done['recvstart_time']
      ptx_dur = session_done['sendstop_time'] - session_done['sendstart_time']
      
      couplingdoneinfo['overall'] = {'coupling_dur': coupling_dur,
                                     'onthefly_dur': onthefly_dur,
                                     'ptx_dur': ptx_dur,
                                     'recvedsize': coupling_done['recvedsize'],
                                     'sentsize': session_done['sentsize'],
                                     'trans_time': sessionpreserved['trans_time'],
                                     'slack-tt': sessionpreserved['slack-tt'],
                                     'slack-transtime': sessionpreserved['slack-transtime'],
                                     'app_pref_dict': sessionpreserved['app_pref_dict'] }
      idealtrans_time = sessionpreserved['trans_time'] + sessionpreserved['sched_time_list'][-1] - sessionpreserved['sched_time_list'][0]#sec
      couplingdoneinfo['overall']['slack_metric_list'] = sessionpreserved['slack_metric_list']
      couplingdoneinfo['overall']['sched_time_list'] = sessionpreserved['sched_time_list']
      couplingdoneinfo['overall']['bw_list'] = sessionpreserved['bw_list']
      couplingdoneinfo['overall']['datasize_list'] = sessionpreserved['datasize_list']
      couplingdoneinfo['overall']['tobeproced_datasize_list'] = sessionpreserved['tobeproced_datasize_list']
      couplingdoneinfo['overall']['tobeproced_data_transt_list'] = sessionpreserved['tobeproced_data_transt_list']
      
      couplingdur_relerr = 100*float(coupling_dur - idealtrans_time)/idealtrans_time
      
      session_done['joinrr_time'] += 1
      session_done['schingrr_time'] += 1
      sching_overhead = 100*float(session_done['schingrr_time'])/coupling_dur
      couplingdoneinfo['overall'].update({'idealtrans_time': idealtrans_time,
                                          'couplingdur_relerr': couplingdur_relerr,
                                          'sching_overhead': sching_overhead })
      #
      couplingdoneinfo['overall']['recvedpercentwithfunc_dict'] = \
        {func:100*float(size)/coupling_done['recvedsize'] for func,size in coupling_done['recvedsizewithfunc_dict'].items()}
    #
    print 'couplingdoneinfo_dict=\n%s' % pprint.pformat(couplingdoneinfo_dict)
    
    # furl = '/home/ubuntu/pox/ext/logs/schcontroller.log'
    # f = open(furl, 'w')
    # f.write(pprint.pformat(couplingdoneinfo_dict))
    # f.close()
    # #converting schingid_rescapalloc_dict to resid_rescapalloc_dict
    # schingid_rescapalloc_dict = self.scheduler.get_schingid_rescapalloc_dict()
    # print 'schingid_rescapalloc_dict=%s' % pprint.pformat(schingid_rescapalloc_dict)
    # resid_rescapalloc_dict = {}
    # for sching_id, rescapalloc_dict in schingid_rescapalloc_dict.items():
    #   for res_id, rescapalloc in rescapalloc_dict.items():
    #     if not res_id in resid_rescapalloc_dict:
    #       resid_rescapalloc_dict[res_id] = {}
    #     #
    #     resid_rescapalloc_dict[res_id][sching_id] = rescapalloc
    # #
    # print 'resid_rescapalloc_dict=%s' % pprint.pformat(resid_rescapalloc_dict)
    # #
    # self.exp_plotter.write_expdatafs(couplingdoneinfo_dict = couplingdoneinfo_dict,
    #                                 outf1url='/home/ubuntu/pox/ext/logs/couplingdoneinfo.dat',
    #                                 resid_rescapalloc_dict = resid_rescapalloc_dict,
    #                                 outf2basename='/home/ubuntu/pox/ext/logs/rescapalloc_resid' )
    # #
    # geninfo_dict = self.scheduler.get_geninfo_dict()
    # maxbw = 10 #Mbps
    # maxproc = 100 #Mfps
    # for res_id in resid_rescapalloc_dict:
    #   if res_id <= geninfo_dict['ll_index']: #res is link
    #     self.exp_plotter.plot_resallocrel(datafurl='/home/ubuntu/pox/ext/logs/rescapalloc_resid'+str(res_id)+'.dat',
    #                                       outfurl='/home/ubuntu/pox/ext/logs/fig_rescapallocLINKid'+str(res_id)+'.png',
    #                                       numsching=len(schingid_rescapalloc_dict),
    #                                       yrange=1.1*maxbw,
    #   else: #res is itr
    #                                       resunit='Mbps' )
    #     self.exp_plotter.plot_resallocrel(datafurl='/home/ubuntu/pox/ext/logs/rescapalloc_resid'+str(res_id)+'.dat',
    #                                       outfurl='/home/ubuntu/pox/ext/logs/fig_rescapallocITRid'+str(res_id)+'.png',
    #                                       numsching=len(schingid_rescapalloc_dict),
    #                                       yrange=1.1*maxproc,
    #                                       resunit='Mfps' )
    #   #
    # #
    # self.exp_plotter.plot_sizerel(datafurl = '/home/ubuntu/pox/ext/logs/couplingdoneinfo.dat', 
    #                               outfurl = '/home/ubuntu/pox/ext/logs/sizerel.png',
    #                               nums = len(couplingdoneinfo_dict),
    #                               yrange = 1.1*max([couplingdoneinfo['overall']['recvedsize']/(1024**2) for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items()]) )
    # self.exp_plotter.plot_timerel(datafurl = '/home/ubuntu/pox/ext/logs/couplingdoneinfo.dat',
    #                               outfurl = '/home/ubuntu/pox/ext/logs/timerel.png',
    #                               nums = len(couplingdoneinfo_dict),
    #                               yrange = 1.1*max([couplingdoneinfo['overall']['coupling_dur'] for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items()]) )
    
    # self.exp_plotter.plot_overheadrel(datafurl = '/home/ubuntu/pox/ext/logs/couplingdoneinfo.dat',
    #                                   outfurl = '/home/ubuntu/pox/ext/logs/overheadrel.png',
    #                                   nums = len(couplingdoneinfo_dict),
    #                                   yrange = 1.1*max([couplingdoneinfo['session_done']['schingrr_time'] for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items()] + \
    #                                                   [couplingdoneinfo['session_done']['joinrr_time'] for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items()]) )
    #
    
  #########################  _handle_*** methods  #######################
  def _handle_SendMsgToUser(self, event):
    #print '_handle_SendMsgToUser::'
    #dict_ includes info necessary to send packet_out
    dict_ = event.userinfo_dict
    conn = self.dpid_conn_dict[dict_['gw_dpid']]
    self.send_udp_packet_out(conn, payload=event.msg,
                             fw_port=dict_['gw_conn_port'],
                             tp_src=info_dict['sching_port'],
                             tp_dst=info_dict['sching_port'],
                             src_ip=info_dict['scher_vip'],
                             dst_ip=dict_['user_ip'],
                             src_mac=info_dict['scher_vmac'],
                             dst_mac=dict_['user_mac'] )
    
  def _handle_PacketIn(self, event):
    eth_packet = event.parsed
    conn = event.connection
    ip_packet = eth_packet.find('ipv4')
    if ip_packet is None:
      print '_handle_PacketIn:: doesnt have ip_payload; eth_packet=%s' % eth_packet
      return
    
    src_ip = (ip_packet.srcip).toStr()
    src_mac = (eth_packet.src).toStr()
    print '_handle_PacketIn:: rxed via sw_dpid=%s sw_port=%s from user_ip=%s' % (conn.dpid, event.port, src_ip)
    #handle_recv - assume only dts users know about udp_dts_port, no pre-checking
    userinfo_dict = {'user_ip': src_ip,
                     'user_mac': src_mac,
                     'gw_dpid': conn.dpid,
                     'gw_conn_port': event.port}
    msg = (ip_packet.payload).payload
    #self.scheduler.recv_from_user(userinfo_dict, msg)
    threading.Thread(target = self.scheduler.recv_from_user,
                     kwargs = {'userinfo_dict': userinfo_dict,
                               'msg': msg} ).start()
  
  def _handle_ConnectionUp(self, event):
    print "_handle_ConnectionUp:: %s" % (event.connection)
    self.dpid_conn_dict[event.connection.dpid] = event.connection
    self.install_default_to_controller(event, 17) #UDP
    #self.install_drop_sch_response(event)
  
  def _handle_FlowStatsReceived (self, event):
    print '_handle_FlowStatsReceived::'
    stats = flow_stats_to_list(event.stats)
    print "from sw",event.connection.dpid, ": ",stats
  #######################  send_*** methods  ###################################
  # Method for just sending a UDP packet over any sw port (broadcast by default)
  def send_udp_packet_out(self, conn, payload, tp_src, tp_dst,src_ip, dst_ip, 
                          src_mac, dst_mac, fw_port = of.OFPP_ALL):
    msg = of.ofp_packet_out(in_port=of.OFPP_NONE)
    msg.buffer_id = None
    #Make the udp packet
    udpp = pkt.udp()
    udpp.srcport = tp_src
    udpp.dstport = tp_dst
    udpp.payload = payload
    #Make the IP packet around it
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
    #show msg before sending
    """
    print '*******************'
    print 'msg.show(): ',msg.show()
    print '*******************'
    """
    #print "send_udp_packet_out; sw%s and fw_port:%s" %(conn.dpid, fw_port)
    conn.send(msg)
  
  def send_stat_req(self, event):
    print "ofp_stats_request is sent to sw", event.connection.dpid
    event.connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
  #########################  install_*** methods  #######################
  def install_drop_sch_response(self, event):
    fm = of.ofp_flow_mod()
    fm.priority = 0x0002 # should be higher than default_to_controller !
    fm.match.dl_type = ethernet.IP_TYPE
    fm.match.nw_src = IPAddr(info_dict['scher_vip'])
    fm.match.nw_proto = 17 #UDP
    fm.match.tp_dst = info_dict['sching_port']
    fm.idle_timeout = 0
    fm.hard_timeout = 0
    event.connection.send(fm)
    print "install_drop_sch_response is done for ", event.connection
  
  def install_default_to_controller(self, event, proto):
    fm = of.ofp_flow_mod()
    fm.priority = 1 #0x0001 # Pretty low
    fm.match.dl_type = ethernet.IP_TYPE
    fm.match.nw_proto = int(proto) #17:UDP, 6:TCP
    fm.match.tp_dst = info_dict['sching_port']
    """
    from OF Spec 1.0.0;
     If both idle_timeout and hard_timeout are zero, the entry is considered
     permanent and will never time out. It can still be removed with a flow_mod
     message of type OFPFC_DELETE
    """
    fm.idle_timeout = 0
    fm.hard_timeout = 0
    fm.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
    event.connection.send(fm)
    print "install_default_to_controller is done for ", event.connection
  ##############################################################################
def launch ():
  core.registerNew(SchController)
  

import json,pprint,os,inspect,sys,logging,time,copy
from xmlparser import XMLParser
from graphman import GraphMan
from scheduling_optimization_new import SchingOptimizer
# from perf_plot import PerfPlotter
from control_comm_intf import ControlCommIntf
from dtsuser_comm_intf import DTSUserCommIntf

cmd_subfolder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0],"ext")))
if cmd_subfolder not in sys.path:
   sys.path.insert(0, cmd_subfolder)
# to import pox modules while __name__ == "__main__"
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parentdir not in sys.path:
  sys.path.insert(0,parentdir)
  
from pox.lib.revent.revent import Event, EventMixin
class SendMsgToUser(Event):
  def __init__ (self, msg=None, userinfo_dict=None):
    Event.__init__(self)
    self.msg = msg
    self.userinfo_dict = userinfo_dict
  @property
  def get_msg(self):
    return self.msg
  @property
  def get_userinfo_dict(self):
    return self.userinfo_dict
  
class EventChief(EventMixin):
  _eventMixin_events = set([
    SendMsgToUser,
  ])
  def raise_event(self, event_type, arg1, arg2):
    if event_type == 'send_msg_to_user':
      #sargs = ["Generic"] #[sch_res, "Generic"]
      self.raiseEvent(SendMsgToUser(arg1, arg2)) #sch_res
    elif event_type == 'sth_else':
      pass
    else:
      print 'Unknown event_type: ', event_type
      raise KeyError('Unknown event_type')
#
info_dict = {'acterl_addr':('127.0.0.1',7999), #192.168.56.1
             'lacter_addr':('127.0.0.1',7998),
             'scher_vip':'10.0.0.255',
             'base_sport':6000,
             'sching_port':7000 }

BW_REG_CONST = 1 #0.95
ELAPSED_DS_REG_CONST = 1 #0.95

'''
class Scheduler(object):
def __init__(self, xml_net_num, sching_logto, data_over_tp):
def get_couplingdoneinfo_dict(self):
def get_sessionspreserved_dict(self):
def get_schingid_rescapalloc_dict(self):
def get_geninfo_dict(self):
###################################  _handle_*** methods  ##########################################
def _handle_recvfromacter(self, msg):
def _handle_sendtouser(self, userinfo_dict, msg_str):
def _handle_recvfromuser(self, userinfo_dict, msg_):
def init_network_from_xml(self):
def print_scher_state(self):
def next_sching_id(self):
def next_sch_req_id(self):
def next_tp_dst(self):
def did_user_joindts(self, user_ip):
def welcome_user(self, user_ip, user_mac, gw_dpid, gw_conn_port):
def bye_user(self, user_ip):
def welcome_session(self, p_c_ip_list, req_dict, app_pref_dict):
def bye_session(self, sch_req_id):
###################################  Sching rel methods  ###########################################
def update_sid_res_dict(self):
def give_incintkeyform(self, flag, indict):
def do_sching(self):
def get_overtcp_session_walk_rule_list__itjob_rule_dict(self, s_id, s_walk_list, s_itwalk_dict):
def exp(self):
def run_sching(self):
def test(self, num_session):
'''

class Scheduler(object):
  event_chief = EventChief()
  def __init__(self, xml_net_num, sching_logto, data_over_tp, act):
    # logging.basicConfig(filename='logs/schinglog',filemode='w',level=logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)
    #
    if not (sching_logto == 'console' or sching_logto == 'file'):
      logging.error('Unexpected sching_logto=%s', sching_logto)
      return
    self.sching_logto = sching_logto
    #
    if not (data_over_tp == 'tcp' or data_over_tp == 'udp'):
      logging.error('Unexpected data_over_tp=%s', data_over_tp)
      return
    self.data_over_tp = data_over_tp
    #
    self.net_xml_file_url = "net_xmls/net_simpler.xml" #"net_xmls/net_four_paths.xml" #"net_xmls/net_mesh_topo.xml"  #"net_xmls/net_resubmit_exp.xml"
    if not is_scheduler_run:
      self.net_xml_file_url = "ext/" + self.net_xml_file_url
    
    logging.info("Scheduler:: self.net_xml_file_url= %s", self.net_xml_file_url)
    self.xml_parser = XMLParser(self.net_xml_file_url, str(xml_net_num))
    #
    self.gm = GraphMan()
    self.init_network_from_xml()
    # self.gm.print_graph()
    # Useful state variables
    self.last_sching_id_given = -1
    self.last_sch_req_id_given = -1
    self.last_tp_dst_given = info_dict['base_sport']-1
    # Scher state dicts
    self.num_dstusers = 0
    self.users_beingserved_dict = {} #user_ip:{'gw_dpid':<>, 'gw_conn_port':<> ...}
    #
    self.N = 0 #num_activesessions
    self.alloc_dict = None
    self.sessionsbeingserved_dict = {}
    self.sessionspreserved_dict = {}
    self.sid_res_dict = {}
    self.actual_res_dict = self.gm.get_actual_resource_dict()
    # for perf plotting
    # self.perf_plotter = PerfPlotter(self.actual_res_dict)
    # for control_comm
    self.cci = ControlCommIntf()
    self.act = act
    if act:
      self.cci.reg_commpair(sctag = 'scher-acter',
                            proto = 'tcp',
                            _recv_callback = self._handle_recvfromacter,
                            s_addr = info_dict['lacter_addr'],
                            c_addr = info_dict['acterl_addr'] )
    self.dtsuser_intf = DTSUserCommIntf()
    #
    self.couplinginfo_dict = {}
    self.starting_time = time.time()
    #
    self.sid_schregid_dict = {}
    self.schingid_rescapalloc_dict = {}
    self.geninfo_dict = {}
    #
    # self.exp()
    self.s_id_elapsed_time_list_dict = {}
    self.s_id_elapsed_datasize_list_dict = {}
    
  def recv_from_user(self, userinfo_dict, msg):
    user_ip = userinfo_dict['user_ip']
    #reg everytime, in case the user is new
    self.dtsuser_intf.reg_user(user_ip = user_ip,
                               userinfo_dict = userinfo_dict,
                               _recv_callback = self._handle_recvfromuser,
                               _send_callback = self._handle_sendtouser )
    self.dtsuser_intf.pass_to_dts(user_ip = user_ip,
                                  msg =  msg )
  
  def get_couplingdoneinfo_dict(self):
    return self.couplinginfo_dict
  
  def get_sessionspreserved_dict(self):
    return self.sessionspreserved_dict
  
  def get_schingid_rescapalloc_dict(self):
    return self.schingid_rescapalloc_dict
  
  def get_geninfo_dict(self):
    return self.geninfo_dict
  ###################################  _handle_*** methods  ##########################################
  def _handle_recvfromacter(self, msg):
    [type_, data_] = msg
    if type_ == 's_sching_reply' or type_ == 'res_sching_reply':
      reply = data_['reply']
      #
      s_id = int(data_['s_id'])
      sch_req_id = self.sid_schregid_dict[s_id]
      s_info = self.sessionsbeingserved_dict[sch_req_id]
      [p_ip, c_ip] = s_info['p_c_ip_list']
      user_info = self.users_beingserved_dict[p_ip]
      userinfo_dict = {'ip': p_ip,
                       'mac': user_info['mac'],
                       'gw_dpid': user_info['gw_dpid'],
                       'gw_conn_port': user_info['gw_conn_port'] }
      if reply == 'done':
        s_info['sching_job_done'] = True
        s_alloc_info = self.alloc_dict['s-wise'][s_id]
        
        type_touser = None
        if type_ == 's_sching_reply':
          type_touser = 'sching_reply'
        elif type_ == 'res_sching_reply':
          type_touser = 'resching_reply'
        # to consumer
        if type_ == 's_sching_reply': # no need to resend for resching
          msg = {'type': type_touser,
                 'data': {'sch_req_id': sch_req_id,
                          'tp_dst': s_info['tp_dst'] } }
          if self.dtsuser_intf.relsend_to_user(user_ip = c_ip, msg = msg ) == 0:
            logging.error('_handle_recvfromacter:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
          else:
            logging.debug('_handle_recvfromacter:: sent msg=%s' % pprint.pformat(msg) )
        # to producer
        msg = {'type': type_touser,
               'data': {'sch_req_id': sch_req_id,
                        'bw': s_alloc_info['bw'],
                        'tp_dst': s_info['tp_dst'] } }
        if self.dtsuser_intf.relsend_to_user(user_ip = p_ip, msg = msg ) == 0:
          logging.error('_handle_recvfromacter:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
        else:
          logging.debug('_handle_recvfromacter:: sent msg=%s', pprint.pformat(msg) )
      else:
        logging.error('_handle_recvfromacter:: Unexpected reply=%s', reply)
        msg = {'type':'sching_reply',
               'data':'sorry' }
        if self.dtsuser_intf.relsend_to_user(user_ip = p_ip,
                                             msg = msg ) == 0:
          logging.error('_handle_recvfromacter:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
        else:
          logging.debug('_handle_recvfromacter:: sent msg=%s', pprint.pformat(msg) )
      #
    #

  def _handle_sendtouser(self, userinfo_dict, msg_str):
    Scheduler.event_chief.raise_event('send_msg_to_user', msg_str, userinfo_dict)
    
  def _handle_recvfromuser(self, userinfo_dict, msg_):
    user_ip = userinfo_dict['user_ip']
    [type_, data_] = msg_
    if type_ == 'join_req':
      if self.welcome_user(user_ip = user_ip,
                           user_mac = userinfo_dict['user_mac'],
                           gw_dpid = userinfo_dict['gw_dpid'],
                           gw_conn_port = userinfo_dict['gw_conn_port'] ):
        msg = {'type':'join_reply',
               'data':'welcome' }
        if self.dtsuser_intf.relsend_to_user(user_ip = user_ip,
                                             msg = msg ) == 0:
          logging.error('_handle_recvfromuser:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
        else:
          logging.debug('_handle_recvfromuser:: sent msg=%s', pprint.pformat(msg) )
      else:
        msg = {'type':'join_reply',
               'data':'sorry' }
        if self.dtsuser_intf.relsend_to_user(user_ip = user_ip,
                                             msg = msg ) == 0:
          logging.error('_handle_recvfromuser:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
        else:
          logging.debug('_handle_recvfromuser:: sent msg=%s', pprint.pformat(msg) )
    elif type_ == 'sching_req':
      sch_req_id = self.welcome_session(p_c_ip_list = [user_ip, data_['c_ip']],
                                        req_dict = data_['req_dict'],
                                        app_pref_dict = data_['app_pref_dict'] )
      if sch_req_id  != -1:
        # TODO: for now ...
        self.do_sching()
      else:
        msg = {'type':'sching_reply',
               'data':'sorry' }
        if self.dtsuser_intf.relsend_to_user(user_ip = user_ip,
                                             msg = msg ) == 0:
          logging.error('_handle_recvfromuser:: could not send msg=%s, \nuserinfo_dict=%s', pprint.pformat(msg), pprint.pformat(userinfo_dict) )
        else:
          logging.debug('_handle_recvfromuser:: sent msg=%s', pprint.pformat(msg) )
    elif type_ == 'session_done':
      sch_req_id = int(data_['sch_req_id'])
      del data_['sch_req_id']
      
      self.couplinginfo_dict[sch_req_id] = {}
      self.couplinginfo_dict[sch_req_id]['session_done'] = data_
      self.bye_session(sch_req_id = sch_req_id )
    elif type_ == 'coupling_done':
      sch_req_id = int(data_['sch_req_id'])
      del data_['sch_req_id']
      
      if not sch_req_id in self.couplinginfo_dict:
        self.couplinginfo_dict[sch_req_id] = {}
      self.couplinginfo_dict[sch_req_id]['coupling_done'] = data_
    
  ####################  scher_state_management  methods  #######################
  def init_network_from_xml(self):
    [node_list, edge_list] = self.xml_parser.get_node__edge_list()
    # print 'node_list= %s' % pprint.pformat(node_list)
    # print 'edge_list= %s' % pprint.pformat(edge_list)
    self.gm.graph_add_nodes(node_list)
    self.gm.graph_add_edges(edge_list)
  
  def print_scher_state(self):
    print '<---------------------------------------->'
    print 'is_scheduler_run: ', is_scheduler_run
    print 'users_beingserved_dict:'
    pprint.pprint(self.users_beingserved_dict)
    print 'sessions_beingserved_dict:'
    pprint.pprint(self.sessionsbeingserved_dict)
    print 'sessions_pre_served_dict:'
    pprint.pprint(self.sessionspreserved_dict)
    print '<---------------------------------------->'
  
  def next_sching_id(self):
    self.last_sching_id_given += 1
    return  self.last_sching_id_given
  
  def next_sch_req_id(self):
    self.last_sch_req_id_given += 1
    return  self.last_sch_req_id_given
  
  def next_tp_dst(self):
    self.last_tp_dst_given += 1
    return  self.last_tp_dst_given
  
  def did_user_joindts(self, user_ip):
    return user_ip in self.users_beingserved_dict
  
  def welcome_user(self, user_ip, user_mac, gw_dpid, gw_conn_port):
    """
    if self.did_user_joindts(user_ip):
      print 'user_ip=%s already joined' % user_ip
      return False
    """
    #
    self.users_beingserved_dict.update({user_ip:{'gw_dpid':gw_dpid,
                                                 'gw_conn_port':gw_conn_port,
                                                 'mac': user_mac } } )
    logging.info('welcome user:: ip=%s, mac=%s, gw_dpid=%s, gw_conn_port=%s', user_ip, user_mac, gw_dpid, gw_conn_port)
    return True
  
  # not used now, for future
  def bye_user(self, user_ip):
    if not self.did_user_joindts(user_ip):
      logging.error('bye_user:: user_ip=%s is not joined.', user_ip)
      return False
    #
    del self.users_beingserved_dict[user_ip]
    logging.info('bye user:: bye ip=%s', user_ip)
    return True
  
  def welcome_session(self, p_c_ip_list, req_dict, app_pref_dict):
    #sch_req_id: should be unique for every sch_session
    [p_ip, c_ip] = p_c_ip_list
    if not (self.did_user_joindts(p_ip) and self.did_user_joindts(c_ip) ):
      logging.error('welcome_session:: nonjoined user in sching_req.')
      return -1
    #
    p_c_gwtag_list = ['s'+str(self.users_beingserved_dict[p_ip]['gw_dpid']),
                      's'+str(self.users_beingserved_dict[c_ip]['gw_dpid']) ]
    #update global var, list and dicts
    self.N += 1
    sch_req_id = self.next_sch_req_id()
    self.sessionsbeingserved_dict.update(
      {sch_req_id:{'tp_dst': self.next_tp_dst(),
                   'p_c_ip_list': p_c_ip_list,
                   'p_c_gwtag_list': p_c_gwtag_list,
                   'app_pref_dict': app_pref_dict,
                   'req_dict': req_dict,
                   'sching_job_done': False }
      }
    )
    #print 'self.sessionsbeingserved_dict: '
    #pprint.pprint(self.sessionsbeingserved_dict)
    #
    return sch_req_id
  
  def bye_session(self, sch_req_id):
    self.N -= 1
    # Send sessions whose "sching job" is done is sent to pre_served category
    self.sessionspreserved_dict[sch_req_id] = self.sessionsbeingserved_dict[sch_req_id]
    path_info = self.sid_res_dict[sch_req_id]['path_info']
    self.gm.rm_user_from_edge__itr_list(path_info['edge_on_path_list'], path_info['itr_on_path_list'])
    del self.sessionsbeingserved_dict[sch_req_id]
    del self.sid_res_dict[sch_req_id]
    #
    logging.info('bye_session:: bye sch_req_id=%s, session_info=\n%s', sch_req_id, pprint.pformat(self.sessionspreserved_dict[sch_req_id]) )
  
  ###################################  Sching rel methods  ###########################################
  def update_sid_res_dict(self):
    for s_id in self.sessionsbeingserved_dict:
      if not s_id in self.sid_res_dict:
        p_c_gwtag_list = self.sessionsbeingserved_dict[s_id]['p_c_gwtag_list']
        path_info = self.gm.get_path__edge__itr_on_path_list__fair_bw_dict(p_c_gwtag_list[0], p_c_gwtag_list[1])
        self.sid_res_dict[s_id] = {'path_info': path_info}
        self.gm.add_user_to_edge__itr_list(path_info['edge_on_path_list'], path_info['itr_on_path_list'])
        logging.debug('update_sid_res_dict:: s_id=%s, path=\n%s', s_id, path_info['path'])
        
        for s_id_ in self.sid_res_dict:
          path_info_ = self.sid_res_dict[s_id_]['path_info']
          [path_bw_, path_fair_bw_] = self.gm.get_path_bw__fair_bw(path_info_['edge_on_path_list'])
          path_info_['bw'] = path_bw_
          path_info_['fair_bw'] = path_fair_bw_
    #
    
  # def update_sid_schregid_dict(self):
  #   self.sid_schregid_dict = {}
  #   #
  #   i = 0
  #   for k in self.sessionsbeingserved_dict:
  #     self.sid_schregid_dict[i] = k
  #     i += 1
  def give_incintkeyform(self, flag, indict):
    outdict = {}
    i = 0
    for k in indict:
      outdict[i] = indict[k]
      if flag:
        self.sid_schregid_dict[i]=k
      
      i += 1
    #
    return outdict
  
  def do_sching(self):
    # Currently for active sessions, gets things together to work sching logic and then sends corresponding 
    # walk/itjob rules to correspoding actuator - which is a single actuator right now !
    sching_id = self.next_sching_id()
    if self.sching_logto == 'file':
      fname = 'ext/sching_decs/sching_' + sching_id + '.log'
      logging.basicConfig(filename=fname, filemode='w', level=logging.DEBUG)
    elif self.sching_logto == 'console':
      logging.basicConfig(level=logging.DEBUG)
    
    for sch_req_id, sinfo in self.sessionsbeingserved_dict.items():
      if not sch_req_id in self.s_id_elapsed_datasize_list_dict:
        self.s_id_elapsed_datasize_list_dict[sch_req_id] = []
        self.s_id_elapsed_time_list_dict[sch_req_id] = []
      
      if 'sched_time_list' in sinfo:
        elapsed_time = time.time() - self.starting_time - sinfo['sched_time_list'][-1]
        # elapsed_datasize = sinfo['req_dict']['datasize']*elapsed_time/ #MB
        # elapsed_datasize = sinfo['req_dict']['datasize'] - float(sinfo['bw_list'][-1]*elapsed_time)/8 #MB
        elapsed_datasize = None
        tobeproced_data_transt = sinfo['tobeproced_data_transt_list'][-1]
        tobeproced_datasize = sinfo['tobeproced_datasize_list'][-1]
        if elapsed_time < tobeproced_data_transt:
          elapsed_datasize = ELAPSED_DS_REG_CONST*float(tobeproced_datasize*float(elapsed_time))/tobeproced_data_transt
        else:
          elapsed_datasize = tobeproced_datasize + float(BW_REG_CONST*(sinfo['bw_list'][-1])*elapsed_time)/8
         #
        sinfo['req_dict']['slack_metric'] = sinfo['slack_metric_list'][-1] - elapsed_time
        sinfo['req_dict']['datasize'] = max(0.01, sinfo['req_dict']['datasize'] - elapsed_datasize)
        self.s_id_elapsed_datasize_list_dict[sch_req_id].append(elapsed_datasize)
        self.s_id_elapsed_time_list_dict[sch_req_id].append(elapsed_time)
      #
    logging.info('do_sching:: sching_id=%s started;', sching_id)
    self.update_sid_res_dict()
    # self.update_sid_schregid_dict()
    sching_opter = SchingOptimizer(self.give_incintkeyform(flag = True,
                                                           indict = self.sessionsbeingserved_dict),
                                   self.actual_res_dict,
                                   self.give_incintkeyform(flag = False,
                                                           indict = self.sid_res_dict) )
    sching_opter.solve()
    #
    self.alloc_dict = sching_opter.get_sching_result()
    logging.info('do_sching:: alloc_dict=\n%s', pprint.pformat(self.alloc_dict))
    for s_id, salloc in self.alloc_dict['s-wise'].items():
      sch_req_id = self.sid_schregid_dict[s_id]
      sinfo = self.sessionsbeingserved_dict[sch_req_id]
      if not 'sched_time_list' in sinfo:
        sinfo['sched_time_list'] = []
        sinfo['slack_metric_list'] = []
        sinfo['bw_list'] = []
        sinfo['datasize_list'] = []
        sinfo['tobeproced_datasize_list'] = []
        sinfo['tobeproced_data_transt_list'] = []
      #
      sinfo['sched_time_list'].append(time.time() - self.starting_time)
      sinfo['slack_metric_list'].append(sinfo['req_dict']['slack_metric'])
      sinfo['bw_list'].append(salloc['bw'])
      sinfo['datasize_list'].append(sinfo['req_dict']['datasize'])
      sinfo['tobeproced_datasize_list'].append(salloc['tobeproced_datasize'])
      sinfo['tobeproced_data_transt_list'].append(salloc['tobeproced_data_transt'])
      
      sinfo['trans_time'] = salloc['trans_time']
      sinfo['elapsed_datasize_list'] = self.s_id_elapsed_datasize_list_dict[sch_req_id]
      sinfo['elapsed_time_list'] = self.s_id_elapsed_time_list_dict[sch_req_id]
    # Resource capacity allocation distribution over sessions
    self.schingid_rescapalloc_dict[sching_id] = self.alloc_dict['res-wise']
    self.geninfo_dict = self.alloc_dict['general']
    
    # logging.info('saving sching_dec to figs...')
    # self.perf_plotter.save_sching_result(g_info_dict = self.alloc_dict['general'],
    #                                     s_info_dict = self.alloc_dict['s-wise'],
    #                                     res_info_dict = self.alloc_dict['res-wise'])
    # Convert sching decs to rules
    for s_id in range(self.N):
      s_allocinfo_dict = self.alloc_dict['s-wise'][s_id]
      
      s_itwalk_dict = s_allocinfo_dict['itwalk_dict']
      s_walk_list = s_allocinfo_dict['walk_list']
      if not self.data_over_tp == 'tcp':
        logging.error("do_sching:: Unexpected data_over_tp= %s", self.data_over_tp)
      #
      [walk_rule_list, itjob_rule_dict] = \
        self.get_overtcp_session_walk_rule_list__itjob_rule_dict(s_id,
                                                                 s_walk_list = s_walk_list,
                                                                 s_itwalk_dict = s_itwalk_dict)
      s_info = self.sessionsbeingserved_dict[self.sid_schregid_dict[s_id]]
      s_info['slack-tt'] = s_allocinfo_dict['slack-tt']
      s_info['slack-transtime'] = abs(s_allocinfo_dict['trans_time']-s_info['req_dict']['slack_metric'])
      # logging.debug('for s_id= %s;', s_id)
      # logging.debug('walk_rule_list= \n%s', pprint.pformat(walk_rule_list) )
      # logging.debug('itjob_rule_dict= \n%s', pprint.pformat(itjob_rule_dict) )
      # Dispatching rule to actuator_actuator
      if s_info['sching_job_done'] == False:
        type_toacter = 's_sching_req'
      else:
        type_toacter = 'res_sching_req'
      
      msg = json.dumps({'type': type_toacter,
                        'data': {'s_id': s_id,
                                 'walk_rule_list': walk_rule_list,
                                 'itjob_rule_dict': itjob_rule_dict } } )
      self.cci.send_to_client('scher-acter', msg)
      #
    #  
    logging.info('do_sching:: sching_id= %s done.', sching_id)
  
  def get_overtcp_session_walk_rule_list__itjob_rule_dict(self, s_id, s_walk_list, s_itwalk_dict):
    def get_port_name(dpid, port):
      return 's' + str(dpid) + '-eth' + str(port)
    #
    def chop_swalk_into_tcppaths():
      chopped_swalk_list = []
      cur_chop_id = 0
      #
      l_ = list(enumerate(s_walk_list))
      for i, node_str in l_:
        node = self.gm.get_node(node_str)
        node_type = node['type']
        if i == 0:
          if node_type != 'sw':
            logging.error('right after p only sw type is allowed! what is found=(%s, %s)', node_str, node_type)
            system.exit(2)
          #
          chopped_swalk_list.append(['p', node_str])
        elif i == len(l_) - 1:
          if node_type != 'sw':
            logging.error('right before c only sw type is allowed! what is found=(%s, %s)', node_str, node_type)
            system.exit(2)
          #
          chopped_swalk_list[cur_chop_id].append(node_str)
          chopped_swalk_list[cur_chop_id].append('c')
        else: # i is pointing to intermediate pwalk_nodes
          if node_type == 'sw':
            chopped_swalk_list[cur_chop_id].append(node_str)
          elif node_type == 't':
            chopped_swalk_list[cur_chop_id].append(node_str)
            cur_chop_id += 1
            chopped_swalk_list.append([node_str])
        #
      return chopped_swalk_list
    #
    chopped_swalk_list = chop_swalk_into_tcppaths()
    #
    # print '---> for s_id= %s' % (s_id)
    # print 's_itwalk_dict= \n%s' % pprint.pformat(s_itwalk_dict)
    # print 's_walk_list= \n%s' % s_walk_list
    # print 'chopped_swalk_list= \n%s' % pprint.pformat(chopped_swalk_list)
    itjob_rule_dict = {}
    walk_rule_list = []
    
    s_info_dict =  self.sessionsbeingserved_dict[self.sid_schregid_dict[s_id]]
    s_tp_dst = s_info_dict['tp_dst']
    p_c_ip_list = s_info_dict['p_c_ip_list']
    
    duration = 0
    [from_ip, to_ip] = p_c_ip_list
    p_info_dict = self.users_beingserved_dict[from_ip]
    c_info_dict = self.users_beingserved_dict[to_ip]
    [from_mac, to_mac] = [p_info_dict['mac'], c_info_dict['mac']]
    #
    first_itr_done = False
    uptoitrjob_list = []
    #
    for i, swalk_chop in enumerate(chopped_swalk_list):
      chop_walk_rule_list = []
      head_i, tail_i = 0, len(swalk_chop) - 1
      head_str, tail_str = swalk_chop[head_i], swalk_chop[tail_i]
      head_ip, tail_ip = None, None
      try:
        chop_head = self.gm.get_node(head_str)
        head_ip, head_mac = chop_head['ip'], chop_head['mac']
      except KeyError: #head_str = 'p'
        head_ip, head_mac = from_ip, from_mac
      try:
        chop_tail = self.gm.get_node(tail_str)
        tail_ip, tail_mac = chop_tail['ip'], chop_tail['mac']
      except KeyError: #tail_str = 'c'
        tail_ip, tail_mac = to_ip, to_mac
      # Extract forward route from head to tail
      # print 'extracting forward route >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
      for j in range(head_i+1, tail_i-1): #sws in [head_sw, tail_sw)
        sw_str = swalk_chop[j]
        sw = self.gm.get_node(sw_str)
        forward_edge = self.gm.get_edge((sw_str, swalk_chop[j+1]))
        tail_ip_ = tail_ip
        if head_str == 'p':
          tail_ip_ = to_ip
        # print 'sw_str= %s, swalk_chop[j+1]= %s, forward_edge= %s' % (sw_str, swalk_chop[j+1], pprint.pformat(forward_edge) )
        chop_walk_rule_list.append({'conn': [sw['dpid'], head_ip],
                                    'typ': 'forward',
                                    'wc': [head_ip, tail_ip_, 6, -1, int(s_tp_dst)],
                                    'rule': [forward_edge['pre_dev'], duration] })
      # Extract backward route from tail to head
      # print 'extracting backward route >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
      for j in range(head_i+2, tail_i): #sws in (head_sw-tail_sw]
        sw_str = swalk_chop[j]
        sw = self.gm.get_node(sw_str)
        backward_edge = self.gm.get_edge((swalk_chop[j-1], sw_str))
        # print 'swalk_chop[j-1]= %s, sw_str= %s, backward_edge= %s' % (swalk_chop[j-1], sw_str, pprint.pformat(backward_edge) )
        chop_walk_rule_list.append({'conn': [sw['dpid'], tail_ip],
                                    'typ': 'forward',
                                    'wc': [tail_ip, head_ip, 6, int(s_tp_dst), -1],
                                    'rule': [backward_edge['post_dev'], duration] })
      # Extract forward (if tail is itr) or modify_forward (if tail is c)
      # Tail
      tail_sw_str = swalk_chop[tail_i-1]
      tail_sw = self.gm.get_node(tail_sw_str)
      to_tail_sw_port_name, type_, rule_list = None, None, None
      tail_ip_ = tail_ip
      if tail_str == 'c':
        to_tail_sw_port_name = get_port_name(dpid = c_info_dict['gw_dpid'],
                                             port = c_info_dict['gw_conn_port'])
        type_ = 'forward'
        rule_list = [to_tail_sw_port_name, duration]
      else: # itr
        to_tail_sw_port_name = self.gm.get_edge((tail_sw_str, tail_str))['pre_dev']
        if first_itr_done:
          type_ = 'forward'
          rule_list = [to_tail_sw_port_name, duration]
        else: # first itr
          type_ = 'mod_nw_dst__forward'
          rule_list = [tail_ip, tail_mac, to_tail_sw_port_name, duration]
          first_itr_done = True
          tail_ip_ = to_ip
        #
      # print 'tail_sw_str= %s, tail_str= %s, to_tail_sw_port_name= %s' % (tail_sw_str, tail_str, to_tail_sw_port_name)
      chop_walk_rule_list.append({
        'conn': [tail_sw['dpid'], head_ip],
        'typ': type_,
        'wc': [head_ip, tail_ip_, 6, -1, int(s_tp_dst)],
        'rule': rule_list })
      # Extract backward (if head is itr) or modify_backward (if head is p) route to head
      head_sw_str = swalk_chop[head_i + 1]
      head_sw = self.gm.get_node(head_sw_str)
      to_head_sw_port_name, type_, rule_list = None, None, None
      if head_str == 'p':
        to_head_sw_port_name = get_port_name(dpid = p_info_dict['gw_dpid'],
                                             port = p_info_dict['gw_conn_port'])
        type_ = 'mod_nw_src__forward'
        rule_list = [to_ip, to_mac, to_head_sw_port_name, duration]
      else: # head is itr
        head_edge = self.gm.get_edge((head_sw_str, head_str))
        to_head_sw_port_name = head_edge['pre_dev']
        type_ = 'forward'
        rule_list = [to_head_sw_port_name, duration]
        # Fill up it_job_rule for the itr
        assigned_job = s_itwalk_dict['itr_info_dict'][head_str]
        if not (tail_sw['dpid'] in itjob_rule_dict):
          itjob_rule_dict[head_sw['dpid']] = []
        itjob_rule_dict[head_sw['dpid']].append({
          'proto': 6,
          'itr_ip': head_ip,
          'itr_mac': head_mac,
          'swdev_to_itr': to_head_sw_port_name,
          'assigned_job': assigned_job,
          'uptoitrjob_list': copy.copy(uptoitrjob_list),
          's_tp_dst': int(s_tp_dst),
          'to_ip': tail_ip,
          'datasize': s_itwalk_dict['info']['datasize'],
          'bw': s_itwalk_dict['info']['bw'] })
          #
        uptoitrjob_list.append(assigned_job)
      #
      # print 'head_str= %s, head_sw_str= %s, to_head_sw_port_name= %s' % (head_str, head_sw_str, to_head_sw_port_name)
      chop_walk_rule_list.append({
        'conn': [head_sw['dpid'], tail_ip],
        'typ': type_,
        'wc': [tail_ip, head_ip, 6, int(s_tp_dst), -1],
        'rule': rule_list })
      #
      walk_rule_list += chop_walk_rule_list
      
    return [walk_rule_list, itjob_rule_dict]

  def exp(self):
    print '*** exp::'
    userinfo_list = [ {'user_ip':'10.0.1.0','user_mac':'00:00:00:01:01:00','gw_dpid':12, 'gw_conn_port':2} ]
    # userinfo_list = [ {'user_ip':'10.0.2.0','user_mac':'00:00:00:01:02:00','gw_dpid':1, 'gw_conn_port':3},
    #                   {'user_ip':'10.0.2.1','user_mac':'00:00:00:01:02:01','gw_dpid':1, 'gw_conn_port':4},
    #                   {'user_ip':'10.0.1.0','user_mac':'00:00:00:01:01:00','gw_dpid':2, 'gw_conn_port':3},
    #                   {'user_ip':'10.0.1.1','user_mac':'00:00:00:01:01:01','gw_dpid':2, 'gw_conn_port':4} ]
    
    for userinfo in userinfo_list:
      self.welcome_user(user_ip = userinfo['user_ip'],
                        user_mac = userinfo['user_mac'],
                        gw_dpid = userinfo['gw_dpid'],
                        gw_conn_port = userinfo['gw_conn_port'] )
      
      
      self.dtsuser_intf.reg_user(user_ip = userinfo['user_ip'],
                                 userinfo_dict = userinfo,
                                 _recv_callback = self._handle_recvfromuser,
                                 _send_callback = self._handle_sendtouser )
    print '***'
  
  def run_sching(self):
    self.update_sid_res_dict()
    sching_opter = SchingOptimizer(self.give_incintkeyform(flag=True,
                                                           indict=self.sessionsbeingserved_dict),
                                   self.actual_res_dict,
                                   self.give_incintkeyform(flag=False,
                                                           indict=self.sid_res_dict) )
    sching_opter.solve()
  
  def test(self, num_session):
    userinfo_list = None
    if self.net_xml_file_url == "net_xmls/net_four_paths.xml":
      userinfo_list = [{'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':20, 'gw_conn_port':3},
                       {'user_ip':'10.0.2.1', 'user_mac':'00:00:00:01:02:01', 'gw_dpid':21, 'gw_conn_port':4},
                       {'user_ip':'10.0.2.2', 'user_mac':'00:00:00:01:02:02', 'gw_dpid':22, 'gw_conn_port':4},
                       {'user_ip':'10.0.2.3', 'user_mac':'00:00:00:01:02:03', 'gw_dpid':23, 'gw_conn_port':3},
                       {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':10, 'gw_conn_port':3},
                       {'user_ip':'10.0.1.1', 'user_mac':'00:00:00:01:01:01', 'gw_dpid':11, 'gw_conn_port':4},
                       {'user_ip':'10.0.1.2', 'user_mac':'00:00:00:01:01:02', 'gw_dpid':12, 'gw_conn_port':4},
                       {'user_ip':'10.0.1.3', 'user_mac':'00:00:00:01:01:03', 'gw_dpid':13, 'gw_conn_port':3} ]
    elif self.net_xml_file_url == 'net_xmls/net_simpler.xml':
      userinfo_list = [{'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':1, 'gw_conn_port':3},
                       {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':2, 'gw_conn_port':3} ]
    elif self.net_xml_file_url == 'net_xmls/net_mesh_topo.xml':
      userinfo_list = [{'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':20, 'gw_conn_port':3},
                       {'user_ip':'10.0.2.1', 'user_mac':'00:00:00:01:02:01', 'gw_dpid':20, 'gw_conn_port':4},
                       {'user_ip':'10.0.2.2', 'user_mac':'00:00:00:01:02:02', 'gw_dpid':20, 'gw_conn_port':5},
                       {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':10, 'gw_conn_port':3},
                       {'user_ip':'10.0.1.1', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':10, 'gw_conn_port':4},
                       {'user_ip':'10.0.1.2', 'user_mac':'00:00:00:01:01:01', 'gw_dpid':10, 'gw_conn_port':5} ]
    elif self.net_xml_file_url == 'net_xmls/net_resubmit_exp.xml':
      userinfo_list = [{'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':11, 'gw_conn_port':3},
                       {'user_ip':'10.0.2.1', 'user_mac':'00:00:00:01:02:01', 'gw_dpid':11, 'gw_conn_port':4},
                       {'user_ip':'10.0.2.2', 'user_mac':'00:00:00:01:02:02', 'gw_dpid':11, 'gw_conn_port':5},
                       {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':12, 'gw_conn_port':3},
                       {'user_ip':'10.0.1.1', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':12, 'gw_conn_port':4},
                       {'user_ip':'10.0.1.2', 'user_mac':'00:00:00:01:01:01', 'gw_dpid':12, 'gw_conn_port':5} ]
    #
    for userinfo in userinfo_list:
      self.welcome_user(user_ip = userinfo['user_ip'],
                        user_mac = userinfo['user_mac'],
                        gw_dpid = userinfo['gw_dpid'],
                        gw_conn_port = userinfo['gw_conn_port'] )
    #
    #datasize (MB) slack_metric (ms)
    req_dict_list = [ {'datasize':100, 'slack_metric':100, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':100, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':100, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':100, 'func_list':['fft','upsampleplot']}
                    ]
    app_pref_dict_list = [
                          {'m_p': 10,'m_u': 0,'x_p': 0,'x_u': 0},
                          {'m_p': 0,'m_u': 50,'x_p': 0,'x_u': 0},
                          {'m_p': 50,'m_u': 0,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0}
                         ]
    p_c_ip_list_list = [
                        ['10.0.2.0','10.0.1.0'],
                        ['10.0.2.1','10.0.1.1'],
                        ['10.0.2.2','10.0.1.2'],
                        ['10.0.2.3','10.0.1.3']
                       ]
    for i in range(num_session):
      self.welcome_session(p_c_ip_list = p_c_ip_list_list[int(i%4)],
                           req_dict = req_dict_list[int(i%4)],
                           app_pref_dict = app_pref_dict_list[int(i%4)] )
    #
    # self.run_sching()
    self.do_sching()
    
    # net_edge_list = self.gm.path_to_netedgelist(s_path)
    # itr_list = self.gm.get_itrlist_on_path(s_path)
    # if not (s_id in self.sid_res_dict):
    #   self.sid_res_dict[s_id] = {'s_info':{}, 'path_info':{}}
    # self.sid_res_dict[s_id]['path_info'].update(
    #   {'path': s_path,
    #   'edge_on_path_list': net_edge_list,
    #   'itr_on_path_list': itr_list } )
    #
    
    # for s_id in range(self.N):
    #   p_c_gwtag_list = self.sessionsbeingserved_dict[s_id]['p_c_gwtag_list']
    #   [path, edge_on_path_list, itr_on_path_list] = \
    #     self.gm.get_path__edge__itr_on_path_list(p_c_gwtag_list[0], p_c_gwtag_list[1])
    #   self.gm.add_user_to_edge__itr_list(edge_on_path_list, itr_on_path_list)
    #   print 'test:: s_id= %s, path= %s' % (s_id, path)

is_scheduler_run = False
def main():
  global is_scheduler_run
  is_scheduler_run = True
  sch = Scheduler(xml_net_num = 1,
                  sching_logto = 'console',
                  data_over_tp = 'tcp',
                  act = False)
  
  sch.test(num_session = 4)
  #
  raw_input('Enter')
  
if __name__ == "__main__":
  main()
  

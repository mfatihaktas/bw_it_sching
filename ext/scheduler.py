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

BWREGCONST = 1 #0.95
ELAPSEDDSREGCONST = 1 #0.95

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
  def __init__(self, xml_net_num, sching_logto, data_over_tp):
    #logging.basicConfig(filename='logs/schinglog',filemode='w',level=logging.DEBUG)
    #logging.basicConfig(level=logging.ERROR)
    #logging.basicConfig(level=logging.WARNING)
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
    net_xml_file_url = "net_xmls/net_mesh_topo.xml" #"net_xmls/net_resubmit_exp.xml" #"net_xmls/net_1p_singletr.xml" #"net_xmls/grenet_multipaths.xml" #"net_xmls/grenet_gbit_1p_singletr.xml" #"net_xmls/grenet_1p_singletr.xml"
    if not is_scheduler_run:
      net_xml_file_url = "ext/" + net_xml_file_url
    
    self.xml_parser = XMLParser(net_xml_file_url, str(xml_net_num))
    #
    self.gm = GraphMan()
    self.init_network_from_xml()
    self.gm.print_graph()
    #Useful state variables
    self.last_sching_id_given = -1
    self.last_sch_req_id_given = -1
    self.last_tp_dst_given = info_dict['base_sport']-1
    #Scher state dicts
    self.num_dstusers = 0
    self.users_beingserved_dict = {} #user_ip:{'gw_dpid':<>, 'gw_conn_port':<> ...}
    #
    self.N = 0 #num_activesessions
    self.alloc_dict = None
    self.sessionsbeingserved_dict = {}
    self.sessionspreserved_dict = {}
    self.sid_res_dict = {}
    self.actual_res_dict = self.gm.get_actual_resource_dict()
    #for perf plotting
    #self.perf_plotter = PerfPlotter(self.actual_res_dict)
    #for control_comm
    self.cci = ControlCommIntf()
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
    #msg = [type_, data_]l
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
        #get s_alloc_info
        s_alloc_info = self.alloc_dict['s-wise'][s_id]
        #
        type_touser = None
        if type_ == 's_sching_reply':
          type_touser = 'sching_reply'
        elif type_ == 'res_sching_reply':
          type_touser = 'resching_reply'
        #to producer
        msg = {'type':type_touser,
               'data':{'sch_req_id': sch_req_id,
                       'bw':s_alloc_info['bw'],
                       'tp_dst':s_info['tp_dst'] } }
        if self.dtsuser_intf.relsend_to_user(user_ip = p_ip,
                                             msg = msg ) == 0:
          print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
        else:
          print 'sent msg=%s' % pprint.pformat(msg)
        #to consumer
        if type_ == 's_sching_reply': #no need to resend for resching
          msg = {'type':type_touser,
                 'data':{'sch_req_id': sch_req_id,
                         'tp_dst':s_info['tp_dst'] } }
          if self.dtsuser_intf.relsend_to_user(user_ip = c_ip,
                                               msg = msg ) == 0:
            print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
          else:
            print 'sent msg=%s' % pprint.pformat(msg)
      else:
        logging.error('_handle_recvfromacter:: Unexpected reply=%s', reply)
        msg = {'type':'sching_reply',
               'data':'sorry' }
        if self.dtsuser_intf.relsend_to_user(user_ip = p_ip,
                                             msg = msg ) == 0:
          print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
        else:
          print 'sent msg=%s' % pprint.pformat(msg)
      #
    #

  def _handle_sendtouser(self, userinfo_dict, msg_str):
    Scheduler.event_chief.raise_event('send_msg_to_user', msg_str, userinfo_dict)
    
  def _handle_recvfromuser(self, userinfo_dict, msg_):
    user_ip = userinfo_dict['user_ip']
    #
    [type_, data_] = msg_
    #
    if type_ == 'join_req':
      if self.welcome_user(user_ip = user_ip,
                           user_mac = userinfo_dict['user_mac'],
                           gw_dpid = userinfo_dict['gw_dpid'],
                           gw_conn_port = userinfo_dict['gw_conn_port'] ):
        msg = {'type':'join_reply',
               'data':'welcome' }
        if self.dtsuser_intf.relsend_to_user(user_ip = user_ip,
                                             msg = msg ) == 0:
          print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
        else:
          print 'sent msg=%s' % pprint.pformat(msg)
      else:
        msg = {'type':'join_reply',
               'data':'sorry' }
        if self.dtsuser_intf.relsend_to_user(user_ip = user_ip,
                                             msg = msg ) == 0:
          print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
        else:
          print 'sent msg=%s' % pprint.pformat(msg)
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
          print 'Couldnt send msg=%s, \nuserinfo_dict=%s' % (pprint.pformat(msg), pprint.pformat(userinfo_dict))
        else:
          print 'sent msg=%s' % pprint.pformat(msg)
    elif type_ == 'session_done':
      sch_req_id = int(data_['sch_req_id'])
      del data_['sch_req_id']
      
      self.couplinginfo_dict[sch_req_id] = {}
      self.couplinginfo_dict[sch_req_id]['session_done'] = data_
      self.bye_session(sch_req_id = sch_req_id )
    elif type_ == 'coupling_done':
      sch_req_id = int(data_['sch_req_id'])
      del data_['sch_req_id']
      
      self.couplinginfo_dict[sch_req_id]['coupling_done'] = data_
    
  ####################  scher_state_management  methods  #######################
  def init_network_from_xml(self):
    node_edge_lst = self.xml_parser.give_node_and_edge_list_from_xml()
    #print 'node_lst:'
    #pprint.pprint(node_edge_lst['node_lst'])
    #print 'edge_lst:'
    #pprint.pprint(node_edge_lst['edge_lst'])
    self.gm.graph_add_nodes(node_edge_lst['node_lst'])
    self.gm.graph_add_edges(node_edge_lst['edge_lst'])
  
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
  
  #not used now, for future
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
    del self.sessionsbeingserved_dict[sch_req_id]
    del self.sid_res_dict[sch_req_id]
    #
    logging.info('bye_session:: bye sch_req_id=%s, session_info=\n%s', sch_req_id, pprint.pformat(self.sessionspreserved_dict[sch_req_id]) )
  
  ###################################  Sching rel methods  ###########################################
  def update_sid_res_dict(self):
    for s_id in self.sessionsbeingserved_dict:
      if not s_id in self.sid_res_dict:
        p_c_gwtag_list = self.sessionsbeingserved_dict[s_id]['p_c_gwtag_list']
        [path, edge_on_path_list, itr_on_path_list] = \
          self.gm.get_path__edge__itr_on_path_list(p_c_gwtag_list[0], p_c_gwtag_list[1])
        logging.debug('update_sid_res_dict:: s_id=%s, path=\n%s', s_id, path)
        
        self.sid_res_dict[s_id] = {'s_info':{}, 'path_info':{}}
        self.sid_res_dict[s_id]['path_info'].update(
          {'path': path,
           'edge_on_path_list': edge_on_path_list,
           'itr_on_path_list': itr_on_path_list } )
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
      fname = 'ext/sching_decs/sching_'+sching_id+'.log'
      logging.basicConfig(filename=fname,filemode='w',level=logging.DEBUG)
    elif self.sching_logto == 'console':
      logging.basicConfig(level=logging.DEBUG)

    for sch_req_id, sinfo in self.sessionsbeingserved_dict.items():
      if 'sched_time_list' in sinfo:
        elapsed_time = (time.time() - self.starting_time - sinfo['sched_time_list'][-1])
        # elapsed_datasize = sinfo['req_dict']['datasize']*elapsed_time/ #MB
        # elapsed_datasize = sinfo['req_dict']['datasize'] - float(sinfo['bw_list'][-1]*elapsed_time)/8 #MB
        elapsed_datasize = None
        tobeproced_data_transt = sinfo['tobeproced_data_transt_list'][-1]
        tobeproced_datasize = sinfo['tobeproced_datasize_list'][-1]
        if elapsed_time < tobeproced_data_transt:
          elapsed_datasize = ELAPSEDDSREGCONST*float(tobeproced_datasize*float(elapsed_time))/tobeproced_data_transt
        else:
          elapsed_datasize = tobeproced_datasize + float(BWREGCONST*(sinfo['bw_list'][-1])*elapsed_time)/8
         #
        sinfo['req_dict']['slack_metric'] = sinfo['slack_metric_list'][-1] - elapsed_time
        sinfo['req_dict']['datasize'] -= elapsed_datasize
      #
    logging.info('do_sching:: sching_id=%s started;', sching_id)
    self.update_sid_res_dict()
    # self.update_sid_schregid_dict()
    sching_opter = SchingOptimizer(self.give_incintkeyform(flag=True,
                                                           indict=self.sessionsbeingserved_dict),
                                   self.actual_res_dict,
                                   self.give_incintkeyform(flag=False,
                                                           indict=self.sid_res_dict) )
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
      logging.info('for s_id= %s;', s_id)
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
    logging.info('do_sching:: sching_id=%s done.', sching_id)
  
  def get_overtcp_session_walk_rule_list__itjob_rule_dict(self, s_id, s_walk_list, s_itwalk_dict):
    def get_touser_swportname(dpid, port):
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
    # print '---> for s_id=%s' % (s_id)
    # print 's_itwalk_dict='
    # pprint.pprint(s_itwalk_dict)
    # print 's_walk_list=', s_walk_list
    # print 'chopped_swalk_list='
    # pprint.pprint(chopped_swalk_list)
    itjob_rule_dict = {}
    walk_rule_list = []
    
    s_info_dict =  self.sessionsbeingserved_dict[self.sid_schregid_dict[s_id]]
    s_tp_dst = s_info_dict['tp_dst']
    p_c_ip_list = s_info_dict['p_c_ip_list']
    
    duration = 0
    from_ip = p_c_ip_list[0]
    to_ip = p_c_ip_list[1]
    p_info_dict = self.users_beingserved_dict[from_ip]
    c_info_dict = self.users_beingserved_dict[to_ip]
    from_mac = p_info_dict['mac']
    to_mac = c_info_dict['mac']
    #
    uptoitrjob_list = []
    #
    for i, swalk_chop in list(enumerate(chopped_swalk_list)):
      chop_walk_rule_list = []
      head_i, tail_i = 0, len(swalk_chop) - 1
      head_str, tail_str = swalk_chop[head_i], swalk_chop[tail_i]
      head_ip, tail_ip = None, None
      try:
        chop_head = self.gm.get_node(head_str)
        head_ip = chop_head['ip']
      except KeyError: #head_str = 'p'
        head_ip = from_ip
      try:
        chop_tail = self.gm.get_node(tail_str)
        tail_ip, tail_mac = chop_tail['ip'], chop_tail['mac']
      except KeyError: #tail_str = 'c'
        tail_ip, tail_mac = to_ip, to_mac
      # Extract forward route from head to tail
      for j in range(head_i + 1, tail_i - 1): #sws in [head_sw, tail_sw)
        sw_str = swalk_chop[j]
        sw = self.gm.get_node(sw_str)
        forward_edge = self.gm.get_edge((sw_str, swalk_chop[j + 1]))
        chop_walk_rule_list.append({'conn': [sw['dpid'], head_ip],
                                    'typ': 'forward',
                                    'wc': [head_ip, to_ip, 6, -1, int(s_tp_dst)],
                                    'rule': [forward_edge['pre_dev'], duration] })
      # Extract backward route from tail to head
      for j in range(head_i + 2, tail_i): #sws in (head_sw-tail_sw]
        sw_str = swalk_chop[j]
        sw = self.gm.get_node(sw_str)
        backward_edge = self.gm.get_edge((swalk_chop[j-1], sw_str))
        chop_walk_rule_list.append({'conn': [sw['dpid'], tail_ip],
                                    'typ': 'forward',
                                    'wc': [tail_ip, head_ip, 6, int(s_tp_dst), -1],
                                    'rule': [backward_edge['post_dev'], duration] })
      # Extract modify_forward route to tail, and fill up itjob_rule
      tailsw_str = swalk_chop[tail_i-1]
      tailsw = self.gm.get_node(tailsw_str)
      totail_swportname = None
      if tail_str == 'c':
        totail_swportname = get_touser_swportname(dpid = c_info_dict['gw_dpid'],
                                                  port = c_info_dict['gw_conn_port'])
        chop_walk_rule_list.append(
          {'conn': [tailsw['dpid'], head_ip],
           'typ': 'forward',
           'wc': [head_ip, to_ip, 6, -1, int(s_tp_dst)],
           'rule': [totail_swportname, duration] } )
      else: # tail is another itres        
        tail_edge = self.gm.get_edge((tailsw_str, tail_str))
        totail_swportname = tail_edge['pre_dev']
        chop_walk_rule_list.append(
          {'conn': [tailsw['dpid'], head_ip],
            'typ': 'mod_nw_dst__forward',
            'wc': [head_ip, to_ip, 6, -1, int(s_tp_dst)],
            'rule': [tail_ip, tail_mac, totail_swportname, duration] } )
        # Fill up it_job_rule for the itres
        assigned_job = s_itwalk_dict['itr_info_dict'][tail_str]
        if not (tailsw['dpid'] in itjob_rule_dict):
          itjob_rule_dict[tailsw['dpid']] = [{
            'proto': 6,
            'tpr_ip': tail_ip,
            'tpr_mac': tail_mac,
            'swdev_to_tpr': totail_swportname,
            'assigned_job': assigned_job,
            'uptoitrjob_list': copy.copy(uptoitrjob_list),
            'session_tp': int(s_tp_dst),
            'consumer_ip': to_ip,
            'datasize': s_itwalk_dict['info']['datasize'],
            'bw': s_itwalk_dict['info']['bw'] }]
        else:
          itjob_rule_dict[tailsw['dpid']].append( {
            'proto': 6,
            'tpr_ip': tail_ip,
            'tpr_mac': tail_mac,
            'swdev_to_tpr': totail_swportname,
            'assigned_job': assigned_job,
            'uptoitrjob_list': copy.copy(uptoitrjob_list),
            'session_tp': int(s_tp_dst),
            'consumer_ip': to_ip,
            'datasize': s_itwalk_dict['info']['datasize'],
            'bw': s_itwalk_dict['info']['bw'] } )
        #
        uptoitrjob_list.append(assigned_job)
      #
      
      # Extract modify_backward route to head
      headsw_str = swalk_chop[head_i + 1]
      headsw = self.gm.get_node(headsw_str)
      tohead_swportname = None
      if head_str == 'p':
        tohead_swportname = get_touser_swportname(dpid = p_info_dict['gw_dpid'],
                                                  port = p_info_dict['gw_conn_port'])
      else: # head is another itres
        headedge = self.gm.get_edge((head_str, headsw_str))
        tohead_swportname = headedge['pre_dev']
      #
      chop_walk_rule_list.append({'conn':[headsw['dpid'],tail_ip],
                      'typ':'mod_nw_src__forward',
                      'wc':[tail_ip,head_ip,6,int(s_tp_dst),-1],
                      'rule':[to_ip, to_mac, tohead_swportname, duration] })
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
    # For net_mesh_topo.xml
    userinfo_list = [ {'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':21, 'gw_conn_port':3},
                      {'user_ip':'10.0.2.1', 'user_mac':'00:00:00:01:02:01', 'gw_dpid':21, 'gw_conn_port':4},
                      {'user_ip':'10.0.2.2', 'user_mac':'00:00:00:01:02:02', 'gw_dpid':21, 'gw_conn_port':5},
                      {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':11, 'gw_conn_port':3},
                      {'user_ip':'10.0.1.1', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':11, 'gw_conn_port':4},
                      {'user_ip':'10.0.1.2', 'user_mac':'00:00:00:01:01:01', 'gw_dpid':11, 'gw_conn_port':5} ]
    # For net_resubmit_exp.xml
    # userinfo_list = [ {'user_ip':'10.0.2.0', 'user_mac':'00:00:00:01:02:00', 'gw_dpid':1, 'gw_conn_port':3},
    #                   {'user_ip':'10.0.2.1', 'user_mac':'00:00:00:01:02:01', 'gw_dpid':1, 'gw_conn_port':4},
    #                   {'user_ip':'10.0.2.2', 'user_mac':'00:00:00:01:02:02', 'gw_dpid':1, 'gw_conn_port':5},
    #                   {'user_ip':'10.0.1.0', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':2, 'gw_conn_port':3},
    #                   {'user_ip':'10.0.1.1', 'user_mac':'00:00:00:01:01:00', 'gw_dpid':2, 'gw_conn_port':4},
    #                   {'user_ip':'10.0.1.2', 'user_mac':'00:00:00:01:01:01', 'gw_dpid':2, 'gw_conn_port':5},
    #                   {'user_ip':'10.0.2.20', 'user_mac':'00:00:00:01:02:20', 'gw_dpid':11, 'gw_conn_port':2},
    #                   {'user_ip':'10.0.1.20', 'user_mac':'00:00:00:01:01:20', 'gw_dpid':21, 'gw_conn_port':2} ]
    #
    for userinfo in userinfo_list:
      self.welcome_user(user_ip = userinfo['user_ip'],
                        user_mac = userinfo['user_mac'],
                        gw_dpid = userinfo['gw_dpid'],
                        gw_conn_port = userinfo['gw_conn_port'] )
    #
    #datasize (MB) slack_metric (ms)
    req_dict_list = [ {'datasize':100, 'slack_metric':300, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':300, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':300, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':300, 'func_list':['fft','upsampleplot']},
                      {'datasize':100, 'slack_metric':300, 'func_list':['fft','upsampleplot']},
                    ]
    app_pref_dict_list = [
                          {'m_p': 0.5,'m_u': 0.5,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 2,'m_u': 2,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                         ]
    p_c_ip_list_list = [
                        ['10.0.2.0','10.0.1.0'],
                        ['10.0.2.1','10.0.1.1'],
                        ['10.0.2.2','10.0.1.2']
                       ]
    for i in range(num_session):
      self.welcome_session(p_c_ip_list = p_c_ip_list_list[int(i%3)],
                           req_dict = req_dict_list[int(i%5)],
                           app_pref_dict = app_pref_dict_list[int(i%5)] )
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
    
def main():
  global is_scheduler_run
  is_scheduler_run = True
  sch = Scheduler(xml_net_num = 1,
                  sching_logto = 'console',
                  data_over_tp = 'tcp')
  
  sch.test(num_session = 5)
  #
  raw_input('Enter')
  
if __name__ == "__main__":
  main()
  

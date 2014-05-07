import json,pprint,os,inspect,sys,logging,time
from xmlparser import XMLParser
from graphman import GraphMan
from scheduling_optimization_new import SchingOptimizer
#from perf_plot import PerfPlotter
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
  
class Scheduler(object):
  event_chief = EventChief()
  def __init__(self, xml_net_num, sching_logto, data_over_tp):
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
    net_xml_file_url = "net_xmls/net_1p_singletr.xml"
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
    self.users_beingserved_dict = {} #user_ip:{'gw_dpid':<>,'gw_conn_port':<> ...}
    #
    self.N = 0 #num_activesessions
    self.alloc_dict = None
    self.sessionsbeingserved_dict = {}
    self.sessionspreserved_dict = {}
    self.sid_res_dict = {}
    self.actual_res_dict = self.gm.give_actual_resource_dict()
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
    self.exp()
    
    self.couplinginfo_dict = {}
    self.startedtime = time.time()
  
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
  
  #########################  _handle_*** methods  #######################
  def _handle_recvfromacter(self, msg):
    #msg = [type_, data_]l
    [type_, data_] = msg
    if type_ == 'sp_sching_reply' or type_ == 'resp_sching_reply':
      reply = data_['reply']
      #
      s_id, p_id = int(data_['s_id']), int(data_['p_id'])
      sch_req_id = self.sid_schregid_dict[s_id]
      s_info = self.sessionsbeingserved_dict[sch_req_id]
      [p_ip, c_ip] = s_info['p_c_ip_list']
      user_info = self.users_beingserved_dict[p_ip]
      userinfo_dict = {'ip': p_ip,
                       'mac': user_info['mac'],
                       'gw_dpid': user_info['gw_dpid'],
                       'gw_conn_port': user_info['gw_conn_port'] }
      if reply == 'done':
        self.sessionsbeingserved_dict[sch_req_id]['sching_job_done'][p_id] = True
        #get s_alloc_info
        s_alloc_info = self.alloc_dict['s-wise'][s_id]
        s_pl = s_alloc_info['parism_level']
        #
        type_touser = None
        if type_ == 'sp_sching_reply':
          type_touser = 'sching_reply'
        elif type_ == 'resp_sching_reply':
          type_touser = 'resching_reply'
        #to producer
        msg = {'type':type_touser,
               'data':{'sch_req_id': sch_req_id,
                       'parism_level':s_pl,
                       'p_bw':s_alloc_info['p_bw'][0:s_pl],
                       'p_tp_dst':s_info['tp_dst_list'][0:s_pl] } }
        self.dtsuser_intf.send_to_user(user_ip = p_ip,
                                       msg = msg )
        #to consumer
        if type_ == 'sp_sching_reply': #no need to resend for resching
          msg = {'type':type_touser,
                 'data':{'sch_req_id': sch_req_id,
                         'parism_level':s_pl,
                         'p_tp_dst':s_info['tp_dst_list'][0:s_pl] } }
          self.dtsuser_intf.send_to_user(user_ip = c_ip,
                                         msg = msg )
      else:
        logging.error('_handle_recvfromacter:: Unexpected reply=%s', reply)
        self.dtsuser_intf.send_to_user(user_ip = p_ip,
                                       msg = {'type':'sching_reply',
                                              'data':'sorry' } )
      #
    #

  def _handle_sendtouser(self, userinfo_dict, msg_str):
    Scheduler.event_chief.raise_event('send_msg_to_user',msg_str,userinfo_dict)
    
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
        self.dtsuser_intf.send_to_user(user_ip = user_ip,
                                          msg = {'type':'join_reply',
                                                 'data':'welcome' } )
      else:
        self.dtsuser_intf.send_to_user(user_ip = user_ip,
                                          msg = {'type':'join_reply',
                                                 'data':'sorry' } )
    elif type_ == 'sching_req':
      sch_req_id = self.welcome_session(p_c_ip_list = [user_ip, data_['c_ip']],
                                        req_dict = data_['req_dict'],
                                        app_pref_dict = data_['app_pref_dict'] )
      if sch_req_id  != -1:
        #TODO: for now ...
        self.do_sching()
      else:
        self.dtsuser_intf.send_to_user(user_ip = user_ip,
                                          msg = {'type':'sching_reply',
                                                 'data':'sorry' } )
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
                                                 'mac': user_mac } })
    print 'welcome user; ip=%s, mac=%s, gw_dpid=%s, gw_conn_port=%s' % (user_ip,user_mac,gw_dpid,gw_conn_port)
    return True
  
  #not used now, for future
  def bye_user(self, user_ip):
    if not self.did_user_joindts(user_ip):
      print 'user_ip=%s is not joined' % user_ip
      return False
    #
    del self.users_beingserved_dict[user_ip]
    print 'bye user: ip=%s' % user_ip
    return True
  
  def welcome_session(self, p_c_ip_list, req_dict, app_pref_dict):
    ''' sch_req_id: should be unique for every sch_session '''
    [p_ip, c_ip] = p_c_ip_list
    if not (self.did_user_joindts(p_ip) and self.did_user_joindts(c_ip)):
      print 'nonjoined user in sching_req'
      return -1
    #
    p_c_gwtag_list = ['s'+str(self.users_beingserved_dict[p_ip]['gw_dpid']),
                      's'+str(self.users_beingserved_dict[c_ip]['gw_dpid']) ]
    #update global var, list and dicts
    self.N += 1
    s_pl = req_dict['parism_level']
    s_tp_dst_list = [self.next_tp_dst() for i in range(s_pl)]
    sch_req_id = self.next_sch_req_id()
    self.sessionsbeingserved_dict.update(
      {sch_req_id:{'tp_dst_list': s_tp_dst_list,
                   'p_c_ip_list': p_c_ip_list,
                   'p_c_gwtag_list': p_c_gwtag_list,
                   'app_pref_dict': app_pref_dict,
                   'req_dict': req_dict,
                   'sching_job_done':[False]*s_pl }
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
    print 'bye_session:: bye sch_req_id=%s, session_info=\n%s' % (sch_req_id, pprint.pformat(self.sessionspreserved_dict[sch_req_id]))
  
  def init_network_from_xml(self):
    node_edge_lst = self.xml_parser.give_node_and_edge_list_from_xml()
    #print 'node_lst:'
    #pprint.pprint(node_edge_lst['node_lst'])
    #print 'edge_lst:'
    #pprint.pprint(node_edge_lst['edge_lst'])
    self.gm.graph_add_nodes(node_edge_lst['node_lst'])
    self.gm.graph_add_edges(node_edge_lst['edge_lst'])
  #########################  sching_rel methods  ###############################
  def update_sid_res_dict(self):
    """
    Network resources will be only the ones on the session_shortest path.
    It resources need to lie on the session_shortest path.
    """
    logging.info('update_sid_res_dict:')
    #TODO: sessions whose resources are already specified no need for putting them in the loop
    for s_id in self.sessionsbeingserved_dict:
      p_c_gwdpid_list = self.sessionsbeingserved_dict[s_id]['p_c_gwtag_list']
      s_all_paths = self.gm.give_all_paths(p_c_gwdpid_list[0], p_c_gwdpid_list[1])
      #print forward all_paths for debugging
      dict_ = {i:p for i,p in enumerate(s_all_paths)}
      logging.info('s_id=%s, all_paths=\n%s', s_id, pprint.pformat(dict_))
      #
      for i,p in dict_.items():
        p_net_edge_list = self.gm.pathlist_to_netedgelist(p)
        p_itres_list = self.gm.give_itreslist_on_path(p)
        if not (s_id in self.sid_res_dict):
          self.sid_res_dict[s_id] = {'s_info':{}, 'ps_info':{}}
        self.sid_res_dict[s_id]['ps_info'].update(
          {i: {'path': p,
               'net_edge_list': p_net_edge_list,
               'itres_list': p_itres_list
              }  }  )
  
  def update_sid_schregid_dict(self):
    self.sid_schregid_dict = {}
    #
    i = 0
    for k in self.sessionsbeingserved_dict:
      self.sid_schregid_dict[i] = k
      i += 1
  
  def give_incintkeyform(self, indict):
    outdict = {}
    i = 0
    for k in indict:
      outdict[i] = indict[k]
      i += 1
    #
    return outdict
  
  def do_sching(self):
    '''
    Currently for active sessions, gets things together to work sching logic and
    then sends corresponding walk/itjob rules to correspoding actuator - which is
    a single actuator right now !
    '''
    sching_id = self.next_sching_id()
    if self.sching_logto == 'file':
      fname = 'ext/sching_decs/sching_'+sching_id+'.log'
      logging.basicConfig(filename=fname,filemode='w',level=logging.DEBUG)
    elif self.sching_logto == 'console':
      logging.basicConfig(level=logging.DEBUG)
    #
    #'''
    for sch_req_id, sinfo in self.sessionsbeingserved_dict.items():
      if 'schedtime_list' in sinfo:
        elapsed_time = 1.0*(time.time() - self.startedtime - sinfo['schedtime_list'][-1])
        elapsed_datasize = sinfo['req_dict']['data_size']*elapsed_time/sinfo['trans_time'] #MB
        sinfo['req_dict']['data_size'] -= elapsed_datasize
        sinfo['req_dict']['slack_metric'] -= elapsed_time
      #
    #
    #'''
    logging.info('do_sching:: sching_id=%s started;', sching_id)
    self.update_sid_res_dict()
    self.update_sid_schregid_dict()
    sching_opter = SchingOptimizer(self.give_incintkeyform(self.sessionsbeingserved_dict),
                                   self.actual_res_dict,
                                   self.give_incintkeyform(self.sid_res_dict) )
    sching_opter.solve()
    #
    self.alloc_dict = sching_opter.get_sching_result()
    logging.info('do_sching:: alloc_dict=\n%s', pprint.pformat(self.alloc_dict))
    #'''
    for s_id, salloc in self.alloc_dict['s-wise'].items():
      sch_req_id = self.sid_schregid_dict[s_id]
      sinfo = self.sessionsbeingserved_dict[sch_req_id]
      if not 'schedtime_list' in sinfo:
        sinfo['schedtime_list'] = []
        sinfo['slackmetric_list'] = []
        sinfo['bw_list'] = []
        sinfo['proc_list'] = []
        sinfo['datasize_list'] = []
      #
      sinfo['schedtime_list'].append(time.time()-self.startedtime)
      sinfo['slackmetric_list'].append(sinfo['req_dict']['slack_metric']*0.001)
      sinfo['bw_list'].append(salloc['bw'])
      sinfo['proc_list'].append(salloc['proc'])
      sinfo['datasize_list'].append(sinfo['req_dict']['data_size'])
      
      sinfo['trans_time'] = salloc['trans_time']*0.001
      sinfo['bw'] = salloc['bw'] #Mbps
    #'''
    #
    """
    logging.info('saving sching_dec to figs...')
    self.perf_plotter.save_sching_result(g_info_dict = self.alloc_dict['general'],
                                         s_info_dict = self.alloc_dict['s-wise'],
                                         res_info_dict = self.alloc_dict['res-wise'])
    """
    #Convert sching decs to rules
    for s_id in range(self.N):
      s_allocinfo_dict = self.alloc_dict['s-wise'][s_id]
      #
      itwalkinfo_dict = s_allocinfo_dict['itwalkinfo_dict']
      p_walk_dict = s_allocinfo_dict['pwalk_dict']
      for p_id in range(s_allocinfo_dict['parism_level']):
        p_walk = p_walk_dict[p_id]
        sp_walk__tprrule = None
        if self.data_over_tp == 'tcp':
          sp_walk__tprrule = \
          self.get_overtcp_spwalkrule__sptprrule(s_id, p_id,
                                                 p_walk = p_walk,
                                                 pitwalkbundle_dict = itwalkinfo_dict[p_id])
        elif self.data_over_tp == 'udp':
          sp_walk__tprrule = \
          self.get_overudp_spwalkrule__sptprrule(s_id, p_id,
                                                 p_walk = p_walk,
                                                 pitwalkbundle_dict = itwalkinfo_dict[p_id])
        #
        logging.info('for s_id=%s, p_id=%s;', s_id, p_id)
        #print 'walkrule:'
        #pprint.pprint(sp_walk__tprrule['walk_rule'])
        #print 'itjob_rule:'
        #pprint.pprint(sp_walk__tprrule['itjob_rule'])
        #
        #Dispatching rule to actuator_actuator
        sch_req_id = self.sid_schregid_dict[s_id]
        s_info = self.sessionsbeingserved_dict[sch_req_id]
        #update s_info
        #s_info['trans_time'] = s_allocinfo_dict['trans_time']*0.001 #sec
        s_info['slack-tt'] = s_allocinfo_dict['slack-tt']
        s_info['slack-transtime'] = abs(s_allocinfo_dict['trans_time']-s_info['req_dict']['slack_metric'])
        #
        if s_info['sching_job_done'][p_id] == False:
          type_toacter = 'sp_sching_req'
        else:
          type_toacter = 'resp_sching_req'
        #
        msg = json.dumps({'type':type_toacter,
                          'data':{'s_id':s_id, 'p_id':p_id,
                                  'walk_rule':sp_walk__tprrule['walk_rule'],
                                  'itjob_rule':sp_walk__tprrule['itjob_rule']} })
        self.cci.send_to_client('scher-acter', msg)
      #
    #  
    logging.info('do_sching:: sching_id=%s done.', sching_id)
  
  def get_overtcp_spwalkrule__sptprrule(self,s_id,p_id,p_walk,pitwalkbundle_dict):
    def get_touser_swportname(dpid, port):
      return 's'+str(dpid)+'-eth'+str(port)
    #
    def chop_pwalk_into_tcppaths():
      chopped_pwalk_list = []
      cur_chop_id = 0
      #
      l_ = list(enumerate(p_walk))
      for i,node_str in l_:
        node = self.gm.get_node(node_str)
        node_type = node['type']
        if i == 0:
          if node_type != 'sw':
            logging.error('right after p only sw type is allowed! what is found=(%s,%s)', node_str, node_type)
            system.exit(2)
          #
          chopped_pwalk_list.append(['p', node_str])
        elif i == len(l_)-1:
          if node_type != 'sw':
            logging.error('right before c only sw type is allowed! what is found=(%s,%s)', node_str, node_type)
            system.exit(2)
          #
          chopped_pwalk_list[cur_chop_id].append(node_str)
          chopped_pwalk_list[cur_chop_id].append('c')
        else: #i is pointing to intermediate pwalk_nodes
          if node_type == 'sw':
            chopped_pwalk_list[cur_chop_id].append(node_str)
          elif node_type == 't':
            chopped_pwalk_list[cur_chop_id].append(node_str)
            cur_chop_id += 1
            chopped_pwalk_list.append([node_str])
        #
      return chopped_pwalk_list
    #
    chopped_pwalk_list = chop_pwalk_into_tcppaths()
    #
    print '---> for s_id=%s, p_id=%s' % (s_id, p_id)
    print 'pitwalkbundle_dict='
    pprint.pprint(pitwalkbundle_dict)
    print 'p_walk=', p_walk
    #print 'chopped_pwalk_list='
    #pprint.pprint(chopped_pwalk_list)
    #
    s_info_dict =  self.sessionsbeingserved_dict[self.sid_schregid_dict[s_id]]
    s_tp_dst = s_info_dict['tp_dst_list'][p_id]
    p_c_ip_list = s_info_dict['p_c_ip_list']
    #
    itjob_rule_dict = {}
    #
    walk_rule = []
    duration = 0
    from_ip = p_c_ip_list[0]
    to_ip = p_c_ip_list[1]
    p_info_dict = self.users_beingserved_dict[from_ip]
    c_info_dict = self.users_beingserved_dict[to_ip]
    from_mac = p_info_dict['mac']
    to_mac = c_info_dict['mac']
    #
    uptoitr_func_dict = {}
    #
    for i,pwalk_chop in list(enumerate(chopped_pwalk_list)):
      chop_wr = [] #chop_walk_rule
      head_i, tail_i = 0, len(pwalk_chop)-1
      head_str, tail_str = pwalk_chop[head_i], pwalk_chop[tail_i]
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
      #extract forward route from head to tail
      for j in range(head_i+1, tail_i-1): #sws in [head_sw-tail_sw)
        sw_str = pwalk_chop[j]
        sw = self.gm.get_node(sw_str)
        forward_edge = self.gm.get_edge(sw_str, pwalk_chop[j+1])
        #
        chop_wr.append({'conn':[sw['dpid'],head_ip],
                        'typ':'forward',
                        'wc':[head_ip,to_ip,6,-1,int(s_tp_dst)],
                        'rule':[forward_edge['pre_dev'], duration] })
      #extract backward route from tail to head
      for j in range(head_i+2, tail_i): #sws in (head_sw-tail_sw]
        sw_str = pwalk_chop[j]
        sw = self.gm.get_node(sw_str)
        backward_edge = self.gm.get_edge(pwalk_chop[j-1], sw_str)
        #
        chop_wr.append({'conn':[sw['dpid'],tail_ip],
                               'typ':'forward',
                               'wc':[tail_ip,head_ip,6,int(s_tp_dst),-1],
                               'rule':[backward_edge['post_dev'], duration] })
      #extract modify_forward route to tail, and fill up itjob_rule
      tailsw_str = pwalk_chop[tail_i-1]
      tailsw = self.gm.get_node(tailsw_str)
      totail_swportname = None
      if tail_str == 'c':
        totail_swportname = get_touser_swportname(dpid = c_info_dict['gw_dpid'],
                                                  port = c_info_dict['gw_conn_port'])
        chop_wr.append({'conn':[tailsw['dpid'],head_ip],
                        'typ':'forward',
                        'wc':[head_ip,to_ip,6,-1,int(s_tp_dst)],
                        'rule':[totail_swportname, duration] })
      else: #tail is another itres        
        tailedge = self.gm.get_edge(tailsw_str, tail_str)
        totail_swportname = tailedge['pre_dev']
        chop_wr.append({'conn':[tailsw['dpid'],head_ip],
                        'typ':'mod_nw_dst__forward',
                        'wc':[head_ip,to_ip,6,-1,int(s_tp_dst)],
                        'rule':[tail_ip, tail_mac, totail_swportname, duration] })
        #fill up it_job_rule for the itres
        assigned_job = pitwalkbundle_dict['itbundle'][tail_str]
        if not (tailsw['dpid'] in itjob_rule_dict):
          itjob_rule_dict[tailsw['dpid']] = [{
            'proto': 6,
            'tpr_ip': tail_ip,
            'tpr_mac': tail_mac,
            'swdev_to_tpr': totail_swportname,
            'assigned_job': assigned_job,
            'completeduptohere_job': uptoitr_func_dict.copy(),
            'session_tp': int(s_tp_dst),
            'consumer_ip': to_ip,
            'datasize': pitwalkbundle_dict['p_info']['datasize'] }]
        else:
          itjob_rule_dict[tailsw['dpid']].append( [{
            'proto': 6,
            'tpr_ip': tail_ip,
            'tpr_mac': tail_mac,
            'swdev_to_tpr': totail_swportname,
            'assigned_job': assigned_job,
            'completeduptohere_job': uptoitr_func_dict.copy(),
            'session_tp': int(s_tp_dst),
            'consumer_ip': to_ip,
            'datasize': pitwalkbundle_dict['p_info']['datasize'] }] )
        #
        #update__uptoitr_func_dict
        for ftag in assigned_job:
          if ftag in uptoitr_func_dict:
            uptoitr_func_dict[ftag] += assigned_job[ftag]
          else:
            uptoitr_func_dict[ftag] = assigned_job[ftag]
        #
      #
      
      #extract modify_backward route to head
      headsw_str = pwalk_chop[head_i+1]
      headsw = self.gm.get_node(headsw_str)
      tohead_swportname = None
      if head_str == 'p':
        tohead_swportname = get_touser_swportname(dpid = p_info_dict['gw_dpid'],
                                                  port = p_info_dict['gw_conn_port'])
      else: #head is another itres
        headedge = self.gm.get_edge(head_str, headsw_str)
        tohead_swportname = headedge['pre_dev']
      #
      chop_wr.append({'conn':[headsw['dpid'],tail_ip],
                      'typ':'mod_nw_src__forward',
                      'wc':[tail_ip,head_ip,6,int(s_tp_dst),-1],
                      'rule':[to_ip, to_mac, tohead_swportname, duration] })
      #print 'chop_wr='
      #pprint.pprint(chop_wr)
      walk_rule += chop_wr
      
    return {'walk_rule':walk_rule, 'itjob_rule':itjob_rule_dict}

  def get_overudp_spwalkrule__sptprrule(self,s_id,p_id,p_walk,pitwalkbundle_dict):
    """
    This method extracts the rule for UDP-based data-coupling.
    Jan 4 2014: Planning to deprecate this and go with TCP-based data-coupling.
    """
    def get_touser_swportname(dpid, port):
      return 's'+str(dpid)+'-eth'+str(port)
    #
    print '---> for s_id=%s, p_id=%s' % (s_id, p_id)
    print 'pitwalkbundle_dict:'
    pprint.pprint(pitwalkbundle_dict)
    print 'p_walk: ', p_walk
    #
    s_info_dict =  self.sessionsbeingserved_dict[self.sid_schregid_dict[s_id]]
    s_tp_dst = s_info_dict['tp_dst_list'][p_id]
    p_c_ip_list = s_info_dict['p_c_ip_list']
    #
    itjob_rule_dict = {}
    #
    walk_rule = []
    cur_from_ip = p_c_ip_list[0]
    cur_to_ip = p_c_ip_list[1]
    duration = 50
    cur_node_str = None
    for i,node_str in list(enumerate(p_walk)):#node = next_hop
      if i == 0:
        cur_node_str = node_str
        #for adding reverse-walk rule for p_gw_sw
        userinfo_dict = self.users_beingserved_dict[cur_from_ip]
        touser_swportname = get_touser_swportname(dpid = userinfo_dict['gw_dpid'],
                                    port = userinfo_dict['gw_conn_port'])
        node = self.gm.get_node(node_str)
        walk_rule.append({'conn':[node['dpid'],cur_to_ip],
                          'typ':'forward',
                          'wc':[cur_to_ip,p_c_ip_list[0],17,-1,int(s_tp_dst)],
                          'rule':[touser_swportname, duration] })
        #
        continue
      cur_node = self.gm.get_node(cur_node_str)
      if cur_node['type'] == 't':
        cur_node_str = node_str
        continue
      #
      node = self.gm.get_node(node_str)
      edge = self.gm.get_edge(cur_node_str, node_str)
      if node['type'] == 't': #sw-t
        walk_rule.append({'conn':[cur_node['dpid'],cur_from_ip],
                          'typ':'mod_nw_dst__forward',
                          'wc':[cur_from_ip,cur_to_ip,17,-1,int(s_tp_dst)],
                          'rule':[node['ip'],node['mac'],edge['pre_dev'],duration]
                         })
        if not (cur_node['dpid'] in itjob_rule_dict):
          itjob_rule_dict[cur_node['dpid']] = [{
            'proto': 17,
            'tpr_ip': node['ip'],
            'tpr_mac': node['mac'],
            'swdev_to_tpr': edge['pre_dev'],
            'assigned_job': pitwalkbundle_dict['itbundle'][node_str],
            'session_tp': int(s_tp_dst),
            'consumer_ip': cur_to_ip,
            'datasize': pitwalkbundle_dict['p_info']['datasize'] }]
        else:
          itjob_rule_dict[cur_node['dpid']].append( [{
            'proto': 17,
            'tpr_ip': node['ip'],
            'tpr_mac': node['mac'],
            'swdev_to_tpr': edge['pre_dev'],
            'assigned_job': pitwalkbundle_dict['itbundle'][node_str],
            'session_tp': int(s_tp_dst),
            'consumer_ip': cur_to_ip,
            'datasize': pitwalkbundle_dict['p_info']['datasize'] }] )
        cur_from_ip = node['ip']
      elif node['type'] == 'sw': #sw-sw
        walk_rule.append({'conn':[cur_node['dpid'],cur_from_ip],
                          'typ':'forward',
                          'wc':[cur_from_ip,cur_to_ip,17,-1,int(s_tp_dst)],
                          'rule':[edge['pre_dev'], duration] })
        cur_from_ip
        #for reverse walk: data from c to p
        walk_rule.append({'conn':[node['dpid'],cur_to_ip],
                          'typ':'forward',
                          'wc':[cur_to_ip,p_c_ip_list[0],17,-1,int(s_tp_dst)],
                          'rule':[edge['post_dev'], duration] })
        '''
        #to deliver sch_response to src
        walk_rule.append({'conn':[node['dpid'],info_dict['scher_vip']],
                          'typ':'forward',
                          'wc':[info_dict['scher_vip'],p_c_ip_list[0],17,-1,info_dict['sching_port']],
                          'rule':[edge['post_dev'], duration] })
        '''
      else:
        raise KeyError('Unknown node_type')
      cur_node_str = node_str
    #default rule to forward packet to consumer
    userinfo_dict = self.users_beingserved_dict[cur_to_ip]
    touser_swportname = get_touser_swportname(dpid = userinfo_dict['gw_dpid'],
                                port = userinfo_dict['gw_conn_port'])
    walk_rule.append({'conn':[userinfo_dict['gw_dpid'],cur_from_ip],
                      'typ':'forward',
                      'wc':[cur_from_ip,cur_to_ip,17,-1,int(s_tp_dst)],
                      'rule':[touser_swportname,duration] })
    return {'walk_rule':walk_rule, 'itjob_rule':itjob_rule_dict}
  
  ##############################################################################
  def exp(self):
    print '*** exp::'
    userinfo_list = [ {'user_ip':'10.0.2.0','user_mac':'00:00:00:01:02:00','gw_dpid':1,'gw_conn_port':3},
                      {'user_ip':'10.0.2.1','user_mac':'00:00:00:01:02:01','gw_dpid':1,'gw_conn_port':4},
                      {'user_ip':'10.0.1.0','user_mac':'00:00:00:01:01:00','gw_dpid':2,'gw_conn_port':3},
                      {'user_ip':'10.0.1.1','user_mac':'00:00:00:01:01:01','gw_dpid':2,'gw_conn_port':4} ]
    #userinfo_list = [ {'user_ip':'10.0.0.2','user_mac':'00:00:00:01:00:02','gw_dpid':1,'gw_conn_port':1},
    #                  {'user_ip':'10.0.0.1','user_mac':'00:00:00:01:00:01','gw_dpid':2,'gw_conn_port':3} ]
    #
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
  
  def test(self):
    userinfo_list = [ {'user_ip':'10.0.0.2','user_mac':'00:00:00:01:00:02','gw_dpid':1,'gw_conn_port':1},
                      {'user_ip':'10.0.0.1','user_mac':'00:00:00:01:00:01','gw_dpid':2,'gw_conn_port':3} ]
    #
    for userinfo in userinfo_list:
      self.welcome_user(user_ip = userinfo['user_ip'],
                        user_mac = userinfo['user_mac'],
                        gw_dpid = userinfo['gw_dpid'],
                        gw_conn_port = userinfo['gw_conn_port'] )
    #
    num_session = 3
    #data_size (MB) slack_metric (ms)
    req_dict_list = [ {'data_size':20, 'slack_metric':60000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':100, 'slack_metric':300000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':100, 'slack_metric':350000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':1, 'par_share':[1]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':1000, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                      {'data_size':1, 'slack_metric':24, 'func_list':['fft','upsampleplot'], 'parism_level':2, 'par_share':[0.5, 0.5]},
                    ]
    app_pref_dict_list = [
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                          {'m_p': 1,'m_u': 1,'x_p': 0,'x_u': 0},
                         ]
    p_c_ip_list_list = [
                        ['10.0.0.2','10.0.0.1'],
                       ]
    for i in range(0, num_session):
      self.welcome_session(p_c_ip_list = p_c_ip_list_list[0],
                           req_dict = req_dict_list[i],
                           app_pref_dict = app_pref_dict_list[i] )
    self.do_sching()
  
is_scheduler_run = False
def main():
  global is_scheduler_run
  is_scheduler_run = True
  sch = Scheduler(xml_net_num = 1,
                  sching_logto = 'console',
                  data_over_tp = 'tcp')
  sch.test()
  #
  raw_input('Enter')
  
if __name__ == "__main__":
  main()
  

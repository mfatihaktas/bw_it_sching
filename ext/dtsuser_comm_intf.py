import sys,json,socket,threading,time,logging,errno,pprint,Queue
from errors import *

dtsuser_protocol_dict = {'send_type':['join_reply', 'resching_reply', 'sching_reply', 'ack'],
                         'recv_type':['join_req', 'sching_req', 'session_done', 'ack', 'coupling_done'] }
RX_SIZE = 1024

class DTSUserCommIntf(object):
  def __init__(self):
    logging.basicConfig(level=logging.DEBUG)
    self.logger = logging.getLogger('dtsusercomm')
    #
    self.timeout = 5
    self.usersinfo_dict = {}
    #
    self.logger.info('dtsuser_comm_inft:: inited.')
  
  def reg_user(self, user_ip, userinfo_dict, _recv_callback, _send_callback):
    if not user_ip in self.usersinfo_dict:
      self.usersinfo_dict[user_ip] = {'userinfo_dict': userinfo_dict,
                                      '_recv_callback': _recv_callback,
                                      '_send_callback': _send_callback,
                                      'seq_num': 0,
                                      'state': 0,
                                      'msg_tobeacked': None,
                                      'timeout_timer': None,
                                      'helper_queue': Queue.Queue(maxsize=1) }
      self.logger.info('reg_user:: new user reged userinfo_dict=\n%s', pprint.pformat(userinfo_dict) )
    #
  
  def relsend_to_user(self, user_ip, msg):
    ''' reliable send over udp with stop-and-wait arq '''
    self.send_to_user(user_ip, msg)
    #
    userinfo_dict = self.usersinfo_dict[user_ip]
    news = userinfo_dict['helper_queue'].get(block=True, timeout=None)
    if news == 'success':
      self.logger.info('relsend_to_user:: completed sending seq_num=%s to user_ip=%s', userinfo_dict['seq_num'],user_ip)
      return 1 #success
    else:
      self.logger.error('relsend_to_user:: could not send seq_num=%s to user_ip=%s', userinfo_dict['seq_num'],user_ip)
      userinfo_dict['timeout_timer'].cancel()
      return 0 #failed
  
  def send_to_user(self, user_ip, msg):
    msg_ = self.check_msg('send', msg)
    if msg_ == None:
      self.logger.error('send_to_user:: msg is not proto-good')
      return
    #
    [type_, data_] = msg_
    #
    userinfo_dict = self.usersinfo_dict[user_ip]
    msg_tobeacked = {'type': type_,
                     'data': data_,
                     'seq_num': userinfo_dict['seq_num'] }
    #
    userinfo_dict['_send_callback'](userinfo_dict = userinfo_dict['userinfo_dict'],
                                    msg_str =  json.dumps(msg_tobeacked) )
    userinfo_dict['msg_tobeacked'] = msg_tobeacked
    userinfo_dict['state'] = 1
    self.logger.debug('send_to_use r:: sent to user_ip=%s, type=%s, seq_num=%s', user_ip, type_, userinfo_dict['seq_num'])
    #
    timeout_timer = threading.Timer(interval = self.timeout,
                                    function = self.handle_timeout,
                                    kwargs = {'user_ip':user_ip} )
    userinfo_dict['timeout_timer'] = timeout_timer
    timeout_timer.start()
  
  def handle_timeout(self, user_ip):
    userinfo_dict = self.usersinfo_dict[user_ip]
    seq_num = userinfo_dict['seq_num']
    msg_tobeacked = userinfo_dict['msg_tobeacked']
    #
    self.logger.debug('handle_timeout:: timeout for user_ip=%s; resend seq_num=%s', user_ip, seq_num)
    self.send_to_user(user_ip = user_ip,
                      msg = msg_tobeacked)
  
  #######  
  def pass_to_dts(self, user_ip, msg): #msg is json in str
    print '***pass_to_dts::'
    print 'msg=%s' % msg
    print '***'
    msg_ = self.check_msg('recv', json.loads(msg))
    if msg_ == None:
      self.logger.error('pass_to_dts:: msg is not proto-good')
      return
    #
    self.logger.debug('pass_to_dts:: dts recved from user_ip=%s', user_ip)
    #
    self.handle_rxfromuser(user_ip, msg_)
    
  def handle_rxfromuser(self, user_ip, msg_):
    userinfo_dict = self.usersinfo_dict[user_ip]
    seq_num = userinfo_dict['seq_num']
    timeout_timer = userinfo_dict['timeout_timer']
    state = userinfo_dict['state']
    helper_queue = userinfo_dict['helper_queue']
    #
    [type_, data_, seq_num_] = msg_
    #print '***handle_rxfromuser::'
    #print 'type_=%s' % type_
    #print 'data_=%s' % data_
    #print 'seq_num_=%s' % seq_num_
    #print '***'
    if type_ == 'ack':
      if seq_num_ == seq_num:
        timeout_timer.cancel()
        userinfo_dict['seq_num'] += 1
        userinfo_dict['state'] = 0
        self.logger.debug('handle_rxfromuser:: for user_ip=%s, ack rxed for seq_num=%s', user_ip, seq_num)
        helper_queue.put('success')
      else:
        self.logger.error('handle_rxfromdts:: for user_ip=%s, ack with seq_num_=%s rxed when expected seq_num=%s', user_ip, seq_num_, seq_num)
        helper_queue.put('failed')
    else:
      if state == 0:
        self.ack_user(user_ip, seq_num_)
        userinfo_dict['_recv_callback'](userinfo_dict = userinfo_dict['userinfo_dict'],
                                        msg_ = [type_, data_])
      else:
        self.logger.error('handle_rxfromuser:: for user_ip=%s, nonack is rxed when state=%s', user_ip, state)
        helper_queue.put('failed')
    #
    #self.logger.debug('handle_rxfromuser:: method returns.')
  
  def ack_user(self, user_ip, seq_num):
    msg_ack = json.dumps({'type': 'ack',
                          'seq_num': seq_num,
                          'data': ''} )
    #
    userinfo_dict = self.usersinfo_dict[user_ip]
    userinfo_dict['_send_callback'](userinfo_dict = userinfo_dict['userinfo_dict'],
                                    msg_str =  msg_ack )
    self.logger.debug('ack_user:: for user_ip=%s, acked seq_num=%s', user_ip,seq_num)
    
  def check_msg(self, acttype, msg):
    if not (acttype == 'send' or acttype == 'recv'):
      self.logger.error('Unexpected acttype')
      return None
    #
    try:
      type_ = msg['type']
      data_ = msg['data']
      if acttype == 'recv':
        seq_num_ = msg['seq_num']
    except ValueError:
      raise CorruptMsgError('Nonjson msg', msg)
      return None
    except KeyError:
      raise CorruptMsgError('No type/data/seq_num field in the msg', dict_ )
      return None
    #
    bool_ = type_ in dtsuser_protocol_dict[acttype+'_type']
    if not bool_: #type_ is not defined under sctag protocol
      raise CorruptMsgError('Wrong msg[type]', type_ )
    #whole check is done
    if acttype == 'recv':
      return [type_, data_, seq_num_]
    return [type_, data_]
  
  def close(self):
    for user_ip in self.usersinfo_dict:
      itrinfo_dict = self.usersinfo_dict[user_ip]
      timeout_timer = itrinfo_dict['timeout_timer']
      helper_queue = itrinfo_dict['helper_queue']
      if timeout_timer != None:
        timeout_timer.cancel()
      helper_queue.put('failed')
    #
    self.logger.info('dtsuser_comm_inft:: closed.')

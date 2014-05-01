import sys,json,socket,threading,time,logging,errno,pprint,Queue
from errors import *

sctag_list = ['p-dts', 'c-dts', 't-dts']
userdts_protocol_dict = {'p-dts':{'send_type':['join_req', 'sching_req', 'session_done', 'ack'],
                                  'recv_type':['join_reply', 'sching_reply', 'resching_reply', 'ack'] },
                         'c-dts':{'send_type':['join_req', 'ack', 'coupling_done'],
                                  'recv_type':['join_reply', 'ack', 'sching_reply'] },
                         't-dts':{'send_type':['ack'],
                                  'recv_type':['itjob_rule', 'ack', 'reitjob_rule'] },
                        }
RX_SIZE = 1024

class UserDTSCommIntf(object):
  def __init__(self, sctag, user_addr, dts_addr, _recv_callback):
    self.logger = logging.getLogger('userdts_comm_intf')
    #
    if not sctag in sctag_list:
      self.logger.error('UserDTSCommIntf:: unexpected sctag=%s', sctag)
      return
    #
    self.sctag = sctag
    self.user_addr = user_addr
    self.dts_addr = dts_addr
    self._recv_callback = _recv_callback
    #
    self.logger.info('UserDTSCommIntf inited, user_addr=%s, dts_addr=%s', user_addr,dts_addr)
    #for stop-and-wait protocol
    self.helper_queue = Queue.Queue(maxsize=1)
    self.seq_num = 0
    self.msg_tobeacked = None
    #state; 0:ready to send, 1:waiting for ack
    self.state = 0
    self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.rx_sock.bind(self.user_addr)
    #
    self.timeout = 5 #sec
    self.timeout_timer = None #threading.Thread(target=self.handle_timeout )
    #
    self.rx_thread = threading.Thread(target = self.init_rx)
    self.rx_thread.start()
  
  def relsend_to_dts(self, msg):
    ''' reliable send over udp with stop-and-wait arq '''
    self.send_to_dts(msg)
    news = self.helper_queue.get(block=True, timeout=None)
    if news == 'success':
      #self.logger.info('relsend_to_dts:: completed sending seq_num=%s', self.seq_num-1 )
      return 1 #success
    else:
      #self.logger.error('relsend_to_dts:: could not send seq_num=%s !', self.seq_num-1 )
      return 0 #failed
  
  def handle_timeout(self):
    self.logger.debug('handle_timeout:: timeout; resend seq_num=%s', self.seq_num)
    self.send_to_dts(self.msg_tobeacked)
  
  def send_to_dts(self, msg):
    msg_ = self.check_msg('send', msg)
    if msg_ == None:
      self.logger.error('send_to_dts:: msg is not proto-good')
      return
    #
    [type_, data_] = msg_
    self.msg_tobeacked = {'type': type_,
                          'data': data_,
                          'seq_num': self.seq_num}
    #
    self.tx_sock.sendto(json.dumps(self.msg_tobeacked), self.dts_addr )
    self.state = 1
    self.logger.debug('send_to_dts:: type=%s, sent seq_num=%s', type_, self.seq_num )
    #
    self.timeout_timer = threading.Timer(self.timeout, self.handle_timeout)
    self.timeout_timer.start()
  
  def init_rx(self):
    while True:
      msg = self.rx_sock.recv(RX_SIZE)
      if msg == '':
        self.logger.info('init_rx:: rxed stop_rxing')
        self.rx_sock.close()
        break
      #
      #print '***init_rx::'
      #pprint.pprint(json.loads(msg))
      #print '***'
      msg_ = self.check_msg('recv', json.loads(msg))
      if msg_ == None:
        self.logger.error('init_rx:: msg is not proto-good')
        return
      #
      #print '***init_rx::'
      #print 'msg_=%s' % pprint.pformat(msg_)
      #print '***'
      #next should be threaded not to block rx
      t = threading.Thread(target = self.handle_rxfromdts,
                           kwargs = {'msg_': msg_} )
      t.start()
  
  def handle_rxfromdts(self, msg_):
    [type_, data_, seq_num_] = msg_
    #
    if type_ == 'ack':
      if seq_num_ == self.seq_num:
        self.timeout_timer.cancel()
        self.seq_num += 1
        self.state = 0
        self.logger.debug('handle_rxfromdts:: seq_num=%s acked', seq_num_)
        self.helper_queue.put('success')
      else:
        self.logger.error('handle_rxfromdts:: ack with seq_num_=%s rxed when expected seq_num=%s', seq_num_, self.seq_num)
        self.helper_queue.put('failed')
    else:
      if self.state == 0:
        self.ack_dts(seq_num_)
        self._recv_callback([type_, data_])
      else:
        self.logger.error('handle_rxfromdts:: nonack is rxed when state=%s', self.state)
        self.helper_queue.put('failed')
  
  def ack_dts(self, seq_num):
    msg_ack = json.dumps({'type': 'ack',
                          'seq_num': seq_num,
                          'data':''} )
    self.tx_sock.sendto(msg_ack, self.dts_addr)
  
  def check_msg(self, acttype, msg):
    '''
    returns [type_,data_,seq_num_] if msg is in correct format (based on pre-defined sctag protocol),
    otherwise raise exception and returns None
    #
    Control Comm protocol:
    msg = {'type':<>, 'data':<>, 'seq_num':<>}
    Note: seq_num considered when acttype=recv
    '''
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
    try:
      bool_ = type_ in userdts_protocol_dict[self.sctag][acttype+'_type']
    except KeyError:
       UnrecogedCommPairError('Undefed sctag protocol',self.sctag)
    if not bool_: #type_ is not defined under sctag protocol
       raise CorruptMsgError('Wrong msg[type]', type_ )
    #whole check is done
    if acttype == 'recv':
      return [type_, data_, seq_num_]
    return [type_, data_]
  
  def close(self):
    self.tx_sock.sendto('', self.user_addr)
    #
    self.tx_sock.close()
    if self.timeout_timer != None:
      self.timeout_timer.cancel()
    self.helper_queue.put('failed')
    #
    self.logger.info('close:: closed.')
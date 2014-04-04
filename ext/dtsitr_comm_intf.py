import sys,json,socket,threading,time,logging,errno,pprint,Queue
from errors import *

dtsitr_protocol_dict = {'send_type':['itjob_rule', 'ack'],
                        'recv_type':['ack'] }
RX_SIZE = 1024

class DTSItrCommIntf(object):
  def __init__(self):
    logging.basicConfig(level=logging.DEBUG)
    #
    self.timeout = 5
    self.itrsinfo_dict = {}
    #
    logging.info('dtsitr_comm_inft:: inited.')
  
  def reg_itr(self, itr_ip, itrinfo_dict, _recv_callback, _send_callback):
    if not itr_ip in self.itrsinfo_dict:
      self.itrsinfo_dict[itr_ip] = {'itrinfo_dict': itrinfo_dict,
                                    '_recv_callback': _recv_callback,
                                    '_send_callback': _send_callback,
                                    'seq_num': 0,
                                    'state': 0,
                                    'msg_tobeacked': None,
                                    'timeout_timer': None,
                                    'helper_queue': Queue.Queue(maxsize=1) }
      logging.info('reg_itr:: new itr reged itrinfo_dict=\n%s', pprint.pformat(itrinfo_dict) )
    #
  
  def relsend_to_itr(self, itr_ip, msg):
    ''' reliable send over udp with stop-and-wait arq '''
    self.send_to_itr(itr_ip, msg)
    #
    itrinfo_dict = self.itrsinfo_dict[itr_ip]
    news = itrinfo_dict['helper_queue'].get(block=True, timeout=None)
    if news == 'success':
      logging.info('relsend_to_itr:: completed sending seq_num=%s to itr_ip=%s', itrinfo_dict['seq_num'],itr_ip)
      return 1 #success
    else:
      logging.error('relsend_to_itr:: could not send seq_num=%s to itr_ip=%s', itrinfo_dict['seq_num'],itr_ip)
      return 0 #failed
  
  def send_to_itr(self, itr_ip, msg):
    msg_ = self.check_msg('send', msg)
    if msg_ == None:
      logging.error('send_to_itr:: msg is not proto-good')
      return
    #
    [type_, data_] = msg_
    #
    itrinfo_dict = self.itrsinfo_dict[itr_ip]
    msg_tobeacked = {'type': type_,
                     'data': data_,
                     'seq_num': itrinfo_dict['seq_num'] }
    #
    itrinfo_dict['_send_callback'](itrinfo_dict = itrinfo_dict['itrinfo_dict'],
                                    msg_str =  json.dumps(msg_tobeacked) )
    itrinfo_dict['msg_tobeacked'] = msg_tobeacked
    itrinfo_dict['state'] = 1
    logging.debug('send_to_itr:: sent to itr_ip=%s', itr_ip)
    #
    timeout_timer = threading.Timer(interval = self.timeout,
                                    function = self.handle_timeout,
                                    kwargs = {'itr_ip':itr_ip} )
    itrinfo_dict['timeout_timer'] = timeout_timer
    timeout_timer.start()
  
  def handle_timeout(self, itr_ip):
    itrinfo_dict = self.itrsinfo_dict[itr_ip]
    seq_num = itrinfo_dict['seq_num']
    msg_tobeacked = itrinfo_dict['msg_tobeacked']
    #
    logging.debug('handle_timeout:: timeout for itr_ip=%s; resend seq_num=%s', itr_ip, seq_num)
    self.send_to_itr(itr_ip, msg_tobeacked)
  
  #######
  def pass_to_dts(self, itr_ip, msg): #msg is json in str
    msg_ = self.check_msg('recv', json.loads(msg))
    if msg_ == None:
      logging.error('pass_to_dts:: msg is not proto-good')
      return
    #
    logging.debug('pass_to_dts:: dts recved from itr_ip=%s', itr_ip)
    #
    self.handle_rxfromitr(itr_ip, msg_)
    
  def handle_rxfromitr(self, itr_ip, msg_):
    itrinfo_dict = self.itrsinfo_dict[itr_ip]
    seq_num = itrinfo_dict['seq_num']
    timeout_timer = itrinfo_dict['timeout_timer']
    state = itrinfo_dict['state']
    helper_queue = itrinfo_dict['helper_queue']
    #
    [type_, data_, seq_num_] = msg_
    #print '***handle_rxfromitr::'
    #print 'type_=%s' % type_
    #print 'data_=%s' % data_
    #print 'seq_num_=%s' % seq_num_
    #print '***'
    if type_ == 'ack':
      if seq_num_ == seq_num:
        timeout_timer.cancel()
        itrinfo_dict['seq_num'] += 1
        itrinfo_dict['state'] = 0
        logging.debug('handle_rxfromitr:: for itr_ip=%s, ack rxed for seq_num=%s', itr_ip, seq_num)
        helper_queue.put('success')
      else:
        logging.error('handle_rxfromdts:: for itr_ip=%s, ack with seq_num_=%s rxed when expected seq_num=%s', itr_ip, seq_num_, self.seq_num)
        helper_queue.put('failed')
    else:
      if state == 0:
        self.ack_itr(itr_ip, seq_num_)
        itrinfo_dict['_recv_callback'](itrinfo_dict = itrinfo_dict['itrinfo_dict'],
                                       msg_ = [type_, data_])
      else:
        logging.error('handle_rxfromitr:: for itr_ip=%s, nonack is rxed when state=%s', itr_ip, state)
        helper_queue.put('failed')
  
  def ack_itr(self, itr_ip, seq_num):
    msg_ack = json.dumps({'type': 'ack',
                          'seq_num': seq_num,
                          'data': ''} )
    #
    itrinfo_dict = self.itrsinfo_dict[itr_ip]
    itrinfo_dict['_send_callback'](itrinfo_dict = itrinfo_dict['itrinfo_dict'],
                                   msg_str =  msg_ack )
    logging.debug('ack_itr:: for itr_ip=%s, acked seq_num=%s', itr_ip,seq_num)
    
  def check_msg(self, acttype, msg):
    if not (acttype == 'send' or acttype == 'recv'):
      logging.error('Unexpected acttype')
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
    bool_ = type_ in dtsitr_protocol_dict[acttype+'_type']
    if not bool_: #type_ is not defined under sctag protocol
      raise CorruptMsgError('Wrong msg[type]', type_ )
      logging.error('check_msg:: bad type=%s', type_)
      return None
    #whole check is done
    if acttype == 'recv':
      return [type_, data_, seq_num_]
    return [type_, data_]
  
  def close(self):
    for itr_ip in self.itrsinfo_dict:
      itrinfo_dict = self.itrsinfo_dict[itr_ip]
      timeout_timer = itrinfo_dict['timeout_timer']
      helper_queue = itrinfo_dict['helper_queue']
      if timeout_timer != None:
        timeout_timer.cancel()
      helper_queue.put('failed')
    #
    logging.info('dtsitr_comm_inft:: closed.')

import sys,json,socket,SocketServer,threading,logging,errno
from errors import *

############################  UDP Server-Handler  ##############################
class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
  def __init__(self, sctag, _call_back, server_address, client_address, RequestHandlerClass):
    SocketServer.UDPServer.__init__(self, server_address, RequestHandlerClass)
    self.client_address = client_address
    self._call_back = _call_back
    self.sctag = sctag
  
class ThreadedUDPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    s = self.server
    if self.client_address[0] != s.client_address[0]:
      logging.info('Unexpected client_ip=%s', self.client_address[0])
      raise UnexpectedClientError('Unexpected client', self.client_address[0])
    #
    msg = self.request[0].strip()
    cur_thread = threading.current_thread()
    logging.info('cur_thread=%s; server_sctag=%s recved msg_size=%sBs', cur_thread.name, s.sctag, sys.getsizeof(msg))
    #
    msg_ = check_smsg('recv', s.sctag, msg)
    if msg_ == None:
      logging.error('msg is not proto-good')
      return
    s._call_back(msg_) #msg_=[type_,data_]
  
############################  TCP Server-Handler  ##############################
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, sctag, _call_back, server_address, client_address, RequestHandlerClass):
    SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
    self.client_address = client_address
    self._call_back = _call_back
    self.sctag = sctag
  
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    s = self.server
    if self.client_address[0] != s.client_address[0]:
      logging.info('Unexpected client_ip=%s', self.client_address[0])
      raise UnknownClientError('Unexpected client', self.client_address[0])
    #
    msg = self.request.recv(4096)
    cur_thread = threading.current_thread()
    logging.info('cur_thread=%s; server_sctag=%s recved msg_size=%sBs', cur_thread.name, s.sctag, sys.getsizeof(msg))
    #
    msg_ = check_smsg('recv', s.sctag, msg)
    if msg_ == None:
      logging.error('msg is not proto-good')
      return
    s._call_back(msg_) #msg_=[type_,data_]
    #
    response = 'ok'
    self.request.sendall(response)
    logging.info('cur_thread=%s; response=%s is sent back to client.', cur_thread.name, response)
################################################################################
sctag_smsgtypes_dict = {'p-dts':{'send_type':['join_req', 'sching_req'],
                                 'recv_type':['join_reply', 'sching_reply'] },
                        'c-dts':{'send_type':['join_req'],
                                 'recv_type':['join_reply'] },
                        't-dts':{'send_type':[],
                                 'recv_type':['itjob_rule'] },
                       }
  
def check_smsg(acttype, sctag, msg):
    '''
    returns [type_,data_] if msg is in correct format (based on pre-defined sctag protocol),
    otherwise raise exception and returns None
    #
    Control Comm protocol:
    msg = {'type':<>, 'data':<> }
    '''
    try:
      dict_ = json.loads(msg)
      type_ = dict_['type']
      data_ = dict_['data']
    except ValueError:
      raise CorruptMsgError('Nonjson msg', msg)
      return None
    except KeyError:
      raise CorruptMsgError('No type/data field in the msg', dict_ )
      return None
    #
    if not (acttype == 'send' or acttype == 'recv'):
      logging.error('Unexpected acttype')
      return None
    try:
      bool_ = type_ in sctag_smsgtypes_dict[sctag][acttype+'_type']
    except KeyError:
      UnrecogedCommPairError('Undefed sctag protocol',sctag)
    if not bool_: #type_ is not defined under sctag protocol
      raise CorruptMsgError('Wrong msg[type]', type_ )
    #whole check is done
    return [type_, data_]
  
class ControlCommIntf(object):
  def __init__(self):
    #commpair_id : {'s_addr':(ip,port), 'c_addr'=(ip,port), 'server'=<>}
    self.commpair_info_dict = {}
  
  def reg_commpair(self, sctag,proto,_recv_callback, s_addr,c_addr):
    #create server,sock
    if proto == 'tcp':
      server = ThreadedTCPServer(sctag, _recv_callback,s_addr,c_addr, ThreadedTCPRequestHandler)
    elif proto == 'udp':
      server = ThreadedUDPServer(sctag, _recv_callback,s_addr,c_addr, ThreadedUDPRequestHandler)
    else:
      logging.error('proto is not tcp/udp.')
      return
    #run server
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    logging.info('%s_server is started at s_addr=%s', proto,s_addr)
    #fill global_dict
    self.commpair_info_dict[sctag] = {'s_addr':s_addr,
                                      'c_addr':c_addr,
                                      'proto':proto,
                                      'server':server }
    logging.info('new commpair added')
    logging.info('proto=%s, s_addr=%s, c_addr=%s', proto,s_addr,c_addr)
  
  def unreg_commpair(self, sctag):
    try:
      cp_info = self.commpair_info_dict[sctag]
    except KeyError:
      raise UnrecogedCommPairError('Unreged commpairsctag is tried to be unreged',sctag)
    #
    cp_info['server'].shutdown()
    #update global_dict
    del self.commpair_info_dict[sctag]
    logging.info('commpair_sctag=%s server is shutdown and commpair_entry is deleted.',sctag)
  
  #TODO: sch_controller can only send over sching_port so will not recv 'ok' after send
  #In other words we are assuming udp_control_msgs will be guarantee-delivered
  def send_to_client(self, sctag, msg): #msg is json in str
    msg_ = check_smsg('send', sctag, msg)
    if msg_ == None:
      logging.error('msg is not proto-good')
      return
    cp_info = self.commpair_info_dict[sctag]
    proto = cp_info['proto']
    #sock = cp_info['sock']
    sock = None
    c_addr = cp_info['c_addr']
    #
    if proto == 'tcp':
      try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(c_addr)
        sock.sendall(msg)
        logging.info('sent to %s_client=%s, datasize=%sBs', proto,c_addr,sys.getsizeof(msg))
      except IOError as e:
        if e.errno == errno.EPIPE:
          #due to insuffient recv_buffer at the other end
          logging.error('broken pipe err, check recv_buffer')
      finally:
        sock.close()
    elif proto == 'udp':
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      sock.sendto(msg, c_addr)
      logging.info('sent to %s_client=%s, datasize=%sBs', proto,c_addr,sys.getsizeof(msg))
    #
  

import sys,json,socket,SocketServer,threading,logging,errno,pprint
from errors import *

#########################  UDP Server-Handler  ###########################
class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
  def __init__(self, sctag, _callback, server_address, client_address, RequestHandlerClass):
    SocketServer.UDPServer.__init__(self, server_address, RequestHandlerClass)
    self.client_address = client_address
    self._callback = _callback
    self.sctag = sctag
  
class ThreadedUDPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    s = self.server
    #
    if s.client_address != 'any':
      if self.client_address[0] != s.client_address[0]:
        raise UnexpectedClientError('Unexpected client', self.client_address[0])
        return
    #
    msg = self.request[0].strip()
    cur_thread = threading.current_thread()
    logging.info('cur_thread=%s; server_sctag=%s recved msg_size=%sBs', cur_thread.name, s.sctag, sys.getsizeof(msg))
    #
    msg_ = check_msg('recv', s.sctag, msg)
    if msg_ == None:
      logging.error('msg is not proto-good')
      return
    s._callback(msg_) #msg_=[type_,data_]
    #
    response = 'ok'
    sock = self.request[1]
    sock.sendto(response, self.client_address)
    logging.info('cur_thread=%s; response=%s is sent back to client.', cur_thread.name, response)
#########################  TCP Server-Handler  ###########################
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, sctag, _callback, server_address, client_address, RequestHandlerClass):
    SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
    self.client_address = client_address
    self._callback = _callback
    self.sctag = sctag
  
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    s = self.server
    #
    if s.client_address != 'any':
      if self.client_address[0] != s.client_address[0]:
        raise UnexpectedClientError('Unexpected client', self.client_address[0])
        return
    #
    msg = self.request.recv(10*1024)
    cur_thread = threading.current_thread()
    logging.info('cur_thread=%s; server_sctag=%s recved msg_size=%sBs', cur_thread.name, s.sctag, sys.getsizeof(msg))
    #
    msg_ = check_msg('recv', s.sctag, msg)
    if msg_ == None:
      logging.error('msg is not proto-good')
      return
    
    s._callback(msg_) #msg_=[type_,data_]
    #
    response = 'ok'
    self.request.sendall(response)
    logging.info('cur_thread=%s; response=%s is sent back to client.', cur_thread.name, response)
################################################################################
sctag_msgtypes_dict = {'scher-acter':{'send_type':['s_sching_req', 'res_sching_req', 'user_dts_tcpchannel_req'],
                                      'recv_type':['s_sching_reply', 'res_sching_reply', 'user_dts_tcpchannel_reply'] },
                       'acter-scher':{'send_type':['s_sching_reply', 'res_sching_reply'],
                                      'recv_type':['s_sching_req', 'res_sching_req'] } }

def check_msg(acttype, sctag, msg):
  # returns [type_, data_] if msg is in correct format (based on pre-defined sctag protocol),
  # otherwise raise exception and returns None
  # Comm protocol:
  # msg = {'type':<>, 'data':<> }
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
    bool_ = type_ in sctag_msgtypes_dict[sctag][acttype+'_type']
  except KeyError:
    UnrecogedCommPairError('Undefed sctag protocol',sctag)
  if not bool_: #type_ is not defined under sctag protocol
    raise CorruptMsgError('Wrong msg[type]', type_ )
  # Whole check is done
  return [type_, data_]
  
class ControlCommIntf(object):
  def __init__(self):
    #commpair_id : {'s_addr':(ip,port), 'c_addr'=(ip,port), 'server'=<>}
    self.commpair_info_dict = {'dts-user': {} }
  
  def reg_commpair(self, sctag, proto, s_addr, _recv_callback, c_addr='any'):
    #create server,sock
    if proto == 'tcp':
      server = ThreadedTCPServer(sctag, _recv_callback, s_addr, c_addr, ThreadedTCPRequestHandler)
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
    self.commpair_info_dict[sctag] = {'s_addr': s_addr,
                                      'c_addr': c_addr,
                                      'proto': proto,
                                      'server': server }
    logging.info('control_comm_intf:: new commpair added\nproto=%s, s_addr=%s, c_addr=%s', proto, s_addr, c_addr)
  
  def unreg_commpair(self, sctag):
    try:
      cp_info = self.commpair_info_dict[sctag]
    except KeyError:
      raise UnrecogedCommPairError('Unreged commpairsctag is tried to be unreged', sctag)
    #
    cp_info['server'].shutdown()
    #update global_dict
    del self.commpair_info_dict[sctag]
    logging.info('commpair_sctag=%s server is shutdown and commpair_entry is deleted.', sctag)
  
  def send_to_client(self, sctag, msg): #msg is json in str
    msg_ = check_msg('send', sctag, msg)
    if msg_ == None:
      logging.error('send_to_client:: msg is not proto-good')
      return
    cp_info = self.commpair_info_dict[sctag]
    proto = cp_info['proto']
    #sock = cp_info['sock']
    sock = None
    c_addr = cp_info['c_addr']
    #
    response = None
    if proto == 'tcp':
      try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(c_addr)
        sock.sendall(msg)
        response = sock.recv(1024)
      except IOError as e:
        if e.errno == errno.EPIPE:
          #due to insuffient recv_buffer at the other end
          logging.error('send_to_client:: broken pipe err, check recv_buffer')
      finally:
        sock.close()
    elif proto == 'udp':
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      sock.sendto(msg, c_addr)
      response = sock.recv(1024)
    #
    logging.info('send_to_client:: sent to %s_client=%s, datasize=%sBs', proto,c_addr,sys.getsizeof(msg))
    if response != 'ok':
      logging.error('send_to_client:: unexpected response=%s', response)
      return
    logging.info('send_to_client:: response=%s', response)
  

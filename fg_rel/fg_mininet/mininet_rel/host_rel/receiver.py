#!/usr/bin/python

import sys,socket,SocketServer,getopt,threading,commands,time,sys,logging,json
#import pprint,json

if sys.version_info[1] < 7:
  PYTHON_STR_HEADER_LEN = 40
else:
  PYTHON_STR_HEADER_LEN = 37
#
def getsizeof(data):
  return sys.getsizeof(data) - PYTHON_STR_HEADER_LEN


CHUNK_H_SIZE = 50 #B
CHUNK_SIZE = 24*8*9*10 #B
CHUNK_STR_SIZE = CHUNK_SIZE + CHUNK_H_SIZE

CHUNK_SIZE_ = 24 #B
CHUNK_STR_SIZE_ = CHUNK_SIZE_ + CHUNK_H_SIZE

RX_CHUNK_SIZE = 1024 #4096

#########################  UDP Server-Handler  ###########################
class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
  def __init__(self, server_address, RequestHandlerClass):
    self.nofBs_rxed = 0
    SocketServer.UDPServer.__init__(self, server_address, RequestHandlerClass)

  def get_nofBs_rxed(self):
    return self.nofBs_rxed

  def inc_nOfBs_rxed(self, howmuch):
    self.nofBs_rxed += howmuch

class ThreadedUDPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request[0].strip()
    cur_thread = threading.current_thread()
    datasize = getsizeof(data)
    #
    s = self.server
    s.inc_nOfBs_rxed(datasize)
    nofBs_rxed = s.get_nofBs_rxed()
    #
    logging.info('cur_thread=%s; threadedserver_udp:%s rxed', cur_thread.name, s.server_address[1])
    logging.info('datasize=%sB\ndata=%s', datasize, '...')
    logging.info('nofBs_rxed=%s, time=%s', nofBs_rxed, time.time() )
#########################  TCP Server-Handler  ###########################
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, server_address, RequestHandlerClass):
    self.nofBs_rxed = 0
    SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
  
  def get_nofBs_rxed(self):
    return self.nofBs_rxed

  def inc_nOfBs_rxed(self, howmuch):
    self.nofBs_rxed += howmuch
  
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request.recv(RX_CHUNK_SIZE)
    cur_thread = threading.current_thread()
    datasize = getsizeof(data)
    #
    s = self.server
    s.inc_nOfBs_rxed(datasize)
    nofBs_rxed = s.get_nofBs_rxed()
    #
    logging.info('cur_thread=%s; threadedserver_tcp:%s rxed', cur_thread.name, s.server_address[1])
    logging.info('datasize=%sB\ndata=%s', datasize, '...')
    logging.info('nofBs_rxed=%s, time=%s', nofBs_rxed, time.time() )
##########################################################################
class Receiver(threading.Thread):
  def __init__(self, in_queue, out_queue, laddr, proto, rx_type, file_url, logto):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.in_queue = in_queue
    self.out_queue = out_queue
    #
    if logto == 'file':
      logging.basicConfig(filename='logs/r_lport=%s.log' % laddr[1], filemode='w', level=logging.DEBUG)
    elif logto == 'console':
      logging.basicConfig(level=logging.DEBUG)
    else:
      print 'Unexpected logto=%s' % logto
      sys.exit(0)
    #
    if not (proto == 'tcp' or proto == 'udp'):
      logging.error('Unexpected proto=%s', proto)
    self.proto = proto
    #
    self.laddr = laddr
    self.file_url = file_url
    self.rx_type = rx_type
    #
    self.recvstart_time = 0
    self.recvend_time = 0
    self.chunk = ''
    self.rxed_datasize = 0
    
    self.recvdsizewithfunc_dict = {}
  
  def run(self):
    if self.rx_type == 'file':
      t = threading.Thread(target=self.rx_file)
      t.start()
    elif self.rx_type == 'dummy':
      if self.proto == 'tcp':
        self.server = ThreadedTCPServer(self.laddr, ThreadedTCPRequestHandler)
        self.server.allow_reuse_address = True
      elif self.proto == 'udp':
        self.server = ThreadedUDPServer(self.laddr, ThreadedUDPRequestHandler)
      #
      server_thread = threading.Thread(target=self.server.serve_forever)
      server_thread.daemon = True
      server_thread.start()
      logging.info('dummyrx_threaded%sserver started on laddr=%s', self.proto, self.laddr)
    elif self.rx_type == 'kstardata':
      t = threading.Thread(target=self.rx_kstardata)
      t.start()
    #
    popped= self.in_queue.get(True, None)
    if popped == 'STOP':
      self.shutdown()
    else:
      logging.error('run:: unexpected is popped from in_queue; popped=%s', popped)
    #
  
  #######################################
  def rx_kstardata(self):
    if not self.proto == 'tcp':
      logging.error('rx_kstardata:: Unexpected proto=%s. Aborting...', self.proto)
      return
    #
    #self.f_obj = open(self.file_url, 'w')
    self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.rx_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self.rx_sock.bind(self.laddr)
    self.rx_sock.listen(1)
    logging.info('rx_kstardata:: listening on laddr=%s', self.laddr)
    sc, addr = self.rx_sock.accept()
    logging.info('rx_kstardata:: got conn from addr=%s', addr[0])
    #
    while 1:
      data = sc.recv(CHUNK_STR_SIZE_)
      datasize = len(data)
      logging.info('rx_kstardata:: lport=%s; rxed datasize=%sB', self.laddr[1], datasize)
      #
      if self.recvstart_time == 0:
        self.recvstart_time = time.time()
      #
      return_ = self.push_to_kstarfile(data)
      if return_ == 0: #failed
        logging.error('rx_kstardata:: push_to_kstarfile for datasize=%s failed. Aborting...', datasize)
        sys.exit(0)
      elif return_ == -1: #EOF
        logging.info('rx_kstardata:: EOF is rxed...')
        break
      elif return_ == -2: #datasize=0
        logging.info('rx_kstardata:: datasize=0 is rxed...')
        break
      elif return_ == 1: #success
        pass
      #
    #
    sc.close()
    #self.f_obj.close()
    
    self.recvend_time = time.time()
    logging.info('rx_kstardata:: finished rxing; rxed_datasize= %s, dur= %s', self.rxed_datasize, self.recvend_time - self.recvstart_time)
    logging.info('rx_kstardata:: rxedsizewithfunc_dict= %s', self.recvdsizewithfunc_dict)
    #let consumer know...
    self.out_queue.put({'recvend_time': self.recvend_time,
                        'recvstart_time': self.recvstart_time,
                        'recvedsize': self.rxed_datasize,
                        'recvedsizewithfunc_dict': self.recvdsizewithfunc_dict })
    
  def push_to_kstarfile(self, data):
    """ returns 1:successful, 0:failed, -1:EOF, -2:datasize=0 """
    self.chunk += data
    chunk_str_size = len(self.chunk)
    #
    if chunk_str_size == 0:
      #this may happen in mininet and cause threads live forever
      return -2
    elif chunk_str_size == 3:
      if self.chunk == 'EOF':
        return -1
    #
    overflow_size = chunk_str_size - CHUNK_STR_SIZE_
    if overflow_size == 0:
      (uptofunc_list, chunk, chunk_size) = self.get_uptofunc_list__chunk(self.chunk)
      self.update_rxedsizewithfunc_dict(uptofunc_list = uptofunc_list,
                                        chunk_size = CHUNK_SIZE )
      #self.f_obj.write(chunk)
      self.rxed_datasize += CHUNK_SIZE
      
      #logging.debug('push_to_kstarfile:: pushed; chunk_size=%s, uptofunc_list=%s', chunk_size, uptofunc_list)
      self.chunk = ''
      return 1
    elif overflow_size < 0:
      return 1
    #
    else: #overflow
      chunk_str_size_ = chunk_str_size-overflow_size
      overflow = self.chunk[chunk_str_size_:]
      chunk_str_to_push = self.chunk[:chunk_str_size_]
      
      (uptofunc_list, chunk, chunk_size) = self.get_uptofunc_list__chunk(chunk_str_to_push)
      self.update_rxedsizewithfunc_dict(uptofunc_list = uptofunc_list,
                                        chunk_size = CHUNK_SIZE )
      #self.f_obj.write(chunk)
      self.rxed_datasize += chunk_size
      
      #logging.debug('push_to_kstarfile:: pushed; chunk_size=%s, overflow_size=%s, uptofunc_list=%s', chunk_size, overflow_size, uptofunc_list)
      #
      if overflow_size == 3 and overflow == 'EOF':
        return -1
      #
      self.chunk = overflow
      return 1
    #
    
  def get_uptofunc_list__chunk(self, chunkstr):
    uptofunc_list = None
    header = chunkstr[:CHUNK_H_SIZE]
    try:
      uptofunc_list = json.loads(header)
    except ValueError:
      pass
    #
    chunk = chunkstr[CHUNK_H_SIZE:]
    chunk_size = len(chunk)
    
    return (uptofunc_list, chunk, chunk_size)
  
  def update_rxedsizewithfunc_dict(self, uptofunc_list, chunk_size):
    for func in uptofunc_list:
      if func in self.recvdsizewithfunc_dict:
        self.recvdsizewithfunc_dict[func] += chunk_size
      else:
        self.recvdsizewithfunc_dict[func] = chunk_size
      #
    #
  
  #######################################
  def rx_file(self):
    self.f_obj = open(self.file_url, 'w')
    logging.info('filerx_%s_sock is listening on laddr=%s', self.proto, self.laddr)
    if self.proto == 'tcp':
      self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.rx_sock.bind(self.laddr)
      self.rx_sock.listen(1)
      sc, addr = self.rx_sock.accept()
      logging.info('%s_file_recver gets conn from addr=%s', self.proto, addr[0])
      #
      rx_ended = False
      l = sc.recv(RX_CHUNK_SIZE)
      #print '***l=\n%s' % l
      l_ = l
      l_len = len(l)
      rxed_tlen = 0
      while (l != 'EOF'):
        l = sc.recv(RX_CHUNK_SIZE)
        #print '***l=\n%s' % l
        if len(l) == 0:
          rxed_tlen += l_len-3
          self.f_obj.write(l_[:l_len-3])
          logging.info('datasize=0 is rxed. rxed_tlen=%s', rxed_tlen)
          rx_ended = True
          break
        else:
          rxed_tlen += l_len
          self.f_obj.write(l_)
        l_ = l
        l_len = len(l)
        logging.info('rxed size=%sB', l_len)
      if not rx_ended:
        logging.info('tcp_EOF is rxed. rxed_tlen=%s', rxed_tlen)
      #
      sc.close()
    elif self.proto == 'udp':
      self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self.rx_sock.bind(self.laddr)
      l = self.rx_sock.recv(RX_CHUNK_SIZE)
      rxed_tlen = len(l)
      while (l != 'EOF'):
        self.f_obj.write(l)        
        l = self.rx_sock.recv(RX_CHUNK_SIZE)
        rxed_tlen += len(l)
        logging.info('rxed size=%sB, rxed_tlen=%sB', len(l), rxed_tlen)
      #
      logging.info('udp_EOF is rxed.')
    #
    self.f_obj.close()
    self.rx_sock.close()
    logging.info('rx_file is complete...')
  
  def shutdown(self):
    if self.rx_type == 'dummy':
      self.server.shutdown()
    elif self.rx_type == 'file' or self.rx_type == 'kstardata':
      self.rx_sock.close()
    #
    logging.debug('shutdown:: %srecver_%s with laddr=%s closed.', self.rx_type, self.proto, self.laddr)
  
def get_laddr(lintf):
  # search and bind to eth0 ip address
  intf_list = commands.getoutput("ifconfig -a | sed 's/[ \t].*//;/^$/d'").split('\n')
  intf_eth0 = None
  for intf in intf_list:
    if lintf in intf:
      intf_eth0 = intf
  intf_eth0_ip = commands.getoutput("ip address show dev " + intf_eth0).split()
  intf_eth0_ip = intf_eth0_ip[intf_eth0_ip.index('inet') + 1].split('/')[0]
  return intf_eth0_ip

###
def main(argv):
  lport = lintf = proto = rx_type = file_url = logto = None
  try:
    opts, args = getopt.getopt(argv,'',['lport=','lintf=','proto=','rx_type=','file_url=', 'logto='])
  except getopt.GetoptError:
    print 'receiver.py --lport=<> --lintf=<> --proto=tcp/udp --rx_type=file/dummy --file_url=<> --logto=<>'
    sys.exit(2)
  #Initializing variables with comman line options
  for opt, arg in opts:
    if opt == '--lport':
       lport = int(arg)
    elif opt == '--lintf':
       lintf = arg
    elif opt == '--proto':
      if arg == 'tcp' or arg == 'udp':
        proto = arg
      else:
        print 'unknown proto=%s' % arg
        sys.exit(2)
    elif opt == '--rx_type':
      if arg == 'file' or arg == 'dummy' or arg == 'kstardata':
        rx_type = arg
      else:
        print 'unknown rx_type=%s' % arg
        sys.exit(2)
    elif opt == '--file_url':
      file_url = arg
    elif opt == '--logto':
      logto = arg
  #
  lip = get_laddr(lintf)
  import Queue
  queue_torecver = Queue.Queue(0)
  dr = Receiver(in_queue = queue_torecver,
                out_queue = Queue.Queue(0),
                laddr = (lip, lport),
                proto = proto,
                rx_type = rx_type,
                file_url = file_url,
                logto = logto )
  dr.start()
  #
  raw_input('Enter\n')
  queue_torecver.put('STOP')
  
if __name__ == "__main__":
  main(sys.argv[1:])

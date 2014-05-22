#!/usr/bin/python
import sys,socket,json,getopt,struct,time,errno,logging,threading
#import numpy as np

CHUNKHSIZE = 50
TXCHUNK_SIZE = 24*8*9*10 #1024 #4096
CHUNKSTRSIZE=TXCHUNK_SIZE+CHUNKHSIZE
#IMGSIZE = 24*8*9

class Sender(threading.Thread):
  def __init__(self, dst_addr, proto, datasize, tx_type, file_url, logto, kstardata_url, txtokenq=None, in_queue=None, out_queue=None):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.txtokenq = txtokenq
    self.in_queue = in_queue
    self.out_queue = out_queue
    #
    if logto == 'file':
      logging.basicConfig(filename='logs/s_tp_port=%s.log' % dst_addr[1], filemode='w', level=logging.DEBUG)
    elif logto == 'console':
      logging.basicConfig(level=logging.DEBUG)
    else:
      print 'Unexpected logto=%s' % logto
      system.exit(0)
    #
    if proto == 'tcp':
      self.sock = None #because; for every chunk being sent we are creating and connecting to dst another socket
    elif proto == 'udp':
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
      logging.error('Unknown proto=%s.', self.proto)
      sys.exit(0)
    self.proto = proto
    #
    if not (tx_type == 'dummy' or tx_type == 'file' or tx_type == 'kstardata' or tx_type == 'kstardata2'):
      logging.error('Unexpected tx_type=%s', tx_type)
      sys.exit(0)
    self.tx_type = tx_type
    #
    self.dst_addr = dst_addr
    self.datasize = datasize
    self.file_url = file_url
    self.kstardata_url = kstardata_url
    #
    self.sendstart_time = 0
    self.sendstop_time = 0
    self.sentsize = 0
  
  def run(self):
    if is_sender_run:
      t = threading.Thread(target=self.test)
      t.start()
    else:
      t = threading.Thread(target=self.init_send)
      t.start()
    #
    popped= self.in_queue.get(True, None)
    if popped == 'STOP':
      self.shutdown()
    else:
      logging.error('run:: unexpected is popped from in_queue; popped=%s', popped)
  
  def shutdown(self):
    if self.sock != None:
      self.sock.close()
    #
    logging.debug('shutdown:: %ssender_%s to dst_addr=%s closed.', self.tx_type, self.proto, self.dst_addr)
  
  
  def init_send(self):
    if self.tx_type == 'dummy':
      #n = int(float(8*float(self.datasize)*1024/8/8))
      n = int(float(8*float(TXCHUNK_SIZE/1024)*1024/8/8))
      data = self.numpy_random(n)
      packer = struct.Struct('%sd' % n)
      data_str = packer.pack(*data)
      #
      self.dummy_send(data_str, self.datasize*1024/TXCHUNK_SIZE)
    elif self.tx_type == 'file':
      self.file_send()
    elif self.tx_type == 'kstardata':
      self.kstardata_send()
    elif self.tx_type == 'kstardata2':
      self.kstardata2_send()
    #
    if self.out_queue != None:
      sendinfo_dict = {'sendstart_time': self.sendstart_time,
                       'sendstop_time': self.sendstop_time,
                       'sentsize': self.sentsize }
      self.out_queue.put(sendinfo_dict)

  def kstardata2_send(self):
    if self.proto != 'tcp':
      logging.info('kstardata2_send:: unexpected proto=%s', self.proto)
      return
    #
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #
    logging.info('kstardata2_send:: trying to connect to %s ...', self.dst_addr )
    self.sock.connect(self.dst_addr)
    logging.info('kstardata2_send:: connected to %s ...', self.dst_addr )
    #
    self.sendstart_time = time.time()
    logging.info('kstardata2_send:: started at time=%s', self.sendstart_time )
    f=open(self.kstardata_url, "r")
    
    ds_tobesent_B = self.datasize*(1024**2)
    #
    len_ = 0
    l = f.read(TXCHUNK_SIZE)
    while (l and len_ < ds_tobesent_B):
      c_len_ = len(l)
      len_ += c_len_
      #add uptofunc_list padding
      uptofunc_list = []
      header = json.dumps(uptofunc_list)
      padding_length = CHUNKHSIZE - len(header)
      header += ' '*padding_length
      l = header+l
      #wait for tx turn
      stoken = self.txtokenq.get(True, None)
      if stoken == CHUNKSTRSIZE:
        pass
      elif stoken == -1:
        self.logger.error('kstardata2_send:: interrupted with txtoken=-1.')
        return
      else:
        self.logger.error('kstardata2_send:: Unexpected stoken=%s', stoken)
        return
      #
      try:
        self.sock.sendall(l)
      except socket.error, e:
        if isinstance(e.args, tuple):
          logging.error('errno is %d', e[0])
          if e[0] == errno.EPIPE:
            logging.error('Detected remote disconnect')
          else:
            pass
        else:
          logging.error('socket error=%s', e)
      #
      l = f.read(TXCHUNK_SIZE)
    #
    self.sock.sendall('EOF')
    logging.info('kstardata_send:: EOF is txed.')
    #
    self.sendstop_time = time.time()
    self.sentsize = len_
    send_dur = self.sendstop_time - self.sendstart_time
    logging.info('kstardata_send:: sent to %s; size=%sB, dur=%ssec', self.dst_addr,len_,send_dur)
    
  def kstardata_send(self):
    if self.proto != 'tcp':
      logging.info('kstardata_send:: unexpected proto=%s', self.proto)
      return
    #
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #IP_MTU_DISCOVER   = 10
    #IP_PMTUDISC_DONT  =  0  # Never send DF frames.
    #self.sock.setsockopt(socket.SOL_IP, IP_MTU_DISCOVER, IP_PMTUDISC_DONT)
    #self.sock.setsockopt(socket.SOL_IP, socket.TCP_MAXSEG, 1)
    #
    logging.info('kstardata_send:: trying to connect to %s ...', self.dst_addr )
    self.sock.connect(self.dst_addr)
    logging.info('kstardata_send:: connected to %s ...', self.dst_addr )
    #
    self.sendstart_time = time.time()
    logging.info('kstardata_send:: started at time=%s', self.sendstart_time )
    f=open(self.kstardata_url, "r")
    
    ds_tobesent_B = self.datasize*(1024**2)
    #
    len_ = 0
    l = f.read(TXCHUNK_SIZE)
    while (l and len_ < ds_tobesent_B):
      c_len_ = len(l)
      len_ += c_len_
      #add uptofunc_list padding
      uptofunc_list = []
      header = json.dumps(uptofunc_list)
      padding_length = CHUNKHSIZE - len(header)
      header += ' '*padding_length
      l = header+l
      #
      try:
        self.sock.sendall(l)
      except socket.error, e:
        if isinstance(e.args, tuple):
          logging.error('errno is %d', e[0])
          if e[0] == errno.EPIPE:
            logging.error('Detected remote disconnect')
          else:
            pass
        else:
          logging.error('socket error=%s', e)
      #
      l = f.read(TXCHUNK_SIZE)
    #
    self.sock.sendall('EOF')
    logging.info('kstardata_send:: EOF is txed.')
    #
    self.sendstop_time = time.time()
    self.sentsize = len_
    send_dur = self.sendstop_time - self.sendstart_time
    logging.info('kstardata_send:: sent to %s; size=%sB, dur=%ssec', self.dst_addr,len_,send_dur)
  
  def file_send(self):
    #TODO (??? ):This method needs to be rewritten according to threaded TCPServer approach
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect(self.dst_addr)
    #
    logging.info('file_send:: started at time=%s', time.time() )
    self.sendstart_time = time.time()
    f=open(self.file_url, "r")
    #
    len_ = 0
    #to emulate tcp byte streaming behavior on lo. e.g.
    #untill whole file is txed
    #  send m*chunk where m is random btw [0.5,1.5]
    import random
    #l = f.read(TXCHUNK_SIZE)
    l = f.read(int(random.uniform(0.5,1.5)*TXCHUNK_SIZE) )
    #
    while (l):
      c_len_ = len(l)
      len_ += c_len_
      if self.proto == 'tcp':
        #
        try:
          self.sock.sendall(l)
          #logging.info('file_send:: over tcp, datasize=%sB', c_len_)
        except socket.error, e:
          if isinstance(e.args, tuple):
            logging.error('errno is %d', e[0])
            if e[0] == errno.EPIPE:
              # remote peer disconnected
              logging.error('Detected remote disconnect')
            else:
              # determine and handle different error
              pass
          else:
            logging.error('socket error=%s', e)
        #
      elif self.proto == 'udp':
        self.sock.sendto(l, self.dst_addr)
      #l = f.read(TXCHUNK_SIZE)
      l = f.read(int(random.uniform(0.5,1.5)*TXCHUNK_SIZE) )
    #
    if self.proto == 'tcp':
      self.sock.sendall('EOF')
    elif self.proto == 'udp':
      self.sock.sendto('EOF', self.dst_addr)
    logging.info('EOF is txed.')
    #
    self.send_dur = time.time() - self.sendstart_time
    logging.info('file_send:: completed sending; size=%sB, dur=%ssec',len_,self.send_dur)
  
  def dummy_send(self, data, noftimes=1):
    self.sendstart_time = time.time()
    nofBs_sent = 0
    logging.info('dummy_send started at time=%s', time.time() )
    logging.info('noftimes=%s', noftimes)
    for i in range(0, int(noftimes)):
      if self.proto == 'tcp':
        try:
          self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.sock.connect(self.dst_addr)
          self.sock.sendall(data)
          datasize = sys.getsizeof(data)-37 #37 is python string format header length
          logging.info('tcp_sent datasize=%sB', datasize)
          nofBs_sent += datasize
        except socket.error, e:
          if isinstance(e.args, tuple):
            logging.error('errno is %d', e[0])
            if e[0] == errno.EPIPE:
              logging.error('Detected remote peer disconnected')
            else:
              # determine and handle different error
              pass
          else:
            logging.error('socket error')
      elif self.proto == 'udp':
        self.sock.sendto(data, self.dst_addr)
        datasize = sys.getsizeof(data)-37 #37 is python string format header length
        nofBs_sent += datasize
        logging.info('udp_sent datasize=%sB', sys.getsizeof(data))
    #
    self.send_dur = time.time() - self.sendstart_time
    logging.info('dummy_over_%s is sent, to addr=%s', self.proto, self.dst_addr)
    logging.info('nofBs_sent=%sB, dur=%ssec', nofBs_sent, self.send_dur)
    logging.info('time=%s', time.time())
  
  def numpy_random(self, n):
    '''
    Return a list/tuple of n random floats in the range [0, 1).
    float_size = 8Bs
    total size of generated random data_list = 8*n+72 Bs
    '''
    return tuple(np.random.random((n)) )
   
  def numpy_randint(self, a, b, n):
    '''Return a list of n random ints in the range [a, b].'''
    return np.random.randint(a, b, n).tolist()
  
  def test(self):
    if self.dst_addr[1] == 7001: #send to t
      data_json = {'type': 'itjob_rule',
                   'data': {'comp': 1.99999998665,
                            'proto': 6,
                            'data_to_ip': u'10.0.0.1',
                            'datasize': 1.0,
                            'itfunc_dict': {u'f1': 1.0, u'f2': 0.99999998665},
                            'proc': 183.150248167,
                            's_tp': 6000} }
      self.dummy_send(json.dumps(data_json))
    elif self.dst_addr[1] == 7998: #send to scher
      data_json = {'type': 'sp_sching_reply',
                   'data': 'OK'}
      self.dummy_send(json.dumps(data_json))
    elif self.dst_addr[1] == 7000: #send to p
      data_json = {'type': 'sching_reply',
                   'data': {'datasize':1,
                            'parism_level':1,
                            'par_share':[1],
                            'p_bw':[1],
                            'p_tp_dst':[6000] }}
      self.dummy_send(json.dumps(data_json))
    else:
      self.init_send()

is_sender_run = False
def main(argv):
  global is_sender_run
  is_sender_run = True
  #
  dst_ip = dst_lport = proto = datasize = tx_type = file_url = logto = kstardata_url = None
  try:
    opts, args = getopt.getopt(argv,'',['dst_ip=','dst_lport=','proto=','datasize=','tx_type=', 'file_url=', 'logto=', 'kstardata_url='])
  except getopt.GetoptError:
    print 'sender.py --dst_ip=<> --dst_lport=<> --proto=tcp/udp --datasize=Mb --tx_type=dummy/file --file_url=<> --logto=<>'
    sys.exit(0)
  #Initializing variables with comman line options
  for opt, arg in opts:
    if opt == '--dst_ip':
      dst_ip = arg
    elif opt == '--dst_lport':
      dst_lport = int(arg)
    elif opt == '--proto':
      if arg == 'tcp' or arg == 'udp':
        proto = arg
      else:
        print 'unknown proto=%s' % arg
        sys.exit(0)
    elif opt == '--datasize':
      datasize = int(arg)
    elif opt == '--tx_type':
      if arg == 'file' or arg == 'dummy' or arg == 'kstardata' or arg == 'kstardata2':
        tx_type = arg
      else:
        print 'unknown rx_type=%s' % arg
        sys.exit(0)
    elif opt == '--file_url':
      file_url = arg
    elif opt == '--logto':
      logto = arg
    elif opt == '--kstardata_url':
      kstardata_url = arg
  #
  import Queue
  queue_tosender = Queue.Queue(0)
  ds = Sender(in_queue = queue_tosender,
              dst_addr = (dst_ip, dst_lport),
              proto = proto,
              datasize = datasize,
              tx_type = tx_type,
              file_url = file_url,
              logto = logto,
              kstardata_url = kstardata_url )
  ds.start()
  #
  raw_input('Enter\n')
  queue_tosender.put('STOP')
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

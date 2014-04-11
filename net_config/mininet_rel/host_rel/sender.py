#!/usr/bin/python
import sys,socket,json,getopt,struct,time,errno,logging
import numpy as np

TXCHUNK_SIZE = 1024 #4096

class Sender(object):
  def __init__(self, dst_addr, proto, datasize, tx_type, file_url, logto):
    if logto == 'file':
      logging.basicConfig(filename='logs/s_tp_port=%s.log' % dst_addr[1], filemode='w', level=logging.DEBUG)
    elif logto == 'console':
      logging.basicConfig(level=logging.DEBUG)
    else:
      print 'Unexpected logto=%s' % logto
      system.exit(2)
    #
    if proto == 'tcp':
      self.sock = None #because; for every chunk being sent we are creating and connecting to dst another socket
    elif proto == 'udp':
      self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
      logging.error('Unknown proto=%s.', self.proto)
      sys.exit(2)
    self.proto = proto
    #
    if not (tx_type == 'dummy' or tx_type == 'file'):
      logging.error('Unexpected tx_type=%s', tx_type)
    self.tx_type = tx_type
    #
    self.dst_addr = dst_addr
    self.datasize = datasize
    self.file_url = file_url
    #
  
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
  
  def file_send(self):
    #TODO (??? ):This method needs to be rewritten according to threaded TCPServer approach
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.connect(self.dst_addr)
    #
    logging.info('file_send started at time=%s', time.time() )
    time_s = time.time()
    f=open(self.file_url, "r")
    #
    len_ = 0
    l = f.read(TXCHUNK_SIZE)
    while (l):
      c_len_ = len(l)
      len_ += c_len_
      if self.proto == 'tcp':
        #
        try:
          self.sock.sendall(l)
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
      l = f.read(TXCHUNK_SIZE)
    #
    if self.proto == 'tcp':
      self.sock.sendall('EOF')
    elif self.proto == 'udp':
      self.sock.sendto('EOF', self.dst_addr)
    logging.info('EOF is txed.')
    #
    tx_dur = time.time() - time_s
    logging.info('file_over_%s:%s is sent; size=%sB, dur=%ssec', self.proto,self.dst_addr,len_,tx_dur)
  
  def dummy_send(self, data, noftimes=1):
    time_s = time.time()
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
    tx_dur = time.time() - time_s
    logging.info('dummy_over_%s is sent, to addr=%s', self.proto, self.dst_addr)
    logging.info('nofBs_sent=%sB, dur=%ssec', nofBs_sent, tx_dur)
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
  ###
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
  
def main(argv):
  dst_ip = dst_lport = proto = datasize = tx_type = file_url = logto = None
  try:
    opts, args = getopt.getopt(argv,'',['dst_ip=','dst_lport=','proto=','datasize=','tx_type=', 'file_url=', 'logto='])
  except getopt.GetoptError:
    print 'sender.py --dst_ip=<> --dst_lport=<> --proto=tcp/udp --datasize=Mb --tx_type=dummy/file --file_url=<> --logto=<>'
    sys.exit(2)
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
        sys.exit(2)
    elif opt == '--datasize':
      datasize = int(arg)
    elif opt == '--tx_type':
      if arg == 'file' or arg == 'dummy':
        tx_type = arg
      else:
        print 'unknown rx_type=%s' % arg
        sys.exit(2)
    elif opt == '--file_url':
      file_url = arg
    elif opt == '--logto':
      logto = arg
  #
  ds = Sender(dst_addr = (dst_ip, dst_lport),
              proto = proto,
              datasize = datasize,
              tx_type = tx_type,
              file_url = file_url,
              logto = logto )
  ds.test()
  #
  raw_input('Enter')
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

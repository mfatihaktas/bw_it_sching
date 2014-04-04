#!/usr/bin/python

import sys,getopt,commands,pprint,mmap,logging,os,Queue,errno,signal
import SocketServer,threading,time,socket,thread
from errors import CommandLineOptionError,NoItruleMatchError
from userdts_comm_intf import UserDTSCommIntf

def get_addr(lintf):
  # search and bind to eth0 ip address
  intf_list = commands.getoutput("ifconfig -a | sed 's/[ \t].*//;/^$/d'").split('\n')
  intf_eth0 = None
  for intf in intf_list:
    if lintf in intf:
      intf_eth0 = intf
  intf_eth0_ip = commands.getoutput("ip address show dev " + intf_eth0).split()
  intf_eth0_ip = intf_eth0_ip[intf_eth0_ip.index('inet') + 1].split('/')[0]
  return intf_eth0_ip

if sys.version_info[1] < 7:
  PYTHON_STR_HEADER_LEN = 40
else:
  PYTHON_STR_HEADER_LEN = 37
#
def getsizeof(data):
  return sys.getsizeof(data) - PYTHON_STR_HEADER_LEN

CHUNKSIZE = 1024*10 #B
NUMCHUNKS_AFILE = 10
PIPE_FILEURL_QUEUE = Queue.Queue(0)
ITSERV_STOP = False
RX_END_TIME = 0
ITSERV_END_TIME = 0
#to be able to close SessionClientHandler and ItServiceHandler threads
HELPER_QUEUE = Queue.Queue(1)

##########################  File TCP Server-Handler  ###########################
class FilePipeServer():
  def __init__(self, server_addr, itwork_dict, to_addr, logger):
    self.server_addr = server_addr
    self.s_tp_dst = int(self.server_addr[1])
    self.itwork_dict = itwork_dict
    self.to_addr = to_addr
    self.logger = logger
    #
    self.sc_handler = None
    self.server_sock = None
    self.itserv_handler = None

  def open_socket(self):
    try:
      self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.server_sock.bind(self.server_addr)
      self.server_sock.listen(0) #only single client can be served
    except socket.error, (value,message):
      if self.server_sock:
        self.server_sock.close()
      self.logger.error('filepipe_server:: Could not open socket=%s', message )
      sys.exit(2)

  def start(self):    
    self.open_socket()
    self.logger.debug('filepipe_server:: serversock_stpdst=%s is opened; waiting for client.', self.s_tp_dst)
    try:
      (sclient_sock,sclient_addr) = self.server_sock.accept()
    except Exception, e:
      self.logger.error('filepipe_server:: Most likely transit.py is terminated with ctrl-c')
      self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      return
      
    self.sc_handler = SessionClientHandler((sclient_sock,sclient_addr),
                                           itwork_dict = self.itwork_dict,
                                           to_addr = self.to_addr,
                                           s_tp_dst = self.s_tp_dst,
                                           logger = self.logger )
    self.sc_handler.start()
    
    self.itserv_handler = ItServiceHandler(itwork_dict = self.itwork_dict,
                                           s_tp_dst = self.s_tp_dst,
                                           to_addr = self.to_addr,
                                           logger = self.logger )
    self.itserv_handler.start()
    #
    self.logger.debug('filepipe_server:: server_addr=%s started.', self.server_addr)
    #threads will handle the rest no need for further listening
    self.server_sock.close()
    self.logger.debug('filepipe_server:: done.')
    
  def shutdown(self):
    global HELPER_QUEUE, PIPE_FILEURL_QUEUE
    #
    self.server_sock.shutdown(socket.SHUT_RDWR)
    self.server_sock.close()
    #close sc_handler
    HELPER_QUEUE.put('stop')
    #close itserv_handler
    PIPE_FILEURL_QUEUE.put('EOF')
    #
    self.logger.info('filepipe_server:: shutdown.')

class SessionClientHandler(threading.Thread):
  def __init__(self,(sclient_sock,sclient_addr), itwork_dict, to_addr, s_tp_dst, logger):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.sclient_sock = sclient_sock
    self.sclient_addr = sclient_addr
    self.s_tp_dst = s_tp_dst
    self.logger = logger
    #for now pipe is list of files
    self.recv_size = 1 #chunks
    self.num_chunks_afile = NUMCHUNKS_AFILE
    self.num_Bs_afile = NUMCHUNKS_AFILE*CHUNKSIZE
    self.pipe_size = 0 #chunks
    self.pipe_size_ = 0 #chunks
    self.pipe_size_B_ = 0 #Bs
    self.pipe_size_B = 0 #Bs

    self.pipe_file_base_str = 'pipe/pipe_tpdst=%s_' % self.s_tp_dst
    self.pipe_file_id = 0
    self.pipe_mm = mmap.mmap(fileno = -1, length = self.num_Bs_afile)
    #session soft expire...
    self.s_soft_expired = False
    self.s_active_last_time = None
    self.s_soft_state_span = 1000 #secs
    soft_expire_timer = threading.Timer(self.s_soft_state_span,
                                        self.handle_s_softexpire )
    soft_expire_timer.daemon = True
    soft_expire_timer.start()
    #
    self.session_over = False
    #
    self.check_file = open('pipe/checkfile.dat', 'w')
    self.started_to_rx_time = None
    
  def run(self):
    self.logger.debug('session_client_handler:: run, sclient_addr=%s', self.sclient_addr)
    threading.Thread(target = self.init_rx).start()
    popped = HELPER_QUEUE.get(True, None)
    if popped == 'stop':
      #brute force to end init_rx thread
      self.sclient_sock.close()
      self.logger.debug('session_client_handler:: stopped.')
    else:
      self.logger.debug('run:: unexpected popped=%s', popped)
    #
    self.logger.debug('session_client_handler:: done. \n\tpipe_size=%s, pipe_size_B=%s\n\tat t=%s; in %ssecs', self.pipe_size, self.pipe_size_B, RX_END_TIME, RX_END_TIME-self.started_to_rx_time)
  
  def init_rx(self):
    global PIPE_FILEURL_QUEUE, RX_END_TIME, ITSERV_STOP
    #
    rxcomplete = False
    while not rxcomplete:
      data = self.sclient_sock.recv(self.recv_size*CHUNKSIZE)
      #
      if self.started_to_rx_time == None:
        self.started_to_rx_time = time.time()
      #
      datasize = getsizeof(data)
      self.logger.info('session_client_handler:: stpdst=%s; rxed datasize=%sB', self.s_tp_dst, datasize)
      #
      return_ = self.push_to_pipe(data, datasize)
      if return_ == 0: #failed
        self.logger.error('session_client_handler:: push_to_pipe for datasize=%s failed. Aborting...', datasize)
        sys.exit(2)
      elif return_ == -1: #EOF
        self.logger.info('session_client_handler:: EOF is rxed...')
        PIPE_FILEURL_QUEUE.put('EOF')
        rxcomplete = True
      elif return_ == -2: #datasize=0
        self.logger.info('session_client_handler:: datasize=0 is rxed...')
        self.flush_pipe_mm()
        ITSERV_STOP = True
        rxcomplete = True
      elif return_ == 1: #success
        self.check_file.write(data)
      #
    #
    RX_END_TIME = time.time()
    self.check_file.close()
    self.sclient_sock.close()
    
  def push_to_pipe(self, data, datasize):
    """ returns 1:successful, 0:failed, -1:EOF, -2:datasize=0 """
    if datasize == 0:
      #this may happen in mininet and cause threads live forever
      return -2
    #
    self.pipe_size_ += self.recv_size
    self.pipe_size_B_ += datasize
    #
    #to handle overflow: pipe_size_B_ > num_Bs_afile
    overflow = None
    overflow_size = self.pipe_size_B_ - self.num_Bs_afile
    data_to_write = None
    if overflow_size <= 0:
      data_to_write = data
    else: #overflow
      data_to_write = data[:datasize-overflow_size]
      overflow = data[datasize-overflow_size:]
    #
    try:
      self.pipe_mm.write(data_to_write)
    except TypeError as e:
      self.logger.error('session_client_handler:: Could not write to pipe_mm. Check mmap.access')
      self.logger.error('e.errno=%s, e.strerror=%s', e.errno, e.strerror)
      return 0
    #
    if overflow_size > 0:
      self.pipe_size_B_ -= overflow_size
      #thread.start_new_thread(self.flush_pipe_mm, (self.pipe_mm, self.pipe_file_id) )
      self.flush_pipe_mm()
      if overflow_size == 3 and overflow == 'EOF':
        return -1
      #
      self.pipe_file_id += 1
      try:
        self.pipe_mm = mmap.mmap(fileno = -1, length = self.num_Bs_afile)
        self.pipe_mm.write(overflow)
        self.pipe_size_B_ += overflow_size
      except Exception, e:
        self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
        return 0
    #
    self.logger.debug('session_client_handler:: datasize=%s pushed to pipe, pipe_size_B_=%s, overflow_size=%s', datasize, self.pipe_size_B_, overflow_size)
    self.s_active_last_time = time.time()
    return 1
    
  def flush_pipe_mm(self):
    global PIPE_FILEURL_QUEUE
    #
    try:
      fileurl = self.pipe_file_base_str+str(self.pipe_file_id)+'.dat'
      pipe_file = open(fileurl, 'w')
      pipe_file.write(self.pipe_mm[:self.num_Bs_afile])
      #
      pipe_file.close()
      self.pipe_mm.close()
      self.pipe_mm = None
      #
      self.pipe_size += self.pipe_size_
      self.pipe_size_B += self.pipe_size_B_
      self.logger.debug('session_client_handler:: pipe_file_id=%s is ready; btw flushed pipe_size_B_=%s', self.pipe_file_id, self.pipe_size_B_)
      self.pipe_size_ = 0
      self.pipe_size_B_ = 0
      #
      PIPE_FILEURL_QUEUE.put(fileurl)
    except Exception, e:
      self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
  
  def handle_s_softexpire(self):
    while True:
      #self.logger.debug('handle_s_softexpire::')
      inactive_time_span = time.time() - self.s_active_last_time
      if inactive_time_span >= self.s_soft_state_span:
        self.s_soft_expired = True
        self.logger.info('session_client_handler:: session_tp_dst=%s soft-expired.',self.s_tp_dst)
        return
      # do every ... secs
      time.sleep(self.s_soft_state_span)

class ItServiceHandler(threading.Thread):
  def __init__(self, itwork_dict, s_tp_dst, to_addr, logger):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.itwork_dict = itwork_dict
    self.s_tp_dst = s_tp_dst
    self.to_addr = to_addr
    self.logger = logger
    #
    self.itfunc_dict = {'f0':self.f0,
                        'f1':self.f1,
                        'f2':self.f2,
                        'f3':self.f3,
                        'f4':self.f4 }
    self.func_comp_dict = {'f0':0.5,
                           'f1':1,
                           'f2':2,
                           'f3':3,
                           'f4':4 }
    #
    self.num_chunks_afile = NUMCHUNKS_AFILE
    #num_chunks_afile % serv_size = 0
    self.serv_size = 1 #chunks
    self.serv_size_B = self.serv_size*CHUNKSIZE
    #
    self.served_size_B = 0
    self.served_size_B_ = 0
    self.served_size = 0 #chunks
    self.served_size_ = 0 #chunks, keeps for current file
    #
    self.cur_fileurl = None
    self.pipe_file = None
    self.pipe_mm = None
    #
    self.max_idle_time = 5 #_after_serv_started, secs
    self.active_last_time = None
    self.serv_started = False
    #
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.forwarding_started = False
    #for test...
    self.test_file = open('pipe/testfile.dat', 'w')
    self.test_file_size = 0 #serv_size
    self.test_file_size_B = 0 #B
    self.served_size_B = 0 #B

  #~~~~~~~~~~~~~~~~~~~~~~~~~  IT functional interface  ~~~~~~~~~~~~~~~~~~~~~~~~#
  def run(self):
    global ITSERV_END_TIME
    #
    self.logger.debug('itserv_handler:: run.')
    serv_over = False
    while not serv_over:
      (data, datasize) = self.pop_from_pipe()
      if data == None:
        if datasize == 0: #failed
          pass
        elif datasize == -1: #EOF
          self.forward_data('EOF', 3)
          self.logger.debug('itserv_handler:: fileurl=EOF')
          serv_over = True
        elif datasize == -2: #STOP
          self.logger.debug('itserv_handler:: stopped with flag:ITSERV_STOP')
          serv_over = True
        elif datasize == -3: #fatal
          self.logger.error('itserv_handler:: sth unexpected happened. Check exceptions. Aborting...')
          sys.exit(2)
      else:
        self.logger.debug('itserv_handler:: datasize=%s popped.', datasize)
        if not self.serv_started:
          self.serv_started = True
        #
        self.active_last_time = time.time()
        #data_ = self.proc(data, float(datasize)/1024)
        data_ = data
        datasize_ = getsizeof(data_)
        self.forward_data(data_, datasize_)
        #
        self.served_size_ += self.serv_size
        self.served_size_B_ += datasize
        #
        self.test_file.write(data)
        self.logger.debug('itserv_handler:: acted on datasize=%sB, served_size=%s, served_size_=%s', datasize, self.served_size, self.served_size_)
    #
    self.test_file.close()
    self.sock.close()
    ITSERV_END_TIME = time.time()
    dur = ITSERV_END_TIME - RX_END_TIME
    self.logger.info('itserv_handler:: done. at t=%s; dur=%ssecs', ITSERV_END_TIME, dur)

  def pop_from_pipe(self):
    """ returns:
    (data, datasize): success
    (None, 0): failed
    (None, -1): EOF
    (None, -2): STOP
    (None, -3): fatal failure
    """
    global PIPE_FILEURL_QUEUE
    if self.pipe_mm == None or self.served_size_ == self.num_chunks_afile: #time to move to next file
      if self.cur_fileurl != None:
        #thread.start_new_thread(self.delete_pipe_file, (self.pipe_mm, self.pipe_file, pipe_file_id_) )
        self.delete_pipe_file(self.cur_fileurl)
      #
      self.served_size += self.served_size_
      self.served_size_B += self.served_size_B_
      self.served_size_ = 0
      self.served_size_B_ = 0
      #
      try:
        self.cur_fileurl = PIPE_FILEURL_QUEUE.get(True, None) #self.max_idle_time)
        self.logger.debug('itserv_handler:: next pipe_fileurl=%s', self.cur_fileurl)
        if self.cur_fileurl == 'EOF':
          return (None, -1)
        #
        self.pipe_file = open(self.cur_fileurl, 'r+')
        self.pipe_mm = mmap.mmap(fileno = self.pipe_file.fileno(),
                                 length = 0,
                                 access=mmap.ACCESS_READ )
        self.logger.debug('itserv_handler:: pipe_mm.size()=%s, served_size=%s', self.pipe_mm.size(), self.served_size)
        self.pipe_file.close()
      except Exception, e:
        self.logger.error('pop_from_pipe:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
        return (None, -3)
    #
    try:
      chunk = self.pipe_mm.read(self.serv_size_B)
    except Exception, e:
      self.logger.error('pop_from_pipe:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      return (None, -3)
    #
    chunk_size = getsizeof(chunk)
    self.logger.warning('itserv_handler:: chunksize=%s', chunk_size)
    if chunk_size <= 0:
      if ITSERV_STOP == True:
        return (None, -2)
      #
      return (None, 0)
    #
    return (chunk, chunk_size)

  def delete_pipe_file(self, cur_fileurl):
    try:
      self.pipe_mm.close()
      self.pipe_mm = None
      self.pipe_file.close()
      self.pipe_file = None
    except Exception, e:
      self.logger.error('delete_pipe_file:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
    #
    try:
      os.remove(cur_fileurl)
    except OSError, e:
      self.logger.error('itserv_handler:: for cur_fileurl=%s', cur_fileurl)
      self.logger.error('Error: %s - %s.' % (e.errno,e.strerror))
      return
    #
    self.logger.debug('itserv_handler:: cur_fileurl=%s is deleted from pipe', cur_fileurl)

  #~~~~~~~~~~~~~~~~~~~~~~~~~  IT data transport  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  def forward_data(self, data, datasize):
    """ TODO: returns:
    1: success
    0: failed
    """
    '''
    if not self.forwarding_started:
      self.logger.info('itserv_handler:: itserv_sock is trying to connect to addr=%s', self.to_addr)
      self.sock.connect(self.to_addr)
      self.logger.info('itserv_handler:: itserv_sock is connected to addr=%s', self.to_addr)
      self.forwarding_started = True
    #
    self.sock.sendall(data)
    self.logger.info('itserv_handler:: datasize=%s forwarded to_addr=%s', datasize, self.to_addr)
    '''
    try:
      if not self.forwarding_started:
        self.logger.info('itserv_handler:: itserv_sock is trying to connect to addr=%s', self.to_addr)
        self.sock.connect(self.to_addr)
        self.logger.info('itserv_handler:: itserv_sock is connected to addr=%s', self.to_addr)
        self.forwarding_started = True
      #
      self.sock.sendall(data)
      self.logger.info('itserv_handler:: datasize=%s forwarded to_addr=%s', datasize, self.to_addr)
    except socket.error, e:
      if isinstance(e.args, tuple):
        self.logger.error('errno is %d', e[0])
        if e[0] == errno.EPIPE:
          # remote peer disconnected
          self.logger.error('forward_data:: Detected remote disconnect')
        else:
          # determine and handle different error
          pass
      else:
        self.logger.error('socket error=%s', e)

  #~~~~~~~~~~~~~~~~~~~~~~~~~  IT data manipulation  ~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  def proc(self, data, datasize):
    try:
      #datasize is in B, datasize_ is in MB
      datasize_ = float(datasize)/1024
      #
      jobtobedone = self.itwork_dict['jobtobedone']
      proc_cap = self.itwork_dict['proc']
      data_ = None
      for ftag in jobtobedone:
        data_ = self.itfunc_dict[ftag](datasize_, data, proc_cap)
        #
        datasize_ = float(getsizeof(data_))/1024
        data = data_
      #
      return data
    except Exception, e:
      self.logger.error('proc:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)

  def proc_time_model(self, datasize, func_comp, proc_cap):
    '''
    proc_time_model used in sching process. To see if the sching results can be reaklized
    by assuming used models for procing are perfectly accurate.
    datasize: in MB
    '''
    proc_t = float(func_comp)*float(8*float(datasize)/64)*float(1/float(proc_cap)) #secs
    #self.logger.info('%s*(%s/64)*(1/%s)=%s', func_comp, datasize, proc_cap, proc_t)
    return proc_t
    
  # transit data manipulation functions
  def f0(self, datasize, data, proc_cap):
    self.logger.info('itserv_handler:: f0 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f0'],
                                   proc_cap = proc_cap)
    self.logger.info('itserv_handler:: f0_sleep=%ssecs', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f1(self, datasize, data, proc_cap):
    self.logger.info('itserv_handler:: f1 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f1'],
                                   proc_cap = proc_cap)
    self.logger.info('itserv_handler:: f1_sleep=%ssecs', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f2(self, datasize, data, proc_cap):
    self.logger.info('itserv_handler:: f2 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f2'],
                                   proc_cap = proc_cap)
    self.logger.info('itserv_handler:: f2_sleep=%ssecs', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f3(self, datasize, data, proc_cap):
    self.logger.info('itserv_handler:: f3 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f3'],
                                   proc_cap = proc_cap)
    self.logger.info('itserv_handler:: f3_sleep=%ssecs', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f4(self, datasize, data, proc_cap):
    self.logger.info('itserv_handler:: f4 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f4'],
                                   proc_cap = proc_cap)
    self.logger.info('itserv_handler:: f4_sleep=%ssecs', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data

##########################  Dummy UDP Server-Handler  ##########################
class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
  def __init__(self, call_back, server_addr, RequestHandlerClass):
    SocketServer.UDPServer.__init__(self, server_addr, logger, RequestHandlerClass)
    self.call_back = call_back
    self.logger = logger
  
class ThreadedUDPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request[0].strip()
    #socket = self.request[1]
    cur_thread = threading.current_thread()
    server = self.server
    s_tp_dst = int(server.server_address[1])
    datasize = getsizeof(data) #in MB
    self.logger.info('cur_udp_thread=%s; s_tp_dst=%s, rxed_data_size=%sB', cur_thread.name, s_tp_dst, datasize)
    #
    server.call_back(s_tp_dst, data, datasize)
##########################  Dummy TCP Server-Handler  ##########################
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, call_back, server_addr, logger, RequestHandlerClass):
    SocketServer.TCPServer.__init__(self, server_addr, RequestHandlerClass)
    self.call_back = call_back
    self.logger = logger
  
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request.recv(CHUNKSIZE)
    #
    cur_thread = threading.current_thread()
    server = self.server
    s_tp_dst = int(server.server_address[1])
    datasize = getsizeof(data) #in MB
    server.logger.info('cur_tcp_thread=%s; s_tp_dst=%s, rxed_data_size=%sB', cur_thread.name, s_tp_dst, datasize)
    #
    server.call_back(s_tp_dst, data, datasize)
#############################  Class Transit  ##################################
class Transit(object):
  def __init__(self, nodename, tl_ip, tl_port, dtsl_ip, dtsl_port, trans_type, logger):
    if not (trans_type == 'file' or trans_type == 'console'):
      self.logger.error('Unexpected trans_type=%s', trans_type)
    self.trans_type = trans_type
    #
    self.nodename = nodename
    self.tl_ip = tl_ip
    self.tl_port = tl_port
    self.dtsl_ip = dtsl_ip
    self.dtsl_port = dtsl_port
    self.logger = logger
    #
    self.sinfo_dict = {}
    #for control comm
    self.itrdts_intf = UserDTSCommIntf(sctag = 't-dts',
                                       user_addr = (self.tl_ip,self.tl_port),
                                       dts_addr = (self.dtsl_ip,self.dtsl_port),
                                       _recv_callback = self._handle_recvfromdts )
    #
    """
    self.session_soft_state_span = 1000
    s_soft_expire_timer = threading.Timer(self.session_soft_state_span,
                                          self._handle_SessionSoftTimerExpire)
    s_soft_expire_timer.daemon = True
    s_soft_expire_timer.start()
    """
    #to handle ctrl-c for doing cleanup
    signal.signal(signal.SIGINT, self.signal_handler)
    #
    self.logger.info('%s is ready...', self.nodename)
  
  def signal_handler(self, signal, frame):
    self.logger.info('signal_handler:: ctrl+c !')
    self.shutdown()
  
  def _handle_SessionSoftTimerExpire(self):
    while True:
      #self.logger.info('_handle_SessionSoftTimerExpire;')
      #print 's_info_dict:'
      #pprint.pprint(s_info_dict )
      for s_tp_dst, s_info in self.sinfo_dict.items():
        inactive_time_span = time.time() - s_info['s_active_last_time']
        if inactive_time_span >= self.session_soft_state_span: #soft state expire
          s_info['s_server_thread'].shutdown()
          del self.sinfo_dict[s_tp_dst]
          self.logger.info('inactive_time_span=%s\ns with tp_dst:%s is soft-expired.',inactive_time_span,s_tp_dst)
      #
      #self.logger.info('------')
      # do every ... secs
      time.sleep(self.session_soft_state_span)
  
  ##########################  handle dts_comm  #################################
  def _handle_recvfromdts(self, msg):
    """
    TODO: Comm btw DTS-t is assumed to be perfect. Not really...
    """
    #msg = [type_, data_]
    [type_, data_] = msg
    if type_ == 'itjob_rule':
      self.welcome_s(data_)
  
  def welcome_s(self, data_):
    #If new_s with same tpdst arrives, old_s is overwritten by new_s
    stpdst = int(data_['s_tp'])
    if stpdst in self.sinfo_dict:
      self.bye_s(stpdst)
    del data_['s_tp']
    #
    to_ip = data_['data_to_ip']
    del data_['data_to_ip']
    #
    to_addr = (to_ip, stpdst) #goes into s_info_dict
    #
    jobtobedone = {}
    for ftag,comp in data_['itfunc_dict'].items():
      jobtobedone[ftag] = 1024*data_['datasize']*comp/func_comp_dict[ftag]
    data_.update( {'jobtobedone': jobtobedone} )
    #
    proto = int(data_['proto']) #6:TCP, 17:UDP - goes into s_info_dict
    del data_['proto']
    #calc est_proct
    est_proct = proc_time_model(datasize = float(data_['datasize']),
                                func_comp = float(data_['comp']),
                                proc_cap = float(data_['proc']))
    #FilePipeServer blocking to accept a tcp conn, so I took log_info up
    dict_forlog = {'itjobrule':data_,
                   'proto': proto,
                   'to_addr': to_addr,
                   'est_proct': est_proct }
    self.logger.info('welcome_s:: welcome stpdst=%s, est_proct=%s, s_info=\n%s', stpdst, est_proct, pprint.pformat(dict_forlog))
    #
    if self.trans_type == 'file':
      s_server_thread = FilePipeServer(server_addr = (self.tl_ip, stpdst),
                                       itwork_dict = data_,
                                       to_addr = to_addr,
                                       logger = self.logger )
      self.sinfo_dict[stpdst] = {'itjobrule':data_,
                                  'to_addr': to_addr,
                                  's_server_thread': s_server_thread,
                                  'est_proct': est_proct }
      s_server_thread.start()
    elif self.trans_type == 'dummy':
      self.sinfo_dict[stpdst] = {'itjobrule':data_,
                                  'proto': proto,
                                  'to_addr': to_addr,
                                  's_server_thread': self.create_sserver_thread(proto = proto, port = stpdst),
                                  's_active_last_time':time.time(),
                                  'est_proct': est_proct }
    #
  
  def bye_s(self, stpdst):
    sinfo_dict = self.sinfo_dict[stpdst]
    if self.trans_type == 'file':
      sinfo_dict['s_server_thread'].shutdown()
    elif self.trans_type == 'dummy':
      sinfo_dict['s_server_thread'].close()
    #ready to erase s_info
    del self.sinfo_dict[stpdst]
    self.logger.info('bye s; tpdst=%s', stpdst)
  
  def shutdown(self):
    for stpdst in self.sinfo_dict:
      sinfo_dict = self.sinfo_dict[stpdst]
      if self.trans_type == 'file':
        sinfo_dict['s_server_thread'].shutdown()
      elif self.trans_type == 'dummy':
        sinfo_dict['s_server_thread'].close()
    #this may close created sub-threads
    self.itrdts_intf.close()
    self.logger.debug('shutdown:: shutdown.')
    sys.exit(0)
  
  #########################  handle s_data_traffic  ############################
  def create_sserver_thread(self, proto, port):
    s_addr = (self.tl_ip, port)
    s_server = None
    if proto == 6:
      s_server = ThreadedTCPServer(self._handle_recvsdata, s_addr, self.logger, ThreadedTCPRequestHandler)
    elif proto == 17:
      s_server = ThreadedUDPServer(self._handle_recvsdata, s_addr, self.logger, ThreadedUDPRequestHandler)
    else:
      self.logger.error('Unexpected proto=%s', proto)
      return
    #
    s_server_thread = threading.Thread(target=s_server_thread.serve_forever)
    s_server_thread.daemon = True
    s_server_thread.start()
    #
    self.logger.info('%s_server_thread is started at s_addr=%s', proto,s_addr )
    return s_server
  
  def _handle_recvsdata(self, s_tp_dst, data, datasize):
    if not s_tp_dst in self.sinfo_dict:
      raise NoItruleMatchError('No itjobrule match', s_tp_dst)
      return
    #
    """
    data_ = self.proc_pipeline(s_tp_dst = s_tp_dst,
                               data = data,
                               datasize = datasize )
    """
    data_ = data
    datasize_ = sys.getsizeof(data_)
    #
    self.forward_data(s_tp_dst, data_, datasize_)
  
  def proc_pipeline(self, s_tp_dst, data, datasize):
    #datasize is in MB
    global itfunc_dict
    itjobrule = self.sinfo_dict[s_tp_dst]['itjobrule']
    jobtobedone = itjobrule['jobtobedone']
    proc_cap = itjobrule['proc']
    #datasize_ = len(data) #in bits
    for ftag,compleft in jobtobedone.items():
      datasize = float(datasize)/1024
      data = itfunc_dict[ftag](datasize, data, proc_cap)
      #for now no need for checking how much left to process for session
      """
      if jobtobedone[ftag] > 0:
        datasize = float(sys.getsizeof(data))/1024
        data = itfunc_dict[ftag](datasize, data, proc_cap)
        #update jobtobedone
        jobtobedone[ftag] -= datasize
      """
    #
    return data
  
  def forward_data(self, s_tp_dst, data, datasize):
    s_info = self.sinfo_dict[s_tp_dst]
    proto = s_info['proto']
    to_addr = s_info['to_addr']
    #
    sock = None
    if proto == 6:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.logger.info('s_tcpsock is trying to connect to addr=%s', to_addr)
      sock.connect(to_addr)
      sock.sendall(data)
      #datasent_size = sock.send(data)
    elif proto == 17:
      sock.sendto(data, to_addr)
    #
    self.logger.info('proced data is forwarded to_addr=%s', to_addr)
    #update session_active_last_time
    s_info['s_active_last_time']=time.time()
  
  def test(self):
    self.logger.debug('test')
    data = {'comp': 1.99999998665,
            'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': 1000,
            'itfunc_dict': {u'f1': 1.0, u'f2': 0.99999998665},
            'proc': 183.150248167,
            's_tp': 6000 }
    self.welcome_s(data)

############################  IT data manipulation  ############################
func_comp_dict = {'f0':0.5,
                  'f1':1,
                  'f2':2,
                  'f3':3,
                  'f4':4 }

def proc_time_model(datasize, func_comp, proc_cap):
  '''
  proc_time_model used in sching process. To see if the sching results can be reaklized
  by assuming used models for procing are perfectly accurate.
  datasize: in MB
  '''
  proc_t = 1000*float(func_comp)*float(8*float(datasize)/64)*float(1/float(proc_cap)) #(ms)
  #self.logger.info('1000*%s*(%s/64)*(1/%s)=%s', func_comp, datasize, proc_cap, proc_t)
  return proc_t
  
# transit data manipulation functions
def f0(datasize, data, proc_cap):
  self.logger.info('f0 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f0'],
                            proc_cap = proc_cap)
  self.logger.info('f0_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f1(datasize, data, proc_cap):
  self.logger.info('f1 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f1'],
                            proc_cap = proc_cap)
  self.logger.info('f1_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f2(datasize, data, proc_cap):
  self.logger.info('f2 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f2'],
                            proc_cap = proc_cap)
  self.logger.info('f2_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f3(datasize, data, proc_cap):
  self.logger.info('f3 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f3'],
                            proc_cap = proc_cap)
  self.logger.info('f3_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f4(datasize, data, proc_cap):
  self.logger.info('f4 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f4'],
                            proc_cap = proc_cap)
  self.logger.info('f4_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data

itfunc_dict = {'f0':f0,
               'f1':f1,
               'f2':f2,
               'f3':f3,
               'f4':f4}
  
def main(argv):
  nodename = intf = dtsl_ip = dtsl_port= dtst_port = logto = trans_type = None
  try:
    opts, args = getopt.getopt(argv,'',['nodename=','intf=','dtsl_ip=','dtsl_port=','dtst_port=','logto=','trans_type='])
  except getopt.GetoptError:
    print 'transit.py --nodename=<> --intf=<> --dtsl_ip=<> --dtsl_port=<> --dtst_port=<> --logto=<> --trans_type=<>'
    sys.exit(2)
  #Initializing global variables with comman line options
  for opt, arg in opts:
    if opt == '--nodename':
      nodename = arg
    elif opt == '--intf':
      intf = arg
    elif opt == '--dtsl_ip':
      dtsl_ip = arg
    elif opt == '--dtsl_port':
      dtsl_port = int(arg)
    elif opt == '--dtst_port':
      dtst_port = int(arg)
    elif opt == '--logto':
      logto = arg
    elif opt == '--trans_type':
      trans_type = arg
  #where to log, console or file
  if logto == 'file':
    fname = 'logs/'+nodename+'.log'
    logging.basicConfig(filename=fname,filemode='w',level=logging.DEBUG)
  elif logto == 'console':
    logging.basicConfig(level=logging.DEBUG)
  else:
    raise CommandLineOptionError('Unexpected logto', logto)
  logger = logging.getLogger('t')
  #
  tl_ip = get_addr(intf)
  tr = Transit(nodename = nodename,
               tl_ip = tl_ip,
               tl_port = dtst_port,
               dtsl_ip = dtsl_ip,
               dtsl_port = dtsl_port,
               trans_type = trans_type,
               logger = logger )
  #
  if nodename == 'mfa':
    tr.test()
    raw_input('Enter')
    tr.shutdown()
  else:
    time.sleep(100000)
    tr.shutdown()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  
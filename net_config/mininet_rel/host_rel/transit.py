#!/usr/bin/python

import sys,getopt,commands,pprint,mmap,logging,os
import SocketServer,threading,time,socket,thread
from errors import CommandLineOptionError,NoItruleMatchError
from control_comm_intf import ControlCommIntf

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

CHUNKSIZE = 1024 #B
NUMCHUNKS_AFILE = 10
RXED_SIZE = -1

##########################  File TCP Server-Handler  ###########################
class FilePipeServer():
  def __init__(self, server_addr, itwork_dict, to_addr):
    self.server_addr = server_addr
    self.s_tp_dst = int(self.server_addr[1])
    self.itwork_dict = itwork_dict
    self.to_addr = to_addr
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
      logging.error('filepipe_server:: Could not open socket=%s', message )
      sys.exit(2)

  def start(self):    
    self.open_socket()
    logging.debug('filepipe_server:: serversock_stpdst=%s is opened; waiting for client.', self.s_tp_dst)

    self.sc_handler = SessionClientHandler(self.server_sock.accept(),
                                           itwork_dict = self.itwork_dict,
                                           to_addr = self.to_addr,
                                           s_tp_dst = self.s_tp_dst )
    self.sc_handler.start()
    #
    self.itserv_handler = ItServiceHandler(itwork_dict = self.itwork_dict,
                                           s_tp_dst = self.s_tp_dst,
                                           to_addr = self.to_addr )
    self.itserv_handler.start()
    #
    logging.debug('filepipe_server:: server_addr=%s started.', self.server_addr)
    #threads will handle the rest no need for further listening
    self.server_sock.close()
    logging.debug('filepipe_server:: done.')
    

  def shutdown(self):
    logging.info('filepipe_server:: shutdown.')

class SessionClientHandler(threading.Thread):
  def __init__(self,(sclient_sock,sclient_addr), itwork_dict, to_addr, s_tp_dst):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.sclient_sock = sclient_sock
    self.sclient_addr = sclient_addr
    self.s_tp_dst = s_tp_dst
    #for now pipe is list of files
    #num_chunks_in_file chunks will be stored in a single file
    #NUMCHUNKS_AFILE % recv_size = 0
    self.recv_size = 1 #chunks
    self.num_chunks_in_file = NUMCHUNKS_AFILE
    self.pipe_size = 0 #chunks
    self.pipe_size_ = 0 #chunks
    self.pipe_size_B = 0

    self.pipe_file_base_str = 'pipe/pipe_tpdst=%s_' % self.s_tp_dst
    self.pipe_file_id = 0
    self.pipe_mm = None
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
    
  def run(self):
    logging.debug('session_client_handler:: sclient_addr=%s started', self.sclient_addr)
    rxcomplete = False
    while not rxcomplete:
      data = self.sclient_sock.recv(self.recv_size*CHUNKSIZE)
      datasize = sys.getsizeof(data) - 37 #in MB
      logging.info('session_client_handler:: stpdst=%s; rxed datasize=%sB, pipe_size=%s, pipe_size_B=%sB', self.s_tp_dst, datasize, self.pipe_size, self.pipe_size_B)
      if datasize < 50:
        logging.debug('data=%s', data)
      #
      if data == 'EOF':
        self.flush_pipe_mm()
        global RXED_SIZE
        RXED_SIZE = self.pipe_size
        logging.info('session_client_handler:: EOF is rxed...')
        rxcomplete = True
        continue
      #
      self.push_to_pipe(data, datasize)
      self.check_file.write(data)
    #
    logging.debug('session_client_handler:: done.')
    self.check_file.close()

  def push_to_pipe(self, data, datasize):
    if self.pipe_size % self.num_chunks_in_file == 0: #time for new pipe_file
      if self.pipe_mm != None:
        #thread.start_new_thread(self.flush_pipe_mm, (self.pipe_mm, self.pipe_file_id) )
        self.flush_pipe_mm()
        self.pipe_file_id += 1
      #
      try:
        self.pipe_mm = mmap.mmap(fileno = -1, length = self.num_chunks_in_file*CHUNKSIZE) #(CHUNKSIZE+37) )
      except Exception, e:
        logging.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
        sys.exit(2)
      #
    #
    try:
      self.pipe_mm.write(data)
      self.pipe_size += self.recv_size
      self.pipe_size_ += self.recv_size
      self.pipe_size_B += datasize
    except TypeError as e:
      logging.error('session_client_handler:: Could not write to pipe_mm. Check mmap.access')
      logging.error('e.errno=%s, e.strerror=%s', e.errno, e.strerror)
    #
    logging.debug('session_client_handler:: datasize=%s is pushed to pipe.', datasize)
    self.s_active_last_time = time.time()
  
  def flush_pipe_mm(self):
    fileurl = self.pipe_file_base_str+str(self.pipe_file_id)
    pipe_file = open(fileurl+'.dat', 'w')
    pipe_file.write(self.pipe_mm[:])
    pipe_file.close()
    self.pipe_mm.close()
    self.pipe_mm = None
    #
    logging.debug('session_client_handler:: pipe_file_id=%s is ready', self.pipe_file_id)
    logging.debug('session_client_handler:: BTW pipe_size_=%s is flushed', self.pipe_size_)
    self.pipe_size_ = 0

  '''
  def flush_pipe_mm(self, pipe_mm, pipe_file_id):
    fileurl = self.pipe_file_base_str+str(pipe_file_id)
    pipe_file = open(fileurl+'.dat', 'w')
    pipe_file.write(pipe_mm[:])
    pipe_file.close()
    pipe_mm.close()
    logging.debug('session_client_handler:: pipe_file_id=%s is ready', pipe_file_id)
  '''
  def handle_s_softexpire(self):
    while True:
      #logging.debug('handle_s_softexpire::')
      inactive_time_span = time.time() - self.s_active_last_time
      if inactive_time_span >= self.s_soft_state_span:
        self.s_soft_expired = True
        logging.info('session_client_handler:: session_tp_dst=%s soft-expired.',self.s_tp_dst)
        return
      # do every ... secs
      time.sleep(self.s_soft_state_span)

class ItServiceHandler(threading.Thread):
  def __init__(self, itwork_dict, s_tp_dst, to_addr):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.itwork_dict = itwork_dict
    self.s_tp_dst = s_tp_dst
    self.to_addr = to_addr
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
    self.num_chunks_in_file = NUMCHUNKS_AFILE
    #num_chunks_in_file % serv_size = 0
    self.serv_size = 1 #chunks
    self.served_size = 0 #chunks
    self.served_size_ = 0 #chunks, keeps for current file
    #
    self.pipe_file_base_str = 'pipe/pipe_tpdst=%s_' % self.s_tp_dst
    self.pipe_file_id = 0
    self.pipe_file = None
    self.pipe_mm = None
    #
    self.max_idle_time = 5 #_after_serv_started, secs
    self.active_last_time = None
    self.serv_started = False
    self.serv_over = False
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
    logging.debug('itserv_handler:: run.')
    while not self.serv_over:
      (data, datasize) = self.pop_from_pipe()
      if data != None:
        if not self.serv_started:
          self.serv_started = True
        #
        self.active_last_time = time.time()
        #data_ = self.proc(data, self.serv_size)
        #self.forward_data(data_, self.serv_size)
        self.served_size += self.serv_size
        self.served_size_ += self.serv_size
        self.served_size_B += datasize
        #
        self.test_file.write(data)
        self.test_file_size += self.serv_size
        self.test_file_size_B += datasize
        logging.debug('itserv_handler:: acted on datasize=%s, test_file_size=%s, test_file_size_B=%sB, served_size=%s, served_size_=%s', datasize, self.test_file_size, self.test_file_size_B, self.served_size, self.served_size_)
      else:
        if RXED_SIZE != -1 and self.served_size == RXED_SIZE:
          logging.debug('itserv_handler:: RXED_SIZE=%s', RXED_SIZE)
          self.serv_over = True
        if self.serv_started and ((time.time()-self.active_last_time) >= self.max_idle_time):
          self.serv_over = True
    #
    logging.info('itserv_handler:: done.')
    self.test_file.close()

  def pop_from_pipe(self):
    if self.served_size % self.num_chunks_in_file == 0:
      if self.pipe_file != None and self.pipe_mm != None: #time to move to next file
        #logging.debug('served_size=%s', self.served_size)
        #thread.start_new_thread(self.delete_pipe_file, (self.pipe_mm, self.pipe_file, pipe_file_id_) )
        self.delete_pipe_file()
        self.served_size_ = 0
        self.pipe_file_id += 1
      #
      try:
        fileurl = self.pipe_file_base_str+str(self.pipe_file_id)
        self.pipe_file = open(fileurl+'.dat', 'r+')
        self.pipe_mm = mmap.mmap(fileno = self.pipe_file.fileno(),
                                 length = 0,
                                 access=mmap.ACCESS_READ )
        logging.debug('itserv_handler:: pipe_mm.size()=%s', self.pipe_mm.size())
      except Exception, e:
        #logging.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
        #logging.error('served_size=%s\npipe_file_id=%s', self.served_size, self.pipe_file_id)
        #sys.exit(2)
        return (None, 0)
    #
    try:
      datasize = self.serv_size*CHUNKSIZE
      #i = self.served_size_*datasize
      #j = (self.served_size_+1)*datasize
      #chunk = self.pipe_mm[i:j]
      chunk = self.pipe_mm.read(datasize)
      chunk_size = sys.getsizeof(chunk) - 37
      #
      return (chunk, chunk_size)
    except Exception, e:
      #logging.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      #sys.exit(2)
      return (None, 0)

  def delete_pipe_file(self):
    self.pipe_mm.close()
    self.pipe_mm = None
    self.pipe_file.close()
    self.pipe_file = None
    #
    fileurl = self.pipe_file_base_str+str(self.pipe_file_id)+'.dat'
    '''
    try:
      os.remove(fileurl)
    except OSError, e:
      logging.error('itserv_handler:: for fileurl=%s' % fileurl)
      logging.error('Error: %s - %s.' % (e.errno,e.strerror))
      #self.serv_over = True
      return
    '''
    #
    logging.debug('itserv_handler:: pipe_file_id=%s is deleted from pipe', self.pipe_file_id)

  #~~~~~~~~~~~~~~~~~~~~~~~~~  IT data transport  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  def forward_data(self, data, datasize):
    if not self.forwarding_started:
      logging.info('itserv_handler:: itserv_sock is trying to connect to addr=%s', self.to_addr)
      self.sock.connect(self.to_addr)
      self.forwarding_started = True
    #
    self.sock.sendall(data)
    logging.info('itserv_handler:: datasize=%s forwarded to_addr=%s', datasize, to_addr)
  
  #~~~~~~~~~~~~~~~~~~~~~~~~~  IT data manipulation  ~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  def proc(self, data, datasize):
    #datasize is in B, datasize_ is in Mb
    datasize_ = float(8*datasize)/1024
    #
    jobtobedone = self.itwork_dict['jobtobedone']
    proc_cap = self.itwork_dict['proc']
    data_ = None
    for ftag in jobtobedone:
      data_ = self.itfunc_dict[ftag](datasize_, data, proc_cap)
      #
      datasize_ = float(8*getsizeof(data_))/1024
      data = data_
    #
    return data

  def proc_time_model(self, datasize, func_comp, proc_cap):
    '''
    proc_time_model used in sching process. To see if the sching results can be reaklized
    by assuming used models for procing are perfectly accurate.
    '''
    proc_t = 1000*float(func_comp)*float(float(datasize)/64)*float(1/float(proc_cap)) #(ms)
    #logging.info('1000*%s*(%s/64)*(1/%s)=%s', func_comp, datasize, proc_cap, proc_t)
    return proc_t
    
  # transit data manipulation functions
  def f0(self, datasize, data, proc_cap):
    logging.info('itserv_handler:: f0 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f0'],
                                   proc_cap = proc_cap)
    logging.info('itserv_handler:: f0_sleep=%s', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f1(self, datasize, data, proc_cap):
    logging.info('itserv_handler:: f1 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f1'],
                                   proc_cap = proc_cap)
    logging.info('itserv_handler:: f1_sleep=%s', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f2(self, datasize, data, proc_cap):
    logging.info('itserv_handler:: f2 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f2'],
                                   proc_cap = proc_cap)
    logging.info('itserv_handler:: f2_sleep=%s', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f3(self, datasize, data, proc_cap):
    logging.info('itserv_handler:: f3 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f3'],
                                   proc_cap = proc_cap)
    logging.info('itserv_handler:: f3_sleep=%s', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data
    
  def f4(self, datasize, data, proc_cap):
    logging.info('itserv_handler:: f4 is on action')
    t_sleep = self.proc_time_model(datasize = datasize,
                                   func_comp = self.func_comp_dict['f4'],
                                   proc_cap = proc_cap)
    logging.info('itserv_handler:: f4_sleep=%s', t_sleep)
    time.sleep(t_sleep)
    #for now no manipulation on data, just move the data forward !
    return data

##########################  Dummy UDP Server-Handler  ##########################
class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
  def __init__(self, call_back, server_addr, RequestHandlerClass):
    SocketServer.UDPServer.__init__(self, server_addr, RequestHandlerClass)
    self.call_back = call_back
  
class ThreadedUDPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request[0].strip()
    #socket = self.request[1]
    cur_thread = threading.current_thread()
    server = self.server
    s_tp_dst = int(server.server_address[1])
    datasize = sys.getsizeof(data) #in MB
    logging.info('cur_udp_thread=%s; s_tp_dst=%s, rxed_data_size=%sB', cur_thread.name, s_tp_dst, datasize)
    #
    server.call_back(s_tp_dst, data, datasize)
##########################  Dummy TCP Server-Handler  ##########################
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, call_back, server_addr, RequestHandlerClass):
    SocketServer.TCPServer.__init__(self, server_addr, RequestHandlerClass)
    self.call_back = call_back
  
class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):
  def handle(self):
    data = self.request.recv(CHUNKSIZE)
    #
    cur_thread = threading.current_thread()
    server = self.server
    s_tp_dst = int(server.server_address[1])
    datasize = sys.getsizeof(data) #in MB
    logging.info('cur_tcp_thread=%s; s_tp_dst=%s, rxed_data_size=%sB', cur_thread.name, s_tp_dst, datasize)
    #
    server.call_back(s_tp_dst, data, datasize)
#############################  Class Transit  ##################################
class Transit(object):
  def __init__(self, nodename, tl_ip, tl_port, dtsl_ip, dtsl_port, trans_type):
    if not (trans_type == 'file' or trans_type == 'console'):
      logging.error('Unexpected trans_type=%s', trans_type)
    self.trans_type = trans_type
    #
    self.nodename = nodename
    self.tl_ip = tl_ip
    self.tl_port = tl_port
    self.dtsl_ip = dtsl_ip
    self.dtsl_port = dtsl_port
    #
    self.s_info_dict = {}
    #for control comm
    self.cci = ControlCommIntf()
    self.cci.reg_commpair(sctag = 't-dts',
                          proto = 'udp',
                          _recv_callback = self._handle_recvfromdts,
                          s_addr = (self.tl_ip,self.tl_port),
                          c_addr = (self.dtsl_ip,self.dtsl_port) )
    #
    """
    self.session_soft_state_span = 1000
    s_soft_expire_timer = threading.Timer(self.session_soft_state_span,
                                          self._handle_SessionSoftTimerExpire)
    s_soft_expire_timer.daemon = True
    s_soft_expire_timer.start()
    """
    #
    logging.info('%s is ready...', self.nodename)
  
  def _handle_SessionSoftTimerExpire(self):
    while True:
      #logging.info('_handle_SessionSoftTimerExpire;')
      #print 's_info_dict:'
      #pprint.pprint(s_info_dict )
      for s_tp_dst, s_info in self.s_info_dict.items():
        inactive_time_span = time.time() - s_info['s_active_last_time']
        if inactive_time_span >= self.session_soft_state_span: #soft state expire
          s_info['s_server_thread'].shutdown()
          del self.s_info_dict[s_tp_dst]
          logging.info('inactive_time_span=%s\ns with tp_dst:%s is soft-expired.',inactive_time_span,s_tp_dst)
      #
      #logging.info('------')
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
    if stpdst in self.s_info_dict:
      self.bye_s(stpdst)
    del data_['s_tp']
    #
    to_ip = data_['data_to_ip']
    del data_['data_to_ip']
    #
    to_addr = (to_ip, stpdst) #goes into s_info_dict
    #
    jobtobedone = {ftag:1024*data_['datasize']*comp/func_comp_dict[ftag] \
                     for ftag,comp in data_['itfunc_dict'].items() }
    data_.update( {'jobtobedone': jobtobedone} )
    #
    proto = int(data_['proto']) #6:TCP, 17:UDP - goes into s_info_dict
    del data_['proto']
    #calc est_proct
    est_proct = proc_time_model(datasize = float(data_['datasize']),
                                func_comp = float(data_['comp']),
                                proc_cap = float(data_['proc']))
    #
    if self.trans_type == 'file':
      s_server_thread = FilePipeServer(server_addr = (self.tl_ip, stpdst),
                                       itwork_dict = data_,
                                       to_addr = to_addr )
      s_server_thread.start()
      self.s_info_dict[stpdst] = {'itjobrule':data_,
                                  'to_addr': to_addr,
                                  's_server_thread': s_server_thread,
                                  'est_proct': est_proct }
    elif self.trans_type == 'dummy':
      self.s_info_dict[stpdst] = {'itjobrule':data_,
                                  'proto': proto,
                                  'to_addr': to_addr,
                                  's_server_thread': self.create_sserver_thread(proto = proto, port = stpdst),
                                  's_active_last_time':time.time(),
                                  'est_proct': est_proct }
    #
    logging.info('welcome new_s; tpdst=%s, s_info=\n%s', stpdst, pprint.pformat(self.s_info_dict[stpdst]))
  
  def bye_s(self, stpdst):
    if self.trans_type == 'dummy':
      self.s_info_dict[stpdst]['s_server_thread'].shutdown()
    elif self.trans_type == 'file':
      self.s_info_dict[stpdst]['s_server_thread'].close()
    #ready to erase s_info
    del self.s_info_dict[stpdst]
    logging.info('bye s; tpdst=%s', stpdst)
  
  def shutdown(self):
    logging.debug('shutting down...')
    for s_tp_dst, s_info in self.s_info_dict.items():
      s_info['s_server_thread'].shutdown()
      logging.debug('thread for server_s_tp_dst=%s is terminated', s_tp_dst)
    #this may close created sub-threads
    sys.exit(2)
  
  #########################  handle s_data_traffic  ############################
  def create_sserver_thread(self, proto, port):
    s_addr = (self.tl_ip, port)
    s_server = None
    if proto == 6:
      s_server = ThreadedTCPServer(self._handle_recvsdata, s_addr, ThreadedTCPRequestHandler)
    elif proto == 17:
      s_server = ThreadedUDPServer(self._handle_recvsdata, s_addr, ThreadedUDPRequestHandler)
    else:
      logging.error('Unexpected proto=%s', proto)
      return
    #
    s_server_thread = threading.Thread(target=s_server_thread.serve_forever)
    s_server_thread.daemon = True
    s_server_thread.start()
    #
    logging.info('%s_server_thread is started at s_addr=%s', proto,s_addr )
    return s_server
  
  def _handle_recvsdata(self, s_tp_dst, data, datasize):
    if not s_tp_dst in self.s_info_dict:
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
    itjobrule = self.s_info_dict[s_tp_dst]['itjobrule']
    jobtobedone = itjobrule['jobtobedone']
    proc_cap = itjobrule['proc']
    #datasize_ = 8*len(data) #in bits
    for ftag,compleft in jobtobedone.items():
      datasize = float(8*datasize)/1024
      data = itfunc_dict[ftag](datasize, data, proc_cap)
      #for now no need for checking how much left to process for session
      """
      if jobtobedone[ftag] > 0:
        datasize = float(8*sys.getsizeof(data))/1024
        data = itfunc_dict[ftag](datasize, data, proc_cap)
        #update jobtobedone
        jobtobedone[ftag] -= datasize
      """
    #
    return data
  
  def forward_data(self, s_tp_dst, data, datasize):
    s_info = self.s_info_dict[s_tp_dst]
    proto = s_info['proto']
    to_addr = s_info['to_addr']
    #
    sock = None
    if proto == 6:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      logging.info('s_tcpsock is trying to connect to addr=%s', to_addr)
      sock.connect(to_addr)
      sock.sendall(data)
      #datasent_size = sock.send(data)
    elif proto == 17:
      sock.sendto(data, to_addr)
    #
    logging.info('proced data is forwarded to_addr=%s', to_addr)
    #update session_active_last_time
    s_info['s_active_last_time']=time.time()
  
  def test(self):
    logging.debug('test')
    data = {'comp': 1.99999998665,
            'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': 1.0,
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
  '''
  proc_t = 1000*float(func_comp)*float(float(datasize)/64)*float(1/float(proc_cap)) #(ms)
  #logging.info('1000*%s*(%s/64)*(1/%s)=%s', func_comp, datasize, proc_cap, proc_t)
  return proc_t
  
# transit data manipulation functions
def f0(datasize, data, proc_cap):
  logging.info('f0 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f0'],
                            proc_cap = proc_cap)
  logging.info('f0_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f1(datasize, data, proc_cap):
  logging.info('f1 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f1'],
                            proc_cap = proc_cap)
  logging.info('f1_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f2(datasize, data, proc_cap):
  logging.info('f2 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f2'],
                            proc_cap = proc_cap)
  logging.info('f2_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f3(datasize, data, proc_cap):
  logging.info('f3 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f3'],
                            proc_cap = proc_cap)
  logging.info('f3_sleep=%s', t_sleep)
  time.sleep(t_sleep)
  #for now no manipulation on data, just move the data forward !
  return data
  
def f4(datasize, data, proc_cap):
  logging.info('f4 is on action')
  t_sleep = proc_time_model(datasize = datasize,
                            func_comp = func_comp_dict['f4'],
                            proc_cap = proc_cap)
  logging.info('f4_sleep=%s', t_sleep)
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
  #
  tl_ip = get_addr(intf)
  tr = Transit(nodename = nodename,
               tl_ip = tl_ip,
               tl_port = dtst_port,
               dtsl_ip = dtsl_ip,
               dtsl_port = dtsl_port,
               trans_type = trans_type )
  tr.test()
  #
  raw_input('Enter')
  tr.shutdown()
  #time.sleep(100000)
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

#!/usr/bin/python

import sys,getopt,commands,pprint,mmap,logging,os,Queue,errno,signal,copy
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

CHUNKSIZE = 24*8*9*10 #B
NUMCHUNKS_AFILE = 10

class FilePipeServer(threading.Thread):
  def __init__(self, server_addr, itwork_dict, to_addr, sflagq, stokenq):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.server_addr = server_addr
    self.stpdst = int(self.server_addr[1])
    self.itwork_dict = itwork_dict
    self.to_addr = to_addr
    self.sflagq = sflagq
    self.stokenq = stokenq
    #
    self.logger = logging.getLogger('filepipeserver')
    #
    self.pipefileurl_q = Queue.Queue(0)
    self.flagq_tosubthreads = Queue.Queue(1) #to be able to close SessionClientHandler thread
    #
    self.sc_handler = None
    self.server_sock = None
    self.itserv_handler = None
  
  def open_socket(self):
    try:
      self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.server_sock.bind(self.server_addr)
      self.server_sock.listen(0) #only single client can be served
    except socket.error, (value,message):
      if self.server_sock:
        self.server_sock.close()
      self.logger.error('Could not open socket=%s', message )
      sys.exit(2)
  
  def run(self):
    self.open_socket()
    self.logger.debug('run:: serversock_stpdst=%s is opened; waiting for client.', self.stpdst)
    try:
      (sclient_sock,sclient_addr) = self.server_sock.accept()
    except Exception, e:
      self.logger.error('Most likely transit.py is terminated with ctrl-c')
      self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      return
      
    self.sc_handler = SessionClientHandler((sclient_sock,sclient_addr),
                                           itwork_dict = self.itwork_dict,
                                           to_addr = self.to_addr,
                                           stpdst = self.stpdst,
                                           pipefileurl_q = self.pipefileurl_q,
                                           flagq = self.flagq_tosubthreads )
    self.sc_handler.start()
    
    self.itserv_handler = ItServHandler(itwork_dict = self.itwork_dict,
                                        stpdst = self.stpdst,
                                        to_addr = self.to_addr,
                                        pipefileurl_q = self.pipefileurl_q,
                                        flagq = self.flagq_tosubthreads,
                                        stokenq = self.stokenq )
    self.itserv_handler.start()
    #
    self.logger.debug('run:: server_addr=%s started.', self.server_addr)
    #
    flag = self.sflagq.get(True, None)
    if flag == 'STOP':
      self.shutdown()
    else:
      self.logger('Unexpected flag=%s', flag)
    #
    self.logger.debug('run:: done.')
  
  def shutdown(self):
    #
    self.server_sock.shutdown(socket.SHUT_RDWR)
    self.server_sock.close()
    #close sc_handler
    self.flagq_tosubthreads.put('STOP')
    #close itserv_handler
    self.pipefileurl_q.put('EOF')
    #
    self.logger.info('shutdown.')

class SessionClientHandler(threading.Thread):
  def __init__(self,(sclient_sock,sclient_addr), itwork_dict, to_addr, stpdst,
               pipefileurl_q, flagq ):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.sclient_sock = sclient_sock
    self.sclient_addr = sclient_addr
    self.stpdst = stpdst
    self.pipefileurl_q = pipefileurl_q
    self.flagq = flagq
    #
    self.logger = logging.getLogger('sessionclienthandler_%s' % stpdst)
    #for now pipe is list of files
    self.recv_size = 1 #chunks
    self.num_chunks_afile = NUMCHUNKS_AFILE
    self.num_Bs_afile = NUMCHUNKS_AFILE*CHUNKSIZE
    self.pipe_size = 0 #chunks
    self.pipe_size_ = 0 #chunks
    self.pipe_size_B_ = 0 #Bs
    self.pipe_size_B = 0 #Bs

    self.pipe_file_base_str = 'pipe/pipe_tpdst=%s_' % self.stpdst
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
    #
    self.startedtorx_time = None
    
  def run(self):
    self.startedtorx_time = time.time()
    
    self.logger.debug('run:: sclient_addr=%s', self.sclient_addr)
    threading.Thread(target = self.init_rx).start()
    popped = self.flagq.get(True, None)
    if popped == 'STOP':
      #brute force to end init_rx thread
      self.sclient_sock.close()
      self.logger.debug('run:: stopped by STOP flag !')
    elif popped == 'EOF':
      self.logger.debug('run:: stopped by EOF.')
    else:
      self.logger.debug('run:: unexpected popped=%s', popped)
    #
    self.stoppedtorx_time = time.time()
    self.logger.debug('run:: done. \n\tpipe_size=%s, pipe_size_B=%s\n\tin dur=%ssecs, at t=%s;', self.pipe_size, self.pipe_size_B, self.stoppedtorx_time-self.startedtorx_time, self.stoppedtorx_time)
  
  def init_rx(self):
    #
    rxcomplete = False
    while 1:
      data = self.sclient_sock.recv(self.recv_size*CHUNKSIZE)
      #
      if self.startedtorx_time == None:
        self.startedtorx_time = time.time()
      #
      datasize = getsizeof(data)
      self.logger.info('init_rx:: stpdst=%s; rxed datasize=%sB', self.stpdst, datasize)
      #
      return_ = self.push_to_pipe(data, datasize)
      if return_ == 0: #failed
        self.logger.error('init_rx:: push_to_pipe for datasize=%s failed. Aborting...', datasize)
        sys.exit(2)
      elif return_ == -1: #EOF
        self.logger.info('init_rx:: EOF is rxed...')
        self.pipefileurl_q.put('EOF')
        self.flagq.put('EOF')
        break
      elif return_ == -2: #datasize=0
        self.logger.info('init_rx:: datasize=0 is rxed...')
        self.flush_pipe_mm()
        self.flagq.put('STOP')
        break
      elif return_ == 1: #success
        pass
        #self.check_file.write(data)
      #
    #
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
      self.logger.error('push_to_pipe:: Could not write to pipe_mm. Check mmap.access')
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
    self.logger.debug('push_to_pipe:: datasize=%s pushed to pipe, pipe_size_B_=%s, overflow_size=%s', datasize, self.pipe_size_B_, overflow_size)
    self.s_active_last_time = time.time()
    return 1
    
  def flush_pipe_mm(self):
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
      self.logger.debug('flush_pipe_mm:: pipe_file_id=%s is ready; btw flushed pipe_size_B_=%s', self.pipe_file_id, self.pipe_size_B_)
      self.pipe_size_ = 0
      self.pipe_size_B_ = 0
      #
      self.pipefileurl_q.put(fileurl)
    except Exception, e:
      self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
  
  def handle_s_softexpire(self):
    while True:
      #self.logger.debug('handle_s_softexpire::')
      inactive_time_span = time.time() - self.s_active_last_time
      if inactive_time_span >= self.s_soft_state_span:
        self.s_soft_expired = True
        self.logger.info('flush_pipe_mm:: session_tp_dst=%s soft-expired.',self.stpdst)
        return
      # do every ... secs
      time.sleep(self.s_soft_state_span)

class ItServHandler(threading.Thread):
  def __init__(self, itwork_dict, stpdst, to_addr,
               pipefileurl_q, flagq, stokenq):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.itwork_dict = itwork_dict
    self.stpdst = stpdst
    self.to_addr = to_addr
    self.pipefileurl_q = pipefileurl_q
    self.flagq = flagq
    self.stokenq = stokenq
    #
    self.logger = logging.getLogger('itservhandler_%s' % stpdst)
    #
    self.stopflag = False
    
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
    #
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.forwarding_started = False
    #for test...
    self.test_file = open('pipe/testfile.dat', 'w')
    self.test_file_size = 0 #serv_size
    self.test_file_size_B = 0 #B
    self.served_size_B = 0 #B
    #
    self.startedtohandle_time = None
    self.totalproc_time = 0
    #
    #to integrate ecei_proc
    self.ftag_fifoid_dict = {'fft':0, 'upsample':0, 'plot':0}
    self.ftag_servsize_dict = {'fft':1, 'upsample':1, 'plot':64} #chunks
    
    self.procsock_dict = {'fft': None, 'upsample': None, 'plot': None}
    self.toprocaddr_dict = {'fft': ('127.0.0.1', 7000),
                            'upsample': ('127.0.0.1', 7001),
                            'plot': ('127.0.0.1', 7002) }
    
    
    self.uptojobdone = self.itwork_dict['uptojobdone']
    self.uptorecvsize_dict = {}
    for ftag,datasize in self.uptojobdone.items():
      self.uptorecvsize_dict[ftag] = datasize*(1024**2) #B
    
    self.jobtobedone_dict = self.itwork_dict['jobtobedone']
    self.jobremaining = {}
    for ftag,datasize in self.jobtobedone_dict.items():
      self.jobremaining[ftag] = datasize*(1024**2)*self.ftag_servsize_dict[ftag] #B
    #
    self.logger.debug('itservhandler:: jobremaining=\n%s', pprint.pformat(self.jobremaining))
  
  def get_itfunclist_overnextchunk(self):
    def reorder(itfunc_list):
      ordered_list = []
      idealfunc_order = ['fft', 'upsample', 'plot']
      for func in idealfunc_order:
        if func in itfunc_list:
          ordered_list.append(func)
      #
      return ordered_list
    #
    itfunc_list = []
    uptoserved_size_B = self.served_size_B + self.served_size_B_
    
    for ftag in self.jobtobedone_dict:
      if ftag in self.uptorecvsize_dict:
        if uptoserved_size_B >= self.uptorecvsize_dict[ftag]:
          itfunc_list.append(ftag)
      else:
        itfunc_list.append(ftag)
    #
    return reorder(itfunc_list)
  
  def init_procsock(self):
    for func in self.procsock_dict:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.connect(self.toprocaddr_dict[func])
      self.procsock_dict[ftag] = sock
    #
  
  def run(self):
    self.init_procsock()
    self.startedtohandle_time = time.time()
    #
    while not self.stopflag:
      #wait for the proc turn
      stoken = self.stokenq.get(True, None)
      if stoken == CHUNKSIZE:
        pass
      elif stoken == -1:
        self.stopflag = True
        continue
      else:
        self.logger.error('run:: Unexpected stoken=%s', stoken)
        self.stopflag = True
        continue
      #
      itfunc_list = self.get_itfunclist_overnextchunk()
      print 'itfunc_list=%s' % pprint.pformat(itfunc_list)
      try:
        firstitfunc = itfunc_list[0]
      except IndexError as e:
        firstitfunc = None
      #
      (data, datasize) = self.pop_from_pipe(firstitfunc)
      datasize_t = copy.copy(datasize)
      if data == None:
        if datasize == 0: #failed
          pass
        elif datasize == -1: #EOF
          self.logger.debug('run:: fileurl=EOF')
          self.stopflag = True
        elif datasize == -2: #STOP
          self.logger.debug('run:: stopped with STOP flag !')
          self.stopflag = True
        elif datasize == -3: #fatal
          self.logger.error('run:: sth unexpected happened. Check exceptions. Aborting...')
          sys.exit(2)
      else:
        self.logger.debug('run:: datasize=%s popped.', datasize)
        self.active_last_time = time.time()
        #
        #self.logger.debug('run:: ready proc and forward datasize=%s', datasize)
        
        #print 'itwork_dict=%s' % pprint.pformat(self.itwork_dict)
        [datasize_, data_] = [0, None]
        for func in itfunc_list:
          if self.jobremaining[func] > 0:
            [datasize_, data_] = self.proc(func = func,
                                           datasize = datasize,
                                           data = data )
            self.jobremaining[func] -= datasize
            datasize = datasize_
            data = data_
        #
        #datasize = getsizeof(data)
        #self.forward_data(data, datasize)
        
        self.served_size_ += self.serv_size
        self.served_size_B_ += datasize_t
        self.test_file.write(data)
        self.logger.debug('run:: acted on datasize=%sB, datasize_=%sB, self.served_size_B=%s, self.served_size_B_=%s', datasize_t, datasize_, self.served_size_B, self.served_size_B_)
    #
    self.test_file.close()
    self.sock.close()
    self.stoppedtohandle_time = time.time()
    self.logger.info('run:: done, dur=%ssecs, at time=%s', self.stoppedtohandle_time-self.startedtohandle_time, self.stoppedtohandle_time)
    self.logger.debug('run:: totalproc_time=%s, jobremaining=\n%s', self.totalproc_time, pprint.pformat(self.jobremaining))
  
  def proc(self, func, datasize, data):
    data_ = None
    datasize_ = None
    #
    sock = self.procsock_dict[func]
    sock.sendall(data)
    self.logger.debug('proc:: wrote to %s_procsock, datasize=%s', func, datasize)
    
    data_ = ''
    readsize = 0
    while readsize < self.procrwsize_dict[func]:
      data_ += sock.recv(RXCHUNK_SIZE)
    
    datasize_ = getsizeof(data_)
    self.logger.debug('proc:: read from %s_procsock, datasize=%s', func, datasize_)
    
    '''
    fifo_id = self.ftag_fifoid_dict[func]
    #first create data_fifo
    data_fifoname = 'fifo/'+func+'_'+str(self.stpdst)+'_data_fifo'+str(fifo_id)
    try:
      os.mkfifo(data_fifoname)
    except OSError as e:
      if not e.errno == 17: #File exists
        self.logger.error('Unexpected oserror, errno=%s', e.errno)
        return [0, None]
    #
    self.logger.debug('proc:: made data_fifoname=%s', data_fifoname)
    #then write data to datafifo
    datafifoname = 'fifo/'+func+'_'+str(self.stpdst)+'_datafifo'+str(fifo_id)
    self.ftag_fifoid_dict[func] += 1
    
    datafifo = open(datafifoname, 'w')
    
    print >> datafifo, data
    datafifo.close()
    """
    try:
      os.remove(datafifoname)
    except OSError, e:
      self.logger.error('Error: %s - %s.' % (e.errno,e.strerror))
      return [0, None]
    """
    #
    self.logger.debug('proc:: wrote to datafifo datasize=%s', datasize)
    #read data_ from data_fifo
    data_fifo = open(data_fifoname, 'r')
    data_ = data_fifo.read()
    datasize_ = getsizeof(data_)
    self.logger.debug('proc:: read from data_fifo datasize=%s', datasize_)
    '''
    #
    self.logger.debug('proc:: %s run on datasize=%s, datasize_=%s', func, datasize, datasize_)
    #
    return [datasize_, data_]
  
  def pop_from_pipe(self, itfunc):
    """ returns:
    (data, datasize): success
    (None, 0): failed
    (None, -1): EOF
    (None, -2): STOP
    (None, -3): fatal failure
    """
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
        self.cur_fileurl = self.pipefileurl_q.get(True, None)
        self.logger.debug('pop_from_pipe:: cur_fileurl=%s', self.cur_fileurl)
        if self.cur_fileurl == 'EOF':
          return (None, -1)
        #
        self.pipe_file = open(self.cur_fileurl, 'r+')
        self.pipe_mm = mmap.mmap(fileno = self.pipe_file.fileno(),
                                 length = 0,
                                 access=mmap.ACCESS_READ )
        self.logger.debug('pop_from_pipe:: pipe_mm.size()=%s, served_size=%s', self.pipe_mm.size(), self.served_size)
        self.pipe_file.close()
      except Exception, e:
        self.logger.error('pop_from_pipe:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
        return (None, -3)
    #
    try:
      if itfunc == None: #no proc will be done, just forward
        chunk = self.pipe_mm.read(self.serv_size_B)
      else:
        chunk = self.pipe_mm.read(self.ftag_servsize_dict[itfunc]*CHUNKSIZE)
    except Exception, e:
      self.logger.error('pop_from_pipe:: \ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      return (None, -3)
    #
    chunk_size = getsizeof(chunk)
    #self.logger.warning('pop_from_pipe:: chunksize=%s', chunk_size)
    if chunk_size <= 0:
      flag = self.flagq.get(False, None)
      if flag == 'STOP':
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
      self.logger.error('delete_pipe_file:: for cur_fileurl=%s', cur_fileurl)
      self.logger.error('Error: %s - %s.' % (e.errno,e.strerror))
      return
    #
    self.logger.debug('delete_pipe_file:: cur_fileurl=%s is deleted from pipe', cur_fileurl)

  def forward_data(self, data, datasize):
    """ TODO: returns:
    1: success
    0: failed
    """
    try:
      if not self.forwarding_started:
        self.logger.info('forward_data:: itserv_sock is trying to connect to addr=%s', self.to_addr)
        self.sock.connect(self.to_addr)
        self.logger.info('forward_data:: itserv_sock is connected to addr=%s', self.to_addr)
        self.forwarding_started = True
      #
      self.sock.sendall(data)
      self.logger.info('forward_data:: datasize=%s forwarded to_addr=%s', datasize, self.to_addr)
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
    #

#############################  Class Transit  ##################################
TOTALPROCCAP = 100 #Mflop/s
TOTALPROCCAP_B = TOTALPROCCAP*64*1024/8
NCHUNKS_PERSEC = TOTALPROCCAP_B/CHUNKSIZE
func_comp_dict = {'f0':0.5,
                  'f1':1,
                  'f2':2,
                  'f3':3,
                  'f4':4,
                  'fft':2,
                  'upsample':4,
                  'plot':4 }

def proc_time_model(datasize, func_comp, proc_cap):
  proc_t = float(func_comp)*float(8*float(datasize)/64)*float(1/float(proc_cap)) #secs
  #self.logger.info('%s*(%s/64)*(1/%s)=%s', func_comp, datasize, proc_cap, proc_t)
  return proc_t

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
    self.N = 0 #number of sessions being served
    #
    self.itrdts_intf = UserDTSCommIntf(sctag = 't-dts',
                                       user_addr = (self.tl_ip,self.tl_port),
                                       dts_addr = (self.dtsl_ip,self.dtsl_port),
                                       _recv_callback = self._handle_recvfromdts )
    #
    #to handle ctrl-c for doing cleanup
    signal.signal(signal.SIGINT, self.signal_handler)
    #for proc_power slicing
    self.stopflag = False
    self.sflagq_dict = {}
    self.stokenq_dict = {}
    #
    #threading.Thread(target = self.manage_stokenqs).start()
    #
    self.logger.info('%s is ready...', self.nodename)

  def manage_stokenq(self, stpdst, intereq_time):
    stokenq = self.stokenq_dict[stpdst]
    while not self.stopflag:
      try:
        stokenq.put(CHUNKSIZE, False)
      except Queue.Full:
        pass
      #self.logger.debug('manage_stokenq_%s:: sleeping for %ssecs', stpdst, intereq_time)
      time.sleep(intereq_time)
    #
    self.logger.debug('manage_stokenq_%s:: stoppped by STOP flag!', stpdst)
  
  ###  handle dts_comm  ###
  def _handle_recvfromdts(self, msg):
    [type_, data_] = msg
    if type_ == 'itjob_rule':
      self.welcome_s(data_)
  
  def welcome_s(self, data_):
    #If new_s with same tpdst arrives, old_s is overwritten by new_s
    stpdst = int(data_['s_tp'])
    if stpdst in self.sinfo_dict:
      self.bye_s(stpdst)
    del data_['s_tp']
    
    to_ip = data_['data_to_ip']
    del data_['data_to_ip']
    
    to_addr = (to_ip, stpdst) #goes into s_info_dict
    #
    uptojobdone = {}
    for ftag,comp in data_['uptoitfunc_dict'].items():
      uptojobdone[ftag] = data_['datasize']*comp/func_comp_dict[ftag]
    data_.update( {'uptojobdone': uptojobdone} )
    #
    jobtobedone = {}
    for ftag,comp in data_['itfunc_dict'].items():
      jobtobedone[ftag] = data_['datasize']*comp/func_comp_dict[ftag]
    data_.update( {'jobtobedone': jobtobedone} )
    #
    modelproct = proc_time_model(datasize = float(data_['datasize']),
                                 func_comp = float(data_['comp']),
                                 proc_cap = float(data_['proc']) )
    #
    proto = int(data_['proto']) #6:TCP, 17:UDP
    del data_['proto']
    #
    sflagq = Queue.Queue(0)
    stokenq = Queue.Queue(1)
    self.sflagq_dict[stpdst] = sflagq
    self.stokenq_dict[stpdst] = stokenq
    #
    nchunks = float(data_['datasize'])*(1024**2)/CHUNKSIZE
    intereq_time = modelproct/nchunks
    threading.Thread(target = self.manage_stokenq,
                     kwargs = {'stpdst':stpdst,
                               'intereq_time':intereq_time } ).start()
    #
    if self.trans_type == 'file':
      s_server_thread = FilePipeServer(server_addr = (self.tl_ip, stpdst),
                                       itwork_dict = data_,
                                       to_addr = to_addr,
                                       sflagq = sflagq,
                                       stokenq = stokenq )
      self.sinfo_dict[stpdst] = {'itjobrule':data_,
                                 'to_addr': to_addr,
                                 's_server_thread': s_server_thread,
                                 'modelproct': modelproct,
                                 'proc': float(data_['proc']),
                                 'intereq_time': intereq_time }
      s_server_thread.start()
      self.N += 1
    else:
      self.logger.error('Unexpected trans_type=%s', self.trans_type)
    #
    self.logger.info('welcome_s:: welcome stpdst=%s, s_info=\n%s', stpdst, pprint.pformat(self.sinfo_dict[stpdst]) )
  
  def bye_s(self, stpdst):
    self.sflagq_dict[stpdst].put('STOP')
    self.N -= 1
    del self.sinfo_dict[stpdst]
    self.logger.info('bye s; tpdst=%s', stpdst)
  
  def signal_handler(self, signal, frame):
    self.logger.info('signal_handler:: ctrl+c !')
    self.shutdown()
  
  def shutdown(self):
    self.stopflag = True
    #
    for stpdst,sflagq in self.sflagq_dict.items():
      sflagq.put('STOP')
    #
    self.itrdts_intf.close()
    self.logger.debug('shutdown:: shutdown.')
    sys.exit(0)
  
  def test(self):
    self.logger.debug('test')
    '''
    data = {'comp': 1.99999998665,
            'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': 7.8125,
            'itfunc_dict': {u'f1': 1.0, u'f2': 0.99999998665},
            'proc': 1, #1.0,
            's_tp': 6000 }
    '''
    imgsize = CHUNKSIZE/10
    #'uptoitfunc_dict': {'fft': 2.0, 'upsample': 2.0 }, #{'fft': 1.0},
    data = {'comp': 2.0,
            'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': float(imgsize*100)/(1024**2),
            'itfunc_dict': {'fft': 2.0}, #{'fft': 2.0, 'upsample': 4.0, 'plot': 4.0},
            'uptoitfunc_dict': {},
            'proc': 1.0,
            's_tp': 6000 }
    self.welcome_s(data)
      
    data = {'comp': 1.99999998665,
            'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': 7.8125,
            'itfunc_dict': {u'f1': 1.0, u'f2': 0.99999998665},
            'uptoitfunc_dict': {},
            'proc': 2, #1.0,
            's_tp': 6001 }
    self.welcome_s(data)
    

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
    raw_input('Enter\n')
    tr.shutdown()
  else:
    time.sleep(100000)
    tr.shutdown()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  
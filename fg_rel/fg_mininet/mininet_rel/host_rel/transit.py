#!/usr/bin/python

import sys,getopt,commands,pprint,mmap,logging,os,Queue,errno,signal,copy,json
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

CHUNKHSIZE = 50 #B
CHUNKSIZE = 24*8*9*10 #B
NUMCHUNKS_AFILE = 1000

class PipeServer(threading.Thread):
  def __init__(self, server_addr, itwork_dict, to_addr, sflagq_in, sflagq_out, stokenq, intereq_time):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.server_addr = server_addr
    self.stpdst = int(self.server_addr[1])
    self.itwork_dict = itwork_dict
    self.to_addr = to_addr
    self.sflagq_in = sflagq_in
    self.sflagq_out = sflagq_out
    self.stokenq = stokenq
    self.intereq_time = intereq_time
    #
    self.logger = logging.getLogger('filepipeserver')
    #
    self.pipefileurl_q = Queue.Queue(0)
    self.flagq_toitservhandler = Queue.Queue(1)
    self.flagq_tosessionhandler = Queue.Queue(1)
    #
    self.sc_handler = None
    self.server_sock = None
    self.itserv_handler = None
    #
    self.sstarted = False
  
  def listen_transit(self):
    self.logger.debug('listen_transit:: listening transit...')
    while 1:
      flag_in = self.sflagq_in.get(True, None)
      self.logger.debug('listen_transit:: Popped flag_in=%s', flag_in)
      
      if flag_in == 'STOP':
        self.shutdown()
        break
      else: #reitjob_rule
        self.itwork_dict = flag_in
        if self.sstarted: #need to inform itserv_handler thread
          self.flagq_toitservhandler.put(self.itwork_dict)
        #
        self.logger.debug('listen_transit:: NEW itwork_dict=%s', self.itwork_dict)
      #
    #
  
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
    t = threading.Thread(target = self.listen_transit)
    t.start()
    #
    self.open_socket()
    self.logger.debug('run:: serversock_stpdst=%s is opened; waiting for client.', self.stpdst)
    try:
      (sclient_sock,sclient_addr) = self.server_sock.accept()
      self.sstarted = True
    except Exception, e:
      self.logger.error('Most likely transit.py is terminated with ctrl-c')
      self.logger.error('\ne.__doc__=%s\n e.message=%s', e.__doc__, e.message)
      return
    #
    procq = Queue.Queue(0)
    
    self.itserv_handler = ItServHandler(itwork_dict = self.itwork_dict,
                                        stpdst = self.stpdst,
                                        to_addr = self.to_addr,
                                        flagq = self.flagq_toitservhandler,
                                        stokenq = self.stokenq,
                                        intereq_time = self.intereq_time,
                                        procq = procq )
    self.itserv_handler.start()
    
    self.sc_handler = SessionClientHandler((sclient_sock,sclient_addr),
                                           itwork_dict = self.itwork_dict,
                                           to_addr = self.to_addr,
                                           stpdst = self.stpdst,
                                           flagq = self.flagq_tosessionhandler,
                                           procq = procq )
    self.sc_handler.start()
    #
    self.logger.debug('run:: server_addr=%s started.', self.server_addr)
    #self.logger.debug('run:: done.')
  
  def shutdown(self):
    #
    self.server_sock.shutdown(socket.SHUT_RDWR)
    self.server_sock.close()
    #close sc_handler
    self.flagq_tosessionhandler.put('STOP')
    #close itserv_handler
    self.pipefileurl_q.put('EOF')
    #
    self.logger.info('shutdown.')

class SessionClientHandler(threading.Thread):
  def __init__(self,(sclient_sock,sclient_addr), itwork_dict, to_addr, stpdst,
               flagq, procq ):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.sclient_sock = sclient_sock
    self.sclient_addr = sclient_addr
    self.stpdst = stpdst
    self.flagq = flagq
    self.procq = procq
    #
    self.logger = logging.getLogger('sessionclienthandler_%s' % stpdst)
    self.startedtorx_time = None
    #session soft expire...
    self.s_soft_expired = False
    self.s_active_last_time = None
    self.s_soft_state_span = 1000 #secs
    soft_expire_timer = threading.Timer(self.s_soft_state_span,
                                        self.handle_s_softexpire )
    soft_expire_timer.daemon = True
    soft_expire_timer.start()
    #
    self.check_file = open('pipe/checkfile.dat', 'w')
    #
    self.chunk = ''
    
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
    self.logger.debug('run:: done. \n\tin dur=%ssecs, at t=%s;', self.stoppedtorx_time-self.startedtorx_time, self.stoppedtorx_time)
  
  def init_rx(self):
    while 1:
      data = self.sclient_sock.recv(CHUNKSIZE)
      datasize = getsizeof(data)
      #
      if self.startedtorx_time == None:
        self.startedtorx_time = time.time()
      #
      self.logger.info('init_rx:: stpdst=%s; rxed datasize=%sB', self.stpdst, datasize)
      #
      return_ = self.push_to_pipe(data)
      if return_ == 0: #failed
        self.logger.error('init_rx:: push_to_pipe for datasize=%s failed. Aborting...', datasize)
        sys.exit(2)
      elif return_ == -1: #EOF
        self.logger.info('init_rx:: EOF is rxed...')
        self.flagq.put('EOF')
        break
      elif return_ == -2: #datasize=0
        self.logger.info('init_rx:: datasize=0 is rxed...')
        self.flagq.put('STOP')
        break
      elif return_ == 1: #success
        self.s_active_last_time = time.time()
        #self.check_file.write(data)
      #
    #
    self.check_file.close()
    self.sclient_sock.close()
  
  def push_to_pipe(self, data):
    """ returns 1:successful, 0:failed, -1:EOF, -2:datasize=0 """
    self.chunk += data
    chunksize = getsizeof(self.chunk)
    #
    if chunksize == 0:
      #this may happen in mininet and cause threads live forever
      return -2
    elif chunksize == 3:
      if self.chunk == 'EOF':
        self.procq.put('EOF')
        return -1
    #
    overflow_size = chunksize - CHUNKSIZE
    if overflow_size == 0:
      self.procq.put(self.chunk)
      self.logger.debug('push_to_pipe:: pushed; chunksize=%s', chunksize)
      self.chunk = ''
      return 1
    elif overflow_size < 0:
      return 1
    #
    else: #overflow
      overflow = self.chunk[chunksize-overflow_size:]
      chunksize_ = chunksize-overflow_size
      chunk_to_push = self.chunk[:chunksize_]
      self.procq.put(chunk_to_push)
      self.logger.debug('push_to_pipe:: pushed; chunksize_=%s, overflow_size=%s', chunksize_, overflow_size)
      #
      if overflow_size == 3 and overflow == 'EOF':
        self.procq.put('EOF')
        return -1
      #
      self.chunk = overflow
      
      return 1
    #
    
  def handle_s_softexpire(self):
    while True:
      #self.logger.debug('handle_s_softexpire::')
      inactive_time_span = time.time() - self.s_active_last_time
      if inactive_time_span >= self.s_soft_state_span:
        self.s_soft_expired = True
        self.logger.info('handle_s_softexpire:: session_tp_dst=%s soft-expired.',self.stpdst)
        return
      # do every ... secs
      time.sleep(self.s_soft_state_span)

class ItServHandler(threading.Thread):
  def __init__(self, itwork_dict, stpdst, to_addr,
               flagq, stokenq, intereq_time, procq):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.itwork_dict = itwork_dict
    self.stpdst = stpdst
    self.to_addr = to_addr
    self.flagq = flagq
    self.stokenq = stokenq
    self.intereq_time = intereq_time
    self.procq = procq
    #
    self.logger = logging.getLogger('itservhandler_%s' % stpdst)
    #
    self.startedtohandle_time = None
    self.served_size_B = 0
    self.active_last_time = None
    
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.forwarding_started = False
    self.stopflag = False
    self.test_file = open('pipe/testfile.dat', 'w')
    #to integrate ecei_proc
    self.idealfunc_order = ['fft', 'upsampleplot']
    self.procsock_dict = {'fft': None, 'upsampleplot': None}
    self.procsockpath_dict = {'fft': 'fft',
                              'upsampleplot': 'upsampleplot' }
    self.procwrsize_dict = {'fft': {'wsize': CHUNKSIZE,
                                    'rsize': CHUNKSIZE },
                            'upsampleplot': {'wsize': CHUNKSIZE,
                                             'rsize': CHUNKSIZE }
                           }
    #
    self.jobtobedone_dict = None
    self.uptorecvsize_dict = {}
    self.jobremaining = {}
    
    self.init_itjobdicts()
    
  
  def init_itjobdicts(self):
    self.jobtobedone_dict = self.itwork_dict['jobtobedone']
    for ftag,datasize in self.jobtobedone_dict.items():
        self.jobremaining[ftag] = datasize*(1024**2) #B
    #
    self.logger.debug('init_itjobdicts:: jobremaining=\n%s', pprint.pformat(self.jobremaining))
  
  def reinit_itjobdicts(self):
    pre_jobtobedone_dict = self.jobtobedone_dict
    self.jobtobedone_dict = self.itwork_dict['jobtobedone']
    for ftag,datasize in self.jobtobedone_dict.items():
      if ftag in self.jobremaining:
        jobdonesize =  pre_jobtobedone_dict[ftag]*(1024**2) - self.jobremaining[ftag]
        self.jobremaining[ftag] = datasize*(1024**2) - jobdonesize #B
      else:
        self.jobremaining[ftag] = datasize*(1024**2) #B
      #
    #
    self.logger.debug('reinit_itjobdicts:: jobremaining=\n%s', pprint.pformat(self.jobremaining))
    
  def init_procsocks(self):
    for func in self.procsock_dict:
      sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      sock.connect(self.procsockpath_dict[func])
      self.procsock_dict[func] = sock
    #
    self.logger.debug('init_procsocks:: done')
  
  def listen_pipeserver(self):
    while 1:
      flag = self.flagq.get(True, None)
      self.logger.debug('listen_pipeserver:: popped flag=%s', flag)
      #flag can only be new itwork_dict
      self.itwork_dict = flag
      self.reinit_itjobdicts()
      self.logger.debug('listen_pipeserver:: NEW itwork_dict=%s\n', pprint.pformat(self.itwork_dict))
  
  def get_itfunclist_overnextchunk(self):
    def reorder(itfunc_list):
      ordered_list = []
      for func in self.idealfunc_order:
        if func in itfunc_list:
          ordered_list.append(func)
      #
      return ordered_list
    #
    itfunc_list = []
    uptoserved_size_B = self.served_size_B
    
    for ftag in self.jobtobedone_dict:
      if self.jobremaining[ftag] > 0:
        itfunc_list.append(ftag)
    #
    return reorder(itfunc_list)
  
  def canfunc_berun(self, func, uptofunc_list):
    try:
      if self.idealfunc_order.index(func) <= self.idealfunc_order.index(uptofunc_list[-1]):
        return False
    except ValueError:
      self.logger.error('A func which is not in idealfunc_order is found !.')
      return False
    #
    return True
      
  def run(self):
    t = threading.Thread(target=self.listen_pipeserver)
    t.start()
    #
    self.init_procsocks()
    self.startedtohandle_time = time.time()
    
    startrunround_time = time.time()
    runround_dur = 0
    totalrunround_dur = 0
    #
    while not self.stopflag:
      #wait for the proc turn
      stoken = self.stokenq.get(True, None)
      
      runround_dur = time.time()-startrunround_time
      self.logger.warning('run:: runround_dur=%s\n', runround_dur)
      totalrunround_dur += runround_dur
      startrunround_time = time.time()
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
      #
      (data, datasize, uptofunc_list) = self.pop_from_pipe()
      print 'uptofunc_list=%s' % uptofunc_list
      datasize_t = copy.copy(datasize)
      if data == None:
        if datasize == 0: #failed
          pass
        elif datasize == -1: #EOF
          self.logger.debug('run:: EOF! Aborting...')
          self.stopflag = True
        elif datasize == -2: #STOP
          self.logger.debug('run:: STOP! Aborting...')
          self.stopflag = True
        elif datasize == -3: #fatal
          self.logger.error('run:: FATAL! Aborting...')
          sys.exit(2)
      else:
        self.logger.debug('run:: datasize=%s popped.', datasize)
        self.active_last_time = time.time()
        #
        #self.logger.debug('run:: ready proc and forward datasize=%s', datasize)
        
        #print 'itwork_dict=%s' % pprint.pformat(self.itwork_dict)
        procstart_time = time.time()
        [datasize_, data_] = [0, None]
        
        for func in itfunc_list:
          if self.canfunc_berun(func, uptofunc_list):
            [datasize_, data_] = self.proc(func = func,
                                           datasize = datasize,
                                           data = data )
            self.jobremaining[func] -= datasize
            datasize = datasize_
            data = data_
        #
        #datasize = getsizeof(data)
        #self.forward_data(data, datasize)
        
        self.served_size_B += datasize_t
        #self.test_file.write(data)
        procdur = time.time() - procstart_time
        self.logger.debug('run:: acted on procdur=%s, datasize=%sB, datasize_=%sB, self.served_size_B=%s', procdur, datasize_t, datasize_, self.served_size_B)
        if procdur > self.intereq_time:
          self.logger.warning('run:: !!! procdur > intereq_time !!!')
    #
    self.test_file.close()
    self.sock.close()
    self.stoppedtohandle_time = time.time()
    self.logger.info('run:: done, dur=%ssecs, stoppedtohandle_time=%s, startedtohandle_time=%s', self.stoppedtohandle_time-self.startedtohandle_time, self.stoppedtohandle_time, self.startedtohandle_time)
    self.logger.debug('run:: totalrunround_dur=%s, jobremaining=\n%s', totalrunround_dur, pprint.pformat(self.jobremaining))
  
  def proc(self, func, datasize, data):
    data_ = None
    datasize_ = None
    #
    sock = self.procsock_dict[func]
    sock.sendall(data)
    self.logger.debug('proc:: wrote to %s_procsock, datasize=%s', func, datasize)
    
    data_ = ''
    readsize_ = self.procwrsize_dict[func]['rsize']
    readsize = 0
    while readsize < readsize_:
      readdata = sock.recv(readsize_)
      readsize += getsizeof(readdata)
      #self.logger.debug('proc:: readsize=%s', readsize)
      data_ += readdata
    
    datasize_ = readsize
    self.logger.debug('proc:: read from %s_procsock, datasize=%s', func, datasize_)
    
    self.logger.debug('proc:: %s run on datasize=%s, datasize_=%s', func, datasize, datasize_)
    #
    return [datasize_, data_]
  
  def pop_from_pipe(self):
    """ returns:
    (data, datasize): success
    (None, 0): failed
    (None, -1): EOF
    (None, -2): STOP
    (None, -3): fatal failure
    """
    chunk = self.procq.get(True, None)
    chunksize = getsizeof(chunk)
    
    if chunksize == 3:
      if chunk == 'EOF':
        return (None, -1, None)
    elif chunksize == 0:
      return (None, -2, None)
    #
    uptofunc_list = None
    header = chunk[:CHUNKHSIZE]
    try:
      uptofunc_list = json.loads(header)
    except ValueError:
      pass
    #
    return (chunk, chunksize, uptofunc_list)
  
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
func_comp_dict = {'f0':0.5,
                  'f1':1,
                  'f2':2,
                  'f3':3,
                  'f4':4,
                  'fft':5,
                  'upsample':8,
                  'plot':8,
                  'upsampleplot':75 }

def proc_time_model(datasize, func_n_dict, proc_cap):
  pm = 0
  for func,n in func_n_dict.items():
    pm += func_comp_dict[func]*float(n)
  #
  proc_t = float(8*float(datasize))*pm*float(1/float(proc_cap)) #secs
  
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
    self.sflagq_topipes_dict = {}
    self.sflagq_frompipes_dict = {}
    self.stokenq_dict = {}
    #
    self.logger.info('%s is ready...', self.nodename)

  ###  handle dts_comm  ###
  def _handle_recvfromdts(self, msg):
    [type_, data_] = msg
    if type_ == 'itjob_rule':
      self.welcome_s(data_)
    elif type_ == 'reitjob_rule':
      self.rewelcome_s(data_)
    #
  ###
  
  def rewelcome_s(self, data_):
    stpdst = int(data_['s_tp'])
    del data_['s_tp']
    if not stpdst in self.sinfo_dict:
      self.logger.error('Recved reitjob_rule msg for a nonreged stpdst=%s', stpdst)
      return
    #
    del data_['data_to_ip']
    del data_['proto']
    del data_['proc']
    
    uptojobdone = {}
    for ftag,n in data_['uptoitfunc_dict'].items():
      uptojobdone[ftag] = data_['datasize']*float(n)
    data_.update( {'uptojobdone': uptojobdone} )
    
    jobtobedone = {}
    for ftag,n in data_['itfunc_dict'].items():
      jobtobedone[ftag] = data_['datasize']*float(n)
    data_.update( {'jobtobedone': jobtobedone} )
    #
    self.sflagq_topipes_dict[stpdst].put(data_)
    self.logger.debug('rewelcome_s:: done for stpdst=%s', stpdst)
    
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
  
  def welcome_s(self, data_):
    #If new_s with same tpdst arrives, old_s is overwritten by new_s
    stpdst = int(data_['s_tp'])
    if stpdst in self.sinfo_dict:
      self.bye_s(stpdst)
    del data_['s_tp']
    #
    to_ip = data_['data_to_ip']
    del data_['data_to_ip']
    
    to_addr = (to_ip, stpdst) #goes into s_info_dict
    datasize = float(data_['datasize'])
    #
    jobtobedone = {}
    for ftag,n in data_['itfunc_dict'].items():
      jobtobedone[ftag] = datasize*float(n)
    data_.update( {'jobtobedone': jobtobedone} )
    #
    proc_cap = float(data_['proc'])
    del data_['proc']
    modelproct = proc_time_model(datasize = datasize,
                                 func_n_dict = data_['itfunc_dict'],
                                 proc_cap = proc_cap )
    #
    proto = int(data_['proto']) #6:TCP, 17:UDP
    del data_['proto']
    #
    sflagq_topipes = Queue.Queue(0)
    sflagq_frompipes = Queue.Queue(0)
    stokenq = Queue.Queue(1)
    self.sflagq_topipes_dict[stpdst] = sflagq_topipes
    self.sflagq_frompipes_dict[stpdst] = sflagq_frompipes
    self.stokenq_dict[stpdst] = stokenq
    #
    nchunks = datasize*(1024**2)/CHUNKSIZE
    intereq_time = 0 #(modelproct/nchunks)*0.95
    #self.logger.warning('welcome_s:: nchunks=%s, intereq_time=%s, nchunks*intereq_time=%s', nchunks, intereq_time, nchunks*intereq_time)
    threading.Thread(target = self.manage_stokenq,
                     kwargs = {'stpdst':stpdst,
                               'intereq_time':intereq_time } ).start()
    #
    if self.trans_type == 'file':
      s_server_thread = PipeServer(server_addr = (self.tl_ip, stpdst),
                                   itwork_dict = data_,
                                   to_addr = to_addr,
                                   sflagq_in = sflagq_topipes,
                                   sflagq_out = sflagq_frompipes,
                                   stokenq = stokenq,
                                   intereq_time = intereq_time )
      self.sinfo_dict[stpdst] = {'itjobrule':data_,
                                 'to_addr': to_addr,
                                 's_server_thread': s_server_thread,
                                 'modelproct': modelproct,
                                 'proc': proc_cap,
                                 'intereq_time': intereq_time }
      s_server_thread.start()
      self.N += 1
    else:
      self.logger.error('Unexpected trans_type=%s', self.trans_type)
    #
    self.logger.info('welcome_s:: welcome stpdst=%s, s_info=\n%s', stpdst, pprint.pformat(self.sinfo_dict[stpdst]) )
  
  def bye_s(self, stpdst):
    self.sflagq_topipes_dict[stpdst].put('STOP')
    self.N -= 1
    del self.sinfo_dict[stpdst]
    self.logger.info('bye s; tpdst=%s', stpdst)
  
  def signal_handler(self, signal, frame):
    self.logger.info('signal_handler:: ctrl+c !')
    self.shutdown()
  
  def shutdown(self):
    self.stopflag = True
    #
    for stpdst,sflagq in self.sflagq_topipes_dict.items():
      sflagq.put('STOP')
    #
    self.itrdts_intf.close()
    self.logger.debug('shutdown:: shutdown.')
    sys.exit(0)
  
  def test(self):
    self.logger.debug('test')
    
    nimg = 100000
    imgsize = CHUNKSIZE/10
    datasize = float(imgsize*nimg)/(1024**2)
    #
    data = {'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': datasize,
            'itfunc_dict': {'fft': 1.0},
            'uptoitfunc_dict': {},
            'proc': 1.0,
            's_tp': 6000 }
    self.welcome_s(data.copy())
    '''
    data_ = {'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': datasize,
            'itfunc_dict': {'fft': 1.0, 'upsampleplot':0.1},
            'uptoitfunc_dict': {},
            'proc': 1.0,
            's_tp': 6000 }
    time.sleep(10)
    self.rewelcome_s(data_.copy())
    '''
    '''
    data = {'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': datasize,
            'itfunc_dict': {'upsampleplot': 1.0},
            'uptoitfunc_dict': {},
            'proc': 1.0,
            's_tp': 6001 }
    self.welcome_s(data)
    '''

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
  
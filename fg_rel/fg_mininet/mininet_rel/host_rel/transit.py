#!/usr/bin/python

import sys,getopt,commands,pprint,mmap,logging,os,Queue,errno,signal,copy,json,subprocess
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
CHUNKSTRSIZE = CHUNKSIZE+CHUNKHSIZE

BWREGCONST = 1 #0.95 #0.9
TXINTEREQTIME_REGCONST = 0.98 #1
PROCINTEREQTIME_REGCONST = 0.98

class PipeServer(threading.Thread):
  def __init__(self, nodename, server_addr, itwork_dict, to_addr, sflagq_in, sflagq_out, sproctokenq, stxtokenq, procintereq_time):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.nodename = nodename,
    self.server_addr = server_addr
    self.stpdst = int(self.server_addr[1])
    self.itwork_dict = itwork_dict
    self.to_addr = to_addr
    self.sflagq_in = sflagq_in
    self.sflagq_out = sflagq_out
    self.sproctokenq = sproctokenq
    self.stxtokenq = stxtokenq
    self.procintereq_time = procintereq_time
    #
    self.logger = logging.getLogger('filepipeserver')
    #
    self.pipefileurl_q = Queue.Queue(0)
    self.flagq_toitsh = Queue.Queue(1)
    self.flagq_fromitsh = Queue.Queue(1)
    self.flagq_tosh = Queue.Queue(1)
    self.flagq_fromsh = Queue.Queue(1)
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
          self.flagq_toitsh.put(self.itwork_dict)
        #
        #self.logger.debug('listen_transit:: NEW itwork_dict=%s', self.itwork_dict)
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
    
    self.itserv_handler = ItServHandler(nodename = self.nodename,
                                        itwork_dict = self.itwork_dict,
                                        stpdst = self.stpdst,
                                        to_addr = self.to_addr,
                                        flagq_in = self.flagq_toitsh,
                                        flagq_out = self.flagq_fromitsh,
                                        sproctokenq = self.sproctokenq,
                                        stxtokenq = self.stxtokenq,
                                        procintereq_time = self.procintereq_time,
                                        procq = procq )
    self.itserv_handler.start()
    
    self.sc_handler = SessionClientHandler((sclient_sock,sclient_addr),
                                           itwork_dict = self.itwork_dict,
                                           to_addr = self.to_addr,
                                           stpdst = self.stpdst,
                                           flagq_in = self.flagq_tosh,
                                           flagq_out = self.flagq_fromsh,
                                           procq = procq )
    self.sc_handler.start()
    #
    self.logger.debug('run:: server_addr=%s started.', self.server_addr)
    #wait for session to end
    popped_fromsh = self.flagq_fromsh.get(True, None)
    popped_fromitsh = self.flagq_fromitsh.get(True, None)
    if popped_fromsh == 'DONE' and popped_fromitsh == 'DONE':
      self.sflagq_out.put('DONE')
    else:
      self.logger.error('Unexpected flag popped from sh=%s, itsh=%s', popped_fromsh, popped_fromitsh)
    #
    self.logger.info('run:: done.')
  
  def shutdown(self):
    #
    self.server_sock.shutdown(socket.SHUT_RDWR)
    self.server_sock.close()
    #close sc_handler
    self.flagq_tosh.put('STOP')
    #close itserv_handler
    self.pipefileurl_q.put('EOF')
    #
    self.logger.info('shutdown.')

class SessionClientHandler(threading.Thread):
  def __init__(self,(sclient_sock,sclient_addr), itwork_dict, to_addr, stpdst,
               flagq_in, flagq_out, procq ):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.sclient_sock = sclient_sock
    self.sclient_addr = sclient_addr
    self.stpdst = stpdst
    self.flagq_in = flagq_in
    self.flagq_out = flagq_out
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
    
    popped = self.flagq_in.get(True, None)
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
    self.logger.info('run:: done. \n\tin dur=%ssecs, at t=%s;', self.stoppedtorx_time-self.startedtorx_time, self.stoppedtorx_time)
    self.flagq_out.put('DONE')
  
  def init_rx(self):
    while 1:
      data = self.sclient_sock.recv(CHUNKSTRSIZE)
      datasize = getsizeof(data)
      self.logger.debug('init_rx:: stpdst=%s; rxed datasize=%sB', self.stpdst, datasize)
      #
      if self.startedtorx_time == None:
        self.startedtorx_time = time.time()
      #
      return_ = self.push_to_pipe(data)
      if return_ == 0: #failed
        self.logger.error('init_rx:: push_to_pipe for datasize=%s failed. Aborting...', datasize)
        sys.exit(2)
      elif return_ == -1: #EOF
        self.logger.info('init_rx:: EOF is rxed...')
        self.flagq_in.put('EOF')
        break
      elif return_ == -2: #datasize=0
        self.logger.info('init_rx:: datasize=0 is rxed...')
        self.flagq_in.put('STOP')
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
    overflow_size = chunksize - CHUNKSTRSIZE
    if overflow_size == 0:
      self.procq.put(self.chunk)
      self.logger.debug('push_to_pipe:: pushed; chunksize=%s', chunksize)
      self.chunk = ''
      return 1
    elif overflow_size < 0:
      return 1
    #
    else: #overflow
      chunksize_ = chunksize-overflow_size
      overflow = self.chunk[chunksize_:]
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
  def __init__(self, nodename, itwork_dict, stpdst, to_addr,
               flagq_in, flagq_out, sproctokenq, stxtokenq, procintereq_time, procq):
    threading.Thread.__init__(self)
    self.setDaemon(True)
    #
    self.nodename = nodename
    self.itwork_dict = itwork_dict
    self.stpdst = stpdst
    self.to_addr = to_addr
    self.flagq_in = flagq_in
    self.flagq_out = flagq_out
    self.sproctokenq = sproctokenq
    self.stxtokenq = stxtokenq
    self.procintereq_time = procintereq_time
    self.procq = procq
    #
    self.logger = logging.getLogger('itservhandler_%s' % self.stpdst)
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
    self.procsockpath_dict = {'fft': '/tmp/fft',
                              'upsampleplot': '/tmp/upsampleplot' }
    self.procwrsize_dict = {'fft': {'wsize': CHUNKSIZE,
                                    'rsize': CHUNKSIZE },
                            'upsampleplot': {'wsize': CHUNKSIZE,
                                             'rsize': CHUNKSIZE }
                           }
    #
    self.jobtobedone_dict = None
    self.uptorecvsize_dict = {}
    self.jobremaining = {}
    self.forwardq = Queue.Queue(0)
    
    self.init_itjobdicts()
    
    self.procingdone = False
    
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
    
  def init_eceiproc(self):
    if self.nodename[0] == 't':
      subprocess.call(['./eceiproc2', '--stpdst=%s' % self.stpdst ])
    else:
      subprocess.call(['./eceiproc2', '--stpdst=%s' % str(int(self.stpdst)-6000) ])
      #subprocess.call(['./eceiproc2', '--stpdst=%s' % self.stpdst, '--loc=mininet',
      #                 '>', 'logs/eceproc%s.log' % self.stpdst ])
    #
  
  def init_procsocks(self):
    self.logger.info('init_procsocks:: inited')
    for func in self.procsock_dict:
      while 1:
        try:
          sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
          sock.connect(self.procsockpath_dict[func]+str(int(self.stpdst)-6000))
          self.procsock_dict[func] = sock
        except:
          continue
        #
        break
      #
    #
    self.logger.info('init_procsocks:: done')
  
  def listen_pipeserver(self):
    while 1:
      flag = self.flagq_in.get(True, None)
      self.logger.debug('listen_pipeserver:: popped flag=%s', flag)
      #flag can only be new itwork_dict
      self.itwork_dict = flag
      #self.reinit_itjobdicts()
      dict_ = {ftag:datasize-float(float(self.jobremaining[ftag])/(1024**2)) for ftag,datasize in self.jobtobedone_dict.items()}
      self.logger.info('>>> jobdone_dict=\n%s', pprint.pformat(dict_))
      self.init_itjobdicts()
      
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
    
    for ftag in self.jobtobedone_dict:
      if self.jobremaining[ftag] > 0:
        itfunc_list.append(ftag)
    #
    return reorder(itfunc_list)
  
  def canfunc_berun(self, func, uptofunc_list):
    if len(uptofunc_list) == 0:
      if self.idealfunc_order.index(func) == 0:
        return True
      else:
        return False
      #
    try:
      if self.idealfunc_order.index(func) <= self.idealfunc_order.index(uptofunc_list[-1]):
        return False
    except ValueError:
      self.logger.error('A func which is not in idealfunc_order is found !.')
      return False
    #
    return True
  
  def run(self):
    threading.Thread(target=self.listen_pipeserver).start()
    #
    threading.Thread(target = self.forward_thread).start()
    #
    #threading.Thread(target=self.init_eceiproc).start()
    #self.init_procsocks()
    #
    self.startedtohandle_time = time.time()
    
    startrunround_time = time.time()
    runround_dur = 0
    totalrunround_dur = 0
    totalexcessrunround_dur = 0
    #
    data = None
    itfunc_list = None
    while not self.stopflag:
      runround_dur = time.time()-startrunround_time
      if runround_dur > self.procintereq_time:
        self.logger.debug('run:: *** runround_dur > procintereq_time = %s ***', self.procintereq_time)
        totalexcessrunround_dur += runround_dur-self.procintereq_time
      #
      self.logger.debug('run:: runround_dur=%s\n', runround_dur)
      totalrunround_dur += runround_dur
      startrunround_time = time.time()
      #
      (data, datasize, uptofunc_list) = self.pop_from_pipe()
      datasize_t = copy.copy(datasize)
      self.active_last_time = time.time()
      
      if data == None:
        if datasize == 0: #failed
          pass
        elif datasize == -1: #EOF
          if not self.nodename[0] == 't':
            #self.forward_data(data = 'EOF',
            #                  datasize = 3 )
            self.forwardq.put('EOF')
          #
          self.logger.debug('run:: EOF is rxed and forwarded! Aborting...')
          self.stopflag = True
        elif datasize == -2: #STOP
          self.logger.debug('run:: STOP! Aborting...')
          self.forwardq.put('STOP')
          self.stopflag = True
        elif datasize == -3: #fatal
          self.logger.error('run:: FATAL! Aborting...')
          sys.exit(2)
      else:
        itfunc_list = self.get_itfunclist_overnextchunk()
        #print 'itfunc_list=%s' % pprint.pformat(itfunc_list)
        self.logger.debug('run:: datasize=%s popped. uptofunc_list=%s', datasize, uptofunc_list)
        if len(itfunc_list) == 0:
          if (not self.nodename[0] == 't'):
            #self.forward_data(data = self.addheader(data, itfunc_list),
            #                  datasize = getsizeof(data) )
            self.forwardq.put( self.addheader(data, itfunc_list) )
            if not self.procingdone:
              self.procingdone = True
              self.logger.debug('run:: procing done, dur=%s', time.time()-self.startedtohandle_time)
            #
          #
        else:
          #wait for the proc turn
          stoken = self.sproctokenq.get(True, None)
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
          #self.logger.debug('run:: ready proc and forward datasize=%s', datasize)
          procstart_time = time.time()
          [datasize_, data_] = [0, None]
          
          for func in itfunc_list:
            if self.canfunc_berun(func, uptofunc_list):
              '''
              [datasize_, data_] = self.proc(func = func,
                                             datasize = datasize,
                                             data = data )
              '''
              self.jobremaining[func] -= datasize
              #datasize = datasize_
              #data = data_
              uptofunc_list.append(func)
          #
          self.served_size_B += datasize_t
          #self.test_file.write(data)
          procdur = time.time() - procstart_time
          self.logger.info('run:: acted on procdur=%s, datasize=%sB, datasize_=%sB, self.served_size_B=%s', procdur, datasize_t, datasize_, self.served_size_B)
          if procdur > self.procintereq_time:
            self.logger.debug('run:: !!! procdur > procintereq_time !!!')
          #
          if (not self.nodename[0] == 't'):
            #self.forward_data(data = self.addheader(data, uptofunc_list),
            #                  datasize = getsizeof(data) )
            self.forwardq.put( self.addheader(data, uptofunc_list) )
          #
        #
    #
    self.test_file.close()
    #
    #self.sock.close()
    #self.flagq_out.put('DONE')
    #
    self.stoppedtohandle_time = time.time()
    self.logger.info('run:: done, dur=%ssecs, stoppedtohandle_time=%s, startedtohandle_time=%s', self.stoppedtohandle_time-self.startedtohandle_time, self.stoppedtohandle_time, self.startedtohandle_time)
    self.logger.info('run:: totalrunround_dur=%s, served_size_B=%s(MB), jobremaining=\n%s', totalrunround_dur, float(self.served_size_B)/(1024**2), pprint.pformat(self.jobremaining))
    self.logger.info('run:: totalexcessrunround_dur=%s', totalexcessrunround_dur)
  
  def addheader(self, data, itfunc_list):
    #add itfunc_list as header
    header = json.dumps(itfunc_list)
    padding_length = CHUNKHSIZE - len(header)
    header += ' '*padding_length
    data = header+data
    #
    return data
  
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
      self.logger.debug('proc:: readsize=%s', readsize)
      data_ += readdata
    
    datasize_ = readsize
    self.logger.debug('proc:: read from %s_procsock, datasize=%s', func, datasize_)
    
    self.logger.debug('proc:: %s run on datasize=%s, datasize_=%s', func, datasize, datasize_)
    #
    return [datasize_, data_]
  
  def forward_thread(self):
    self.logger.info('forward_thread:: inited')
    while 1:
      data = self.forwardq.get(True, None)
      datasize = getsizeof(data)
      self.forward_data(data = data, datasize = datasize)
      if datasize == 3 and data == 'EOF':
        self.logger.info('forward_thread:: forwarded EOF. done. dur=%s', time.time()-self.startedtohandle_time)
        break
      elif datasize == 4 and data == 'STOP':
        self.logger.info('forward_thread:: stopped with flag STOP! done.')
        break
      #
    #
    self.sock.close()
    self.flagq_out.put('DONE')
  
  def forward_data(self, data, datasize):
    #wait for the tx turn
    stoken = self.stxtokenq.get(True, None)
    if stoken == CHUNKSIZE:
      pass
    elif stoken == -1:
      self.logger.error('forward_data:: interrupted with txtoken=-1.')
      return
    else:
      self.logger.error('forward_data:: Unexpected stoken=%s', stoken)
      return
    #
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
        self.logger.error('forward_data:: errno is %d', e[0])
        if e[0] == errno.EPIPE:
          # remote peer disconnected
          self.logger.error('forward_data:: Detected remote disconnect')
        else:
          # determine and handle different error
          pass
      else:
        self.logger.error('forward_data:: socket error=%s', e)
    #
  
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
    chunk = chunk[CHUNKHSIZE:]
    
    return (chunk, chunksize-CHUNKHSIZE, uptofunc_list)
  
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
  def __init__(self, nodename, intf, htbdir, tl_ip, tl_port, dtsl_ip, dtsl_port, trans_type, logger):
    if not (trans_type == 'file' or trans_type == 'console'):
      self.logger.error('Unexpected trans_type=%s', trans_type)
    self.trans_type = trans_type
    #
    self.nodename = nodename
    self.intf = intf
    self.htbdir = htbdir
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
    self.stxtokenq_dict = {}
    self.sproctokenq_dict = {}
    
    self.stpdst_procintereqtime_dict = {}
    self.stpdst_txintereqtime_dict = {}
    self.stpdst_itwork_dict = {}
    #
    #self.init_htbdir()
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
    proc_cap = float(data_['proc'])
    datasize_ = float(data_['datasize'])
    func_n_dict = data_['itfunc_dict']
    #
    bw = float(data_['bw'])
    modeltxt = float(datasize_*8)/(bw*BWREGCONST)
    nchunks = float(datasize_*(1024**2))/CHUNKSTRSIZE
    self.stpdst_txintereqtime_dict[stpdst] = TXINTEREQTIME_REGCONST*float(float(modeltxt)/nchunks)
    self.logger.debug('rewelcome_s:: datasize_=%s, modeltxt=%s', datasize_, modeltxt)
    #self.reinit_htbconf(bw, stpdst)
    #
    jobtobedone = {}
    for ftag,n in func_n_dict.items():
      jobtobedone[ftag] = datasize_*float(n)
    data_.update( {'jobtobedone': jobtobedone} )
    #
    tobeproced_modelproct = proc_time_model(datasize = datasize_,
                                 func_n_dict = func_n_dict,
                                 proc_cap = proc_cap )
    tobeproced_datasize = float(datasize_)*max([float(n) for func,n in func_n_dict.items()])
    tobeproceddata_modeltxt = float(tobeproced_datasize*8)/(bw*BWREGCONST)
    tobeproceddata_modeltranst = tobeproced_modelproct+tobeproceddata_modeltxt
    nchunkstobeproced = tobeproced_datasize*(1024**2)/CHUNKSTRSIZE
    self.stpdst_procintereqtime_dict[stpdst] = PROCINTEREQTIME_REGCONST*float(float(tobeproceddata_modeltranst)/nchunkstobeproced)
    #
    self.sflagq_topipes_dict[stpdst].put(data_)
    self.logger.debug('rewelcome_s:: done for stpdst=%s;\n\ttobeproced_datasize=%s, tobeproceddata_modeltranst=%s, tobeproced_modelproct=%s, tobeproceddata_modeltxt=%s', stpdst, tobeproced_datasize, tobeproceddata_modeltranst, tobeproced_modelproct, tobeproceddata_modeltxt)
    
  def welcome_s(self, data_):
    #If new_s with same tpdst arrives, old_s is overwritten by new_s
    stpdst = int(data_['s_tp'])
    if stpdst in self.sinfo_dict:
      self.bye_s(stpdst)
    del data_['s_tp']
    #
    to_ip = data_['data_to_ip']
    del data_['data_to_ip']
    proc_cap = float(data_['proc'])
    del data_['proc']
    func_n_dict = data_['itfunc_dict']
    proto = int(data_['proto']) #6:TCP, 17:UDP
    del data_['proto']
    to_addr = (to_ip, stpdst) #goes into s_info_dict
    datasize = float(data_['datasize'])
    #
    bw = float(data_['bw'])
    modeltxt = float(datasize*8)/(bw*BWREGCONST)
    nchunks = float(datasize*(1024**2))/CHUNKSTRSIZE
    self.stpdst_txintereqtime_dict[stpdst] = TXINTEREQTIME_REGCONST*float(float(modeltxt)/nchunks)
    
    stxtokenq = Queue.Queue(1)
    self.stxtokenq_dict[stpdst] = stxtokenq
    threading.Thread(target = self.manage_stxtokenq,
                     kwargs = {'stpdst':stpdst } ).start()
    self.logger.debug('welcome_s:: datasize=%s, modeltxt=%s', datasize, modeltxt)
    #self.init_htbconf(bw, stpdst)
    #
    jobtobedone = {}
    for ftag,n in data_['itfunc_dict'].items():
      jobtobedone[ftag] = datasize*float(n)
    data_.update( {'jobtobedone': jobtobedone} )
    #
    sflagq_topipes = Queue.Queue(0)
    sflagq_frompipes = Queue.Queue(0)
    sproctokenq = Queue.Queue(1)
    self.sflagq_topipes_dict[stpdst] = sflagq_topipes
    self.sflagq_frompipes_dict[stpdst] = sflagq_frompipes
    self.sproctokenq_dict[stpdst] = sproctokenq
    #
    tobeproced_modelproct = proc_time_model(datasize = datasize,
                                 func_n_dict = func_n_dict,
                                 proc_cap = proc_cap )
    tobeproced_datasize = float(datasize)*max([float(n) for func,n in func_n_dict.items()])
    tobeproceddata_modeltxt = float(tobeproced_datasize*8)/(bw*BWREGCONST)
    nchunkstobeproced = float(tobeproced_datasize*(1024**2))/CHUNKSTRSIZE
    tobeproceddata_modeltranst = tobeproced_modelproct+tobeproceddata_modeltxt
    
    self.stpdst_procintereqtime_dict[stpdst] = PROCINTEREQTIME_REGCONST*float(float(tobeproceddata_modeltranst)/nchunkstobeproced)
    threading.Thread(target = self.manage_sproctokenq,
                     kwargs = {'stpdst':stpdst } ).start()
    self.logger.debug('welcome_s:: tobeproced_datasize=%s, tobeproceddata_modeltranst=%s, tobeproced_modelproct=%s, tobeproceddata_modeltxt=%s', tobeproced_datasize, tobeproceddata_modeltranst, tobeproced_modelproct, tobeproceddata_modeltxt)
    self.logger.debug('welcome_s::\n stpdst_txintereqtime_dict=%s,\n stpdst_procintereqtime_dict=%s', pprint.pformat(self.stpdst_txintereqtime_dict), pprint.pformat(self.stpdst_procintereqtime_dict))
    #
    #self.stpdst_itwork_dict[stpdst] = data_
    #self.logger.debug('stpdst_itwork_dict=%s', pprint.pformat(self.stpdst_itwork_dict))
    if self.trans_type == 'file':
      s_server_thread = PipeServer(nodename = self.nodename,
                                   server_addr = (self.tl_ip, stpdst),
                                   itwork_dict = data_,
                                   to_addr = to_addr,
                                   sflagq_in = sflagq_topipes,
                                   sflagq_out = sflagq_frompipes,
                                   sproctokenq = sproctokenq,
                                   stxtokenq = stxtokenq,
                                   procintereq_time = self.stpdst_procintereqtime_dict[stpdst] )
      self.sinfo_dict[stpdst] = {'itjobrule':data_,
                                 'to_addr': to_addr,
                                 's_server_thread': s_server_thread,
                                 'tobeproced_modelproct': tobeproced_modelproct,
                                 'proc': proc_cap }
      s_server_thread.start()
      self.N += 1
    else:
      self.logger.error('Unexpected trans_type=%s', self.trans_type)
    #
    self.logger.info('welcome_s:: welcome stpdst=%s, s_info=\n%s', stpdst, pprint.pformat(self.sinfo_dict[stpdst]) )
    threading.Thread(target = self.waitforsession_toend,
                     kwargs = {'stpdst': stpdst} ).start()
  
  def waitforsession_toend(self, stpdst):
    sflagq_frompipe = self.sflagq_frompipes_dict[stpdst]
    popped = sflagq_frompipe.get(True, None)
    if popped == 'DONE':
      #clear htb for the session
      #self.run_htbinit('dconf')
      #self.delete_htbfile(stpdst)
      #self.run_htbinit('conf')
      #self.run_htbinit('show')
      self.sproctokenq_dict[stpdst].put(-1, True)
      self.stxtokenq_dict[stpdst].put(-1, True)
      self.logger.info('waitforsession_toend:: done for stpdst=%s', stpdst)
    else:
      self.logger.error('waitforsession_toend:: Unexpected popped=%s', popped)
    #
  
  def manage_stxtokenq(self, stpdst):
    stxtokenq = self.stxtokenq_dict[stpdst]
    while not self.stopflag:
      try:
        stxtokenq.put(CHUNKSIZE, False)
      except Queue.Full:
        pass
      #self.logger.debug('manage_stxtokenq_%s:: sleeping for %ssecs', stpdst, self.stpdst_procintereqtime_dict[stpdst])
      time.sleep(self.stpdst_txintereqtime_dict[stpdst])
    #
    self.logger.debug('manage_stxtokenq_%s:: stoppped by STOP flag!', stpdst)
  
  def manage_sproctokenq(self, stpdst):
    sproctokenq = self.sproctokenq_dict[stpdst]
    while not self.stopflag:
      try:
        sproctokenq.put(CHUNKSIZE, False)
      except Queue.Full:
        pass
      #self.logger.debug('manage_sproctokenq_%s:: sleeping for %ssecs', stpdst, self.stpdst_procintereqtime_dict[stpdst])
      time.sleep(self.stpdst_procintereqtime_dict[stpdst])
    #
    self.logger.debug('manage_sproctokenq_%s:: stoppped by STOP flag!', stpdst)

  ###  htb rel  ###
  def delete_htbfile(self, stpdst):
    fname = '%s-1:%s.%s' % (self.intf, 10+int(stpdst)-6000, stpdst)
    furl = '%s/%s/%s' % (self.htbdir,self.intf,fname)
    self.delete_file(furl)
  
  def delete_file(self, furl):
    try:
      if os.path.isfile(furl):
        os.unlink(furl)
        self.logger.debug('delete_file:: furl=%s is deleted', furl)
      #
    except Exception, e:
      self.logger.error('delete_file:: %s', e)
    #
  
  def init_htbdir(self):
    dir_ = '%s/%s' % (self.htbdir, self.intf)
    #
    if not os.path.exists(dir_):
      os.makedirs(dir_)
      self.logger.debug('dir=%s is made', dir_)
    else:
      self.clean_dir(dir_)
    #
    #for htb.init.sh - need to put filename=self.intf EVEN IF IT IS EMPTY.
    #(opt: DEFAULT=0 to make unclassified traffic performance as high as possible)
    self.write_to_htbfile(self.intf,'DEFAULT=0')
  
  def clean_dir(self, dir_):
    for f in os.listdir(dir_):
      furl = os.path.join(dir_, f)
      self.delete_file(furl)
    #
  
  def write_to_htbfile(self, filename, data):
    f = open( '%s/%s/%s' % (self.htbdir,self.intf,filename), 'w')
    f.write(data)
    f.close()
    self.logger.debug('data=\n%s\nis written to filename=%s',data,filename)
  
  def clear_htbconf(self):
    self.logger.info('clear_htbconf:: started;')
    self.run_htbinit('dconf')
    self.run_htbinit('show')
    self.logger.info('clear_htbconf::done.')
  
  def reinit_htbconf(self, bw, stpdst):
    self.logger.info('reinit_htbconf:: started;')
    self.run_htbinit('dconf')
    self.delete_htbfile(stpdst)
    #
    data = self.get_htbclass_confdata(rate = '%sMbit' % bw,
                                      burst = '15k',
                                      leaf = 'netem',
                                      rule = '*:%s' % stpdst )
    filename = '%s-1:%s.%s' % (self.intf, 10+int(stpdst)-6000, stpdst)
    self.write_to_htbfile(filename, data)
    #
    self.run_htbinit('conf')
    #
    self.logger.info('reinit_htbconf:: done.')
  
  def init_htbconf(self, bw, stpdst):
    self.logger.info('init_htbconf:: started;')
    self.run_htbinit('dconf')
    #
    data = self.get_htbclass_confdata(rate = '%sMbit' % bw,
                                      burst = '15k',
                                      leaf = 'netem',
                                      rule = '*:%s' % stpdst )
    filename = '%s-1:%s.%s' % (self.intf, 10+int(stpdst)-6000, stpdst)
    self.write_to_htbfile(filename, data)
    #
    self.run_htbinit('conf')
    #
    self.logger.info('init_htbconf:: done.')
  
  def get_htbclass_confdata(self, rate, burst, leaf, rule):
    #print 'rate=%s, rule=%s' % (rate, rule)
    return 'RATE=%s\nBURST=%s\nLEAF=%s\nRULE=%s' % (rate,burst,leaf,rule)

  def run_htbinit(self, command):
    cli_o = None
    if command == 'conf':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),
                                         'start','invalidate',
                                         self.intf, self.htbdir, 'not_add_root' ] )
      except subprocess.CalledProcessError as e:
        self.logger.error('###CONF_ERR=%s', e.output)
    elif command == 'dconf':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),
                                         'minstop','...',
                                         self.intf, self.htbdir ] )
      except subprocess.CalledProcessError as e:
        self.logger.error('###DCONF_ERR=%s', e.output)
    elif command == 'show':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'run.sh'),'show','p'] )
        #cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),'stats'] )
      except subprocess.CalledProcessError as e:
        self.logger.error('###SHOW_ERR=%s', e.output)
    else:
      self.logger.error('unknown command=%s',command)
      return
    #
    #self.logger.info('\n----------------------------------------------------------')
    #self.logger.info('%s_output:\n%s',command,cli_o)
  ###
  
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
    
    datasize = 20 #MB
    #imgsize = CHUNKSIZE/10
    #nimg = datasize*(1024**2)/float(imgsize)
    #
    data = {'proto': 6,
            'data_to_ip': u'10.0.1.0',
            'datasize': datasize,
            'itfunc_dict': {'fft': 1 },
            'uptoitfunc_dict': {},
            'proc': 50.0,
            's_tp': 6000,
            'bw': 3 }
    self.welcome_s(data.copy())
    '''
    data_ = {'proto': 6,
            'data_to_ip': u'10.0.0.1',
            'datasize': datasize,
            'itfunc_dict': {'fft': 0.5, 'upsampleplot':0.05},
            'uptoitfunc_dict': {},
            'proc': 1.0,
            's_tp': 6000 }
    time.sleep(10)
    self.rewelcome_s(data_.copy())
    '''
    
    data = {'proto': 6,
            'data_to_ip': u'10.0.1.1',
            'datasize': datasize,
            'itfunc_dict': {'fft': 1},
            'uptoitfunc_dict': {},
            'proc': 50.0,
            's_tp': 6001,
            'bw': 3 }
    self.welcome_s(data.copy())
    
    data = {'proto': 6,
            'data_to_ip': u'10.0.1.2',
            'datasize': datasize,
            'itfunc_dict': {'fft': 0.5},
            'uptoitfunc_dict': {},
            'proc': 50.0,
            's_tp': 6002,
            'bw': 3 }
    self.welcome_s(data.copy())
    
def main(argv):
  nodename = intf = htbdir = dtsl_ip = dtsl_port= dtst_port = logto = trans_type = None
  try:
    opts, args = getopt.getopt(argv,'',['nodename=','intf=','htbdir=','dtsl_ip=','dtsl_port=','dtst_port=','logto=','trans_type='])
  except getopt.GetoptError:
    print 'transit.py --nodename=<> --intf=<> --dtsl_ip=<> --dtsl_port=<> --dtst_port=<> --logto=<> --trans_type=<>'
    sys.exit(2)
  #Initializing global variables with comman line options
  for opt, arg in opts:
    if opt == '--nodename':
      nodename = arg
    elif opt == '--intf':
      intf = arg
    elif opt == '--htbdir':
      htbdir = arg
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
    fname = 'logs/%s.log' % nodename
    logging.basicConfig(filename=fname,filemode='w',level=logging.DEBUG)
    #logging.basicConfig(filename=fname,filemode='w',level=logging.INFO)
  elif logto == 'console':
    logging.basicConfig(level=logging.DEBUG)
  else:
    raise CommandLineOptionError('Unexpected logto', logto)
  logger = logging.getLogger('t')
  #
  tl_ip = get_addr(intf)
  tr = Transit(nodename = nodename,
               intf = intf,
               htbdir = htbdir,
               tl_ip = tl_ip,
               tl_port = dtst_port,
               dtsl_ip = dtsl_ip,
               dtsl_port = dtsl_port,
               trans_type = trans_type,
               logger = logger )
  #
  if nodename == 't': # or nodename == 't11':
    tr.test()
    raw_input('Enter\n')
    tr.shutdown()
  else:
    time.sleep(100000)
    tr.shutdown()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

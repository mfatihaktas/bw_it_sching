#!/usr/bin/python
import sys,json,logging,subprocess,getopt,commands,pprint,os,Queue,threading,time
from errors import CommandLineOptionError
from userdts_comm_intf import UserDTSCommIntf
from sender import Sender

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

BWREGCONST = 1 #1.05
CHUNKSTRSIZE = 24*8*9*10 + 50
class Producer(object):
  def __init__(self, intf, dtst_port, dtsl_ip, dtsl_port, cl_ip, proto,tx_type, file_url, kstardata_url,
               req_dict,app_pref_dict, htbdir, logto):
    self.logto = logto
    self.intf = intf
    self.pl_ip = get_addr(intf)
    self.dtst_port = dtst_port
    self.dtsl_ip = dtsl_ip
    self.dtsl_port = dtsl_port
    self.cl_ip = cl_ip
    self.proto = proto
    self.tx_type = tx_type
    self.file_url = file_url
    self.kstardata_url = kstardata_url
    self.req_dict = req_dict
    self.app_pref_dict = app_pref_dict
    self.htbdir = htbdir
    #for control state
    '''0:start, 1:joined to dts, 2:sch_reply is recved'''
    self.state = 0
    self.userdts_intf = UserDTSCommIntf(sctag = 'p-dts',
                                        user_addr = (self.pl_ip, self.dtst_port),
                                        dts_addr = (self.dtsl_ip, self.dtsl_port),
                                        _recv_callback = self._handle_recvfromdts )
    #for htb_queue conf - bw shaping
    self.ktif = 230 #kernel timer interrupt frequency (Hz)
    self.init_htbdir()
    #
    self.sinfo_dict = {}
    self.sender_thread = None
    self.qtosender = None
    self.qfromsender = None
    #
    self.joinreqsent_time = 0
    self.joinreplyrecved_time = 0
    self.schingreqsent_time = 0
    self.schingreplyrecved_time = 0
    #
    self.stpdst_txintereqtime_dict = {}
    self.stpdst_threadlock_dict = {}
    self.stpdst_txtokenq_dict = {}
    self.sdone_dict = {}
    self.stopflag = False
    
  ########################  _handle_***  ########################
  def welcome_s(self, sch_req_id, data_):
    if self.state != 2:
      logging.error('welcome_s:: unexpected cur_state=%s', self.state)
      return
    #
    datasize = float(self.req_dict['datasize'])
    bw = float(data_['bw'])
    stpdst = int(data_['tp_dst'])
    #
    modeltxt = float(datasize*8)/(bw*BWREGCONST)
    nchunks = float(datasize*(1024**2))/CHUNKSTRSIZE
    self.stpdst_txintereqtime_dict[stpdst] = float(float(modeltxt)/nchunks)
    
    stxtokenq = Queue.Queue(1)
    self.stpdst_txtokenq_dict[stpdst] = stxtokenq
    self.stpdst_threadlock_dict[stpdst] = threading.Lock()
    self.sdone_dict[stpdst] = False
    threading.Thread(target = self.manage_stxtokenq,
                     kwargs = {'stpdst': stpdst } ).start()
    logging.debug('welcome_s:: stpdst=%s, datasize=%s, bw=%s, modeltxt=%s', stpdst, datasize, bw, modeltxt)
    #self.init_htbconf(pl, p_bw, p_tp_dst)
    
    self.qtosender = Queue.Queue(0)
    self.qfromsender = Queue.Queue(0)
    
    to_addr = (self.cl_ip, stpdst)
    
    self.sender_thread = Sender(in_queue = self.qtosender,
                                out_queue = self.qfromsender,
                                txtokenq = stxtokenq,
                                dst_addr = to_addr,
                                proto = self.proto,
                                datasize = datasize,
                                tx_type = self.tx_type,
                                file_url = self.file_url,
                                logto = self.logto,
                                kstardata_url = self.kstardata_url )
    self.sender_thread.start()
    #
    self.sinfo_dict[sch_req_id] = {'qfromsender': self.qfromsender,
                                   'qtosender': self.qtosender,
                                   'stpdst': stpdst }
  
  def manage_stxtokenq(self, stpdst):
    self.stpdst_threadlock_dict[stpdst].acquire()
    stxtokenq = self.stpdst_txtokenq_dict[stpdst]
    self.stpdst_threadlock_dict[stpdst].release()
    while not self.sdone_dict[stpdst]:
      try:
        stxtokenq.put(CHUNKSTRSIZE, False)
      except Queue.Full:
        pass
      logging.debug('manage_stxtokenq_%s:: sleeping for %ssecs', stpdst, self.stpdst_txintereqtime_dict[stpdst])
      time.sleep(self.stpdst_txintereqtime_dict[stpdst])
    #
    logging.debug('manage_stxtokenq_%s:: stoppped by STOP flag!', stpdst)
  
  def waitfor_sessiontoend(self, sch_req_id):
    sinfo_dict = {'sch_req_id': sch_req_id}
    
    sinfo = self.sinfo_dict[sch_req_id]
    popped = sinfo['qfromsender'].get(True, None)
    sinfo_dict['sendstart_time'] = popped['sendstart_time']
    sinfo_dict['sendstop_time'] = popped['sendstop_time']
    sinfo_dict['sentsize'] = popped['sentsize']
    #
    self.sdone_dict[sinfo['stpdst']] = True
    self.sinfo_dict[sch_req_id]['sdone'] = True
    sinfo_dict['joinrr_time'] = self.joinreqsent_time - self.joinreplyrecved_time
    sinfo_dict['schingrr_time'] = self.schingreplyrecved_time - self.schingreqsent_time
    
    msg = {'type':'session_done',
           'data': sinfo_dict }
    self.userdts_intf.relsend_to_dts(msg)
    #
    #self.clear_htbconf()
    #self.init_htbdir()
  
  def _handle_recvfromdts(self, msg):
    [type_, data_] = msg
    if type_ == 'sching_reply':
      if self.state != 1:
        logging.error('_handle_recvfromdts:: sching_reply: unexpected cur_state= %s', self.state)
        return
      #
      if data_ != 'sorry':
        self.state = 2
        logging.info('_handle_recvfromdts:: sching_reply: successful sch_req :) data_=\n%s', pprint.pformat(data_))
        self.schingreplyrecved_time = time.time()
        
        sch_req_id = int(data_['sch_req_id'])
        del data_['sch_req_id']
        
        self.welcome_s(sch_req_id, data_)
        
        threading.Thread(target = self.waitfor_sessiontoend,
                         kwargs = {'sch_req_id': sch_req_id} ).start()
      else:
        logging.info('_handle_recvfromdts:: sching_reply: unsuccessful sch_req :( data_=%s', data_)
        return
    elif type_ == 'resching_reply':
      if self.state != 2:
        logging.error('_handle_recvfromdts:: resching_reply: unexpected cur_state=%s', self.state)
        return
      #
      logging.info('_handle_recvfromdts:: resching_reply: data_=\n%s', pprint.pformat(data_))
      #reinit htb
      bw = float(data_['bw'])
      datasize = float(data_['datasize'])
      stpdst = int(data_['tp_dst'])
      
      modeltxt = float(datasize*8)/(bw*BWREGCONST)
      nchunks = float(datasize*(1024**2))/CHUNKSTRSIZE
      
      self.stpdst_threadlock_dict[stpdst].acquire()
      self.stpdst_txintereqtime_dict[stpdst] = float(float(modeltxt)/nchunks)
      logging.info('_handle_recvfromdts:: resching_reply: self.stpdst_txintereqtime_dict[%s] changed to %s', stpdst, self.stpdst_txintereqtime_dict[stpdst])
      self.stpdst_threadlock_dict[stpdst].release()
      #self.init_htbconf(pl, p_bw, p_tp_dst)
      
    elif type_ == 'join_reply':
      if self.state != 0:
        logging.error('_handle_recvfromdts:: join_reply: unexpected cur_state=%s', self.state)
        return
      #
      if data_ == 'welcome':
        self.state = 1
        logging.info('_handle_recvfromdts:: join_reply: joined to dts :) data_=%s', data_)
        self.joinreplyrecved_time = time.time()
        self.send_sching_req()
      elif data_ == 'sorry':
        logging.info('_handle_recvfromdts:: join_reply: cannot join to dts :( data_=%s', data_)
  ########################  htb conf  ########################
  def init_htbdir(self):
    dir_ = '%s/%s' % (self.htbdir, self.intf)
    #
    if not os.path.exists(dir_):
      os.makedirs(dir_)
      logging.debug('dir=%s is made', dir_)
    else: #dir already exists, clean it
      self.clean_dir(dir_)
    #
    #for htb.init.sh - need to put filename=self.intf EVEN IF IT IS EMPTY.
    #(opt: DEFAULT=0 to make unclassified traffic performance as high as possible)
    self.write_to_htbfile(self.intf,'DEFAULT=0')
  
  def clean_dir(self, dir_):
    for f in os.listdir(dir_):
      f_path = os.path.join(dir_, f)
      try:
        if os.path.isfile(f_path):
          os.unlink(f_path)
          logging.debug('file=%s is deleted', f)
      except Exception, e:
        logging.error('%s', e)
  
  def write_to_htbfile(self, filename, data):
    f = open( '%s/%s/%s' % (self.htbdir,self.intf,filename), 'w')
    f.write(data)
    f.close()
    logging.debug('data=\n%s\nis written to filename=%s',data,filename)
  
  def clear_htbconf(self):
    logging.info('clear_htbconf:: started;')
    self.run_htbinit('dconf')
    #self.run_htbinit('show')
    logging.info('clear_htbconf::done.')
  
  def init_htbconf(self, parism_l, p_bw, p_tp_dst):
    logging.info('init_htbconf:: started;')
    #
    for p_id in range(0, parism_l):
      data = self.get_htbclass_confdata(rate = str(BWREGCONST*p_bw[p_id])+'Mbit',
                                        burst = '15k',
                                        leaf = 'netem',
                                        rule = '*:%s' % p_tp_dst[p_id] )
                                        #rule = '%s:%s' % (self.cl_ip, p_tp_dst[p_id]) )
      filename = '%s-1:%s.%s' % (self.intf, (p_id+1)*11, p_tp_dst[p_id])
      self.write_to_htbfile(filename, data)
    #
    self.run_htbinit('dconf')
    self.run_htbinit('conf')
    #self.run_htbinit('show')
    #
    logging.info('init_htbconf:: done.')
  
  def get_htbclass_confdata(self, rate, burst, leaf, rule):
    #print 'rate=%s, rule=%s' % (rate, rule)
    return 'RATE=%s\nBURST=%s\nLEAF=%s\nRULE=%s' % (rate,burst,leaf,rule)

  def run_htbinit(self, command):
    cli_o = None
    if command == 'conf':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),
                                         'start','invalidate',
                                         self.intf, self.htbdir, 'add_root' ] )
      except subprocess.CalledProcessError as e:
        logging.error('###CONF_ERR=%s', e.output)
    elif command == 'dconf':
      try:
        #cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),
        #                                 'minstop','...',
        #                                 self.intf, self.htbdir ] )
        cli_o = subprocess.check_output(['sudo','tc','qdisc','del','dev',self.intf,'root' ] )
      except subprocess.CalledProcessError as e:
        logging.error('###DCONF_ERR=%s', e.output)
    elif command == 'show':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'run.sh'),'show','p'] )
        #cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),'stats'] )
      except subprocess.CalledProcessError as e:
        logging.error('###SHOW_ERR=%s', e.output)
    else:
      logging.error('unknown command=%s',command)
      return
    #
    #logging.info('\n----------------------------------------------------------')
    #logging.info('%s_output:\n%s',command,cli_o)
  #############################  data trans rel  ###############################
  def send_join_req(self):
    if self.state != 0:
      logging.error('send_join_req:: unexpected cur_state=%s', self.state)
      return
    #
    msg = {'type':'join_req',
           'data':''}
    if self.userdts_intf.relsend_to_dts(msg) == 0:
      logging.error('send_join_req:: failed!')
    else:
      logging.debug('send_join_req:: success.')
      self.joinreqsent_time = time.time()
  
  def send_sching_req(self):
    if self.state != 1:
      logging.error('send_sching_req:: unexpected cur_state=%s', self.state)
      return
    #
    msg = {'type':'sching_req',
           'data':{'c_ip':self.cl_ip,
                   'req_dict':self.req_dict,
                   'app_pref_dict':self.app_pref_dict } }
    if self.userdts_intf.relsend_to_dts(msg) == 0:
      logging.error('send_sching_req:: failed !')
    else:
      logging.debug('send_sching_req:: success.')
      self.schingreqsent_time = time.time()
    
  def close(self):
    self.userdts_intf.close()
    #
    for sch_req_id,sinfo in self.sinfo_dict.items():
      for qtosender in sinfo['qtosender']:
        qtosender.put('STOP')
    #
    logging.info('close:: all sender threads joined, closed.')
  ##############################################################################
  def test(self):
    self.send_join_req()
    """
    self.state = 1
    self.send_sching_req()
    """
    #self.state = 1
  
def main(argv):
  intf = dtst_port = dtsl_ip = dtsl_port = cl_ip = proto = tx_type = file_url = kstardata_url = logto = nodename = None
  req_dict = app_pref_dict = htbdir = None
  try:
    opts, args = getopt.getopt(argv,'',['intf=','dtst_port=','dtsl_ip=','dtsl_port=', 'cl_ip=','proto=','tx_type=','file_url=', 'kstardata_url=', 'logto=','nodename=','req_dict=','app_pref_dict=', 'htbdir='])
  except getopt.GetoptError:
    print 'producer.py --intf=<> --dtst_port=<> --dtsl_ip=<> --dtsl_port=<> --cl_ip=<> --proto=tcp/udp --tx_type=file/dummy --file_url=<> --kstardata_url=<> --logto=<> --nodename=<> --req_dict=<> --app_pref_dict=<> --htbdir=<>'
    sys.exit(2)
  #Initializing global variables with comman line options
  for opt, arg in opts:
    if opt == '--intf':
      intf = arg
    elif opt == '--dtst_port':
      dtst_port = int(arg)
    elif opt == '--dtsl_ip':
      dtsl_ip = arg
    elif opt == '--dtsl_port':
      dtsl_port = int(arg)
    elif opt == '--cl_ip':
      cl_ip = arg
    elif opt == '--proto':
      if arg == 'tcp' or arg == 'udp':
        proto = arg
      else:
        print 'unknown proto=%s' % arg
        sys.exit(2)
    elif opt == '--tx_type':
      if arg == 'file' or arg == 'dummy' or arg == 'kstardata' or arg == 'kstardata2' or arg == 'fastdata':
        tx_type = arg
      else:
        print 'unknown tx_type=%s' % arg
        sys.exit(2)
    elif opt == '--file_url':
      file_url = arg
    elif opt == '--kstardata_url':
      kstardata_url = arg
    elif opt == '--logto':
      logto = arg
    elif opt == '--nodename':
      nodename = arg
    elif opt == '--req_dict':
      req_dict = json.loads(arg)
    elif opt == '--app_pref_dict':
      app_pref_dict = json.loads(arg)
    elif opt == '--htbdir':
      htbdir = arg
  #where to log; console or file
  if logto == 'file':
    logging.basicConfig(filename='logs/%s.log' % nodename, filemode='w', level=logging.DEBUG)
  elif logto == 'console':
    logging.basicConfig(level=logging.DEBUG)
  else:
    raise CommandLineOptionError('Unexpected logto', logto)
  #
  p = Producer(intf = intf,
               dtst_port = dtst_port,
               dtsl_ip = dtsl_ip,
               dtsl_port = dtsl_port,
               cl_ip = cl_ip,
               proto = proto,
               tx_type = tx_type,
               file_url = file_url,
               kstardata_url = kstardata_url,
               req_dict = req_dict,
               app_pref_dict = app_pref_dict,
               htbdir = htbdir,
               logto = logto )
  #
  import threading
  t = threading.Thread(target=p.test)
  t.start()
  #
  if nodename == 'p':
    raw_input('Enter\n')
  else:
    time.sleep(100000)
  #
  p.close()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

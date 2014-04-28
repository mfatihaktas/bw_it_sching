#!/usr/bin/python
import sys,json,logging,subprocess,getopt,commands,pprint,os,Queue
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

IMGSIZE = 24*8*9

class Producer(object):
  def __init__(self, intf, pl_port, dtsl_ip, dtsl_port, cl_ip, proto,tx_type, file_url, kstardata_url,
               req_dict,app_pref_dict, htbdir, logto):
    self.logto = logto
    self.intf = intf
    self.pl_ip = get_addr(intf)
    self.pl_port = pl_port
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
                                        user_addr = (self.pl_ip,self.pl_port),
                                        dts_addr = (self.dtsl_ip,self.dtsl_port),
                                        _recv_callback = self._handle_recvfromdts )
    #for htb_queue conf - bw shaping
    self.ktif = 230 #kernel timer interrupt frequency (Hz)
    self.init_htbdir()
    #
    self.sender_thread_list = []
    self.queue_tosender = Queue.Queue(0)
    self.queue_fromsender = Queue.Queue(0)
    
  ########################  _handle_***  ########################
  def _handle_recvfromdts(self, msg):
    [type_, data_] = msg
    if type_ == 'sching_reply':
      if self.state != 1:
        logging.error('sching_reply: unexpected cur_state=%s', self.state)
        return
      #
      if data_ != 'sorry':
        self.state = 2
        logging.info('successful sch_req :) data_=\n%s', pprint.pformat(data_))
        #immediately start streaming session data
        pl = int(data_['parism_level'])
        p_bw = data_['p_bw']
        p_tp_dst = data_['p_tp_dst']
        #
        self.init_htbconf(pl, p_bw, p_tp_dst)
        datasize = float(self.req_dict['data_size'])
        for i in range(pl):
          self.stream_sdata(datasize = datasize*float(self.req_dict['par_share'][i]),
                            cl_port = p_tp_dst[i] )
        #
        for i in range(pl):
          popped = self.queue_fromsender.get(True, None)
          if popped != 'done':
            logging.error('_handle_recvfromdts:: unexpected popped=%s', popped)
        #
        self.send_session_done(sch_req_id = data_['sch_req_id'])
        self.clear_htbconf()
        self.init_htbdir()
      else:
        logging.info('unsuccessful sch_req :( data_=%s', data_)
        return
    elif type_ == 'resching_reply':
      if self.state != 2:
        logging.error('resching_reply: unexpected cur_state=%s', self.state)
        return
      #
      logging.info('resching_reply:: data_=\n%s', pprint.pformat(data_))
      #reinit htb
      pl = int(data_['parism_level'])
      p_bw = data_['p_bw']
      p_tp_dst = data_['p_tp_dst']
      #
      self.init_htbconf(pl, p_bw, p_tp_dst)
      
    elif type_ == 'join_reply':
      if self.state != 0:
        logging.error('join_reply: unexpected cur_state=%s', self.state)
        return
      #
      if data_ == 'welcome':
        self.state = 1
        logging.info('joined to dts :) data_=%s', data_)
        self.send_sching_req()
      elif data_ == 'sorry':
        logging.info('cannot join to dts :( data_=%s', data_)
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
    self.write_to_file(self.intf,'DEFAULT=0')
  
  def clean_dir(self, dir_):
    for f in os.listdir(dir_):
      f_path = os.path.join(dir_, f)
      try:
        if os.path.isfile(f_path):
          os.unlink(f_path)
          logging.debug('file=%s is deleted', f)
      except Exception, e:
        logging.error('%s', e)
  
  def write_to_file(self, filename, data):
    f = open( '%s/%s/%s' % (self.htbdir,self.intf,filename), 'w')
    f.write(data)
    f.close()
    logging.debug('data=\n%s\nis written to filename=%s',data,filename)
  
  def clear_htbconf(self):
    logging.info('clear_htbconf:: started;')
    self.run_htbinit('dconf')
    self.run_htbinit('show')
    logging.info('clear_htbconf::done.')
  
  def init_htbconf(self, parism_l, p_bw, p_tp_dst):
    logging.info('init_htbconf:: started;')
    #
    for p_id in range(0, parism_l):
      data = self.get_htbclass_confdata(rate = str(p_bw[p_id])+'Mbit',
                                        burst = '15k',
                                        leaf = 'netem',
                                        rule = '*:%s' % p_tp_dst[p_id] )
                                        #rule = '%s:%s' % (self.cl_ip, p_tp_dst[p_id]) )
      filename = '%s-1:%s.%s' % (self.intf, (p_id+1)*11, p_tp_dst[p_id])
      self.write_to_file(filename, data)
    #
    self.run_htbinit('dconf')
    self.run_htbinit('conf')
    self.run_htbinit('show')
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
                                         self.intf, self.htbdir, 'not_add_root' ] )
      except subprocess.CalledProcessError as e:
        logging.error('###CONF_ERR=%s', e.output)
    elif command == 'dconf':
      try:
        cli_o = subprocess.check_output(['sudo','%s/%s' % (self.htbdir,'htb.init.sh'),
                                         'minstop','...',
                                         self.intf, self.htbdir ] )
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
  def stream_sdata(self, datasize, cl_port):
    if self.state != 2:
      logging.error('stream_sdata: unexpected cur_state=%s', self.state)
      return
    #
    to_addr = (self.cl_ip, cl_port)
    sender = Sender(in_queue = self.queue_tosender,
                    out_queue = self.queue_fromsender,
                    dst_addr = to_addr,
                    proto = self.proto,
                    datasize = datasize,
                    tx_type = self.tx_type,
                    file_url = self.file_url,
                    logto = self.logto,
                    kstardata_url = self.kstardata_url,
                    numimg = int(float(float(datasize)*(1024**2))/IMGSIZE) )
    sender.start()
    self.sender_thread_list.append(sender)
  
  def send_session_done(self, sch_req_id):
    if self.state != 2:
      logging.error('send_session_done:: unexpected cur_state=%s', self.state)
      return
    #
    msg = {'type':'session_done',
           'data':{'sch_req_id': sch_req_id} }
    if self.userdts_intf.relsend_to_dts(msg) == 0:
      logging.error('send_session_done:: failed!')
    else:
      logging.debug('send_session_done:: success.')
  
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
  
  def send_sching_req(self):
    if self.state != 1:
      logging.error('send_sching_req: unexpected cur_state=%s', self.state)
      return
    #
    msg = {'type':'sching_req',
           'data':{'c_ip':self.cl_ip,
                   'req_dict':self.req_dict,
                   'app_pref_dict':self.app_pref_dict } }
    if self.userdts_intf.relsend_to_dts(msg) == 0:
      logging.error('send_sching_req: failed !')
    else:
      logging.debug('send_sching_req:: success.')
    
  def close(self):
    self.userdts_intf.close()
    #
    for i in range(len(self.sender_thread_list)):
      self.queue_tosender.put('stop')
    #
    logging.info('close:: all sender threads joined.')
    logging.info('producer:: closed.')
  ##############################################################################
  def test(self):
    """
    pl = 2
    p_bw = ['1', '2']
    p_tp_dst = ['6000','6001']
    self.init_htbconf(pl, p_bw, p_tp_dst)
    """
    self.send_join_req()
    """
    self.state = 1
    self.send_sching_req()
    """
    #self.state = 1
  
def main(argv):
  intf = pl_port = dtsl_ip = dtsl_port = cl_ip = proto = tx_type = file_url = kstardata_url = logto = None
  req_dict = app_pref_dict = htbdir = None
  try:
    opts, args = getopt.getopt(argv,'',['intf=','dtst_port=','dtsl_ip=','dtsl_port=', 'cl_ip=','proto=','tx_type=','file_url=', 'kstardata_url=', 'logto=','req_dict=','app_pref_dict=', 'htbdir='])
  except getopt.GetoptError:
    print 'producer.py --intf=<> --dtst_port=<> --dtsl_ip=<> --dtsl_port=<> --cl_ip=<> --proto=tcp/udp --tx_type=file/dummy --file_url=<> --kstardata_url=<> --logto=<> --req_dict=<> --app_pref_dict=<> --htbdir=<>'
    sys.exit(2)
  #Initializing global variables with comman line options
  for opt, arg in opts:
    if opt == '--intf':
      intf = arg
    elif opt == '--dtst_port':
      pl_port = int(arg)
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
      if arg == 'file' or arg == 'dummy':
        tx_type = arg
      else:
        print 'unknown rx_type=%s' % arg
        sys.exit(2)
    elif opt == '--file_url':
      file_url = arg
    elif opt == '--kstardata_url':
      kstardata_url = arg
    elif opt == '--logto':
      logto = arg
    elif opt == '--req_dict':
      req_dict = json.loads(arg)
    elif opt == '--app_pref_dict':
      app_pref_dict = json.loads(arg)
    elif opt == '--htbdir':
      htbdir = arg
  #where to log; console or file
  if logto == 'file':
    logging.basicConfig(filename='logs/p.log', filemode='w', level=logging.DEBUG)
  elif logto == 'console':
    logging.basicConfig(level=logging.DEBUG)
  else:
    raise CommandLineOptionError('Unexpected logto', logto)
  #
  p = Producer(intf = intf,
               pl_port = pl_port,
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
  raw_input('Enter\n')
  p.close()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

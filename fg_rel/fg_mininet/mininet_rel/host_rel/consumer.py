#!/usr/bin/python

import sys,json,logging,getopt,commands,Queue,pprint,threading
from errors import CommandLineOptionError
from userdts_comm_intf import UserDTSCommIntf
from receiver import Receiver

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
  
class Consumer(object):
  def __init__(self, cl_ip, cl_port_list, dtsl_ip, dtsl_port, dtst_port, proto, 
               rx_type, logto):
    self.cl_ip = cl_ip
    self.cl_port_list = cl_port_list
    self.dtsl_ip = dtsl_ip
    self.dtsl_port = dtsl_port
    self.dtst_port = dtst_port
    self.proto = proto
    self.rx_type = rx_type
    self.logto = logto
    #for control state
    self.userdts_intf = UserDTSCommIntf(sctag = 'c-dts',
                                        user_addr = (self.cl_ip,self.dtst_port),
                                        dts_addr = (self.dtsl_ip,self.dtsl_port),
                                        _recv_callback = self._handle_recvfromdts )
    #
    self.sinfo_dict = {}
    #
    self.recver_thread_list = []
    self.queue_torecvers = Queue.Queue(0)
  
  def _handle_recvfromdts(self, msg):
    #msg = [type_, data_]
    [type_, data_] = msg
    if type_ == 'join_reply':
      if data_ == 'welcome':
        logging.info('_handle_recvfromdts:: joined to dts :)')
        #immediately start s_recving_servers
        #self.start_recvers()
      elif data_ == 'sorry':
        logging.info('_handle_recvfromdts:: couldnot join to dts :(')
    elif type_ == 'sching_reply':
      self.welcome_s(data_)
      
    
  def welcome_s(self, data_):
    sch_req_id = data_['sch_req_id']
    pl = int(data_['parism_level'])
    p_tp_dst = data_['p_tp_dst']
    qtorecver_list = [Queue.Queue(0) for i in range(pl)]
    qfromrecver_list = [Queue.Queue(0) for i in range(pl)]
    for i,stpdst in enumerate(p_tp_dst):
      laddr = (self.cl_ip, int(stpdst))
      recver = Receiver(in_queue = qtorecver_list[i],
                        out_queue = qfromrecver_list[i],
                        laddr = laddr,
                        proto = self.proto,
                        rx_type = 'kstardata',
                        file_url = 'kstardata_%s.dat' % stpdst,
                        logto = self.logto )
      recver.start()
    #
    self.sinfo_dict[sch_req_id] = {'parism_level': pl,
                                   'p_tp_dst': p_tp_dst,
                                   'qtorecver_list': qtorecver_list,
                                   'qfromrecver_list': qfromrecver_list }
    logging.info('welcome_s:: welcome sinfo=\n%s', pprint.pformat(self.sinfo_dict[sch_req_id]))
    threading.Thread(target = self.waitfor_couplingtoend,
                     kwargs = {'sch_req_id': sch_req_id} ).start()
    
  def waitfor_couplingtoend(self, sch_req_id):
    couplinginfo_dict = {'sch_req_id': sch_req_id,
                         'recvedsize': 0,
                         'recvstart_time': float('Inf'),
                         'recvend_time': 0,
                         'recvedsizewithfunc_dict': {} }
    
    qfromrecver_list = self.sinfo_dict[sch_req_id]['qfromrecver_list']
    for qfromrecver in qfromrecver_list:
      info_dict = qfromrecver.get(True, None)
      couplinginfo_dict['recvedsize'] += info_dict['recvedsize']
      couplinginfo_dict['recvend_time'] = max(couplinginfo_dict['recvend_time'], info_dict['recvend_time'])
      couplinginfo_dict['recvstart_time'] = min(couplinginfo_dict['recvstart_time'], info_dict['recvstart_time'])
      
      recvedsizewithfunc_dict = couplinginfo_dict['recvedsizewithfunc_dict']
      for func,recvedsize in info_dict['recvedsizewithfunc_dict'].items():
        if func in recvedsizewithfunc_dict:
          recvedsizewithfunc_dict[func] += recvedsize
        else:
          recvedsizewithfunc_dict[func] = recvedsize
        #
      #
    #
    msg = {'type': 'coupling_done',
           'data': couplinginfo_dict }
    self.userdts_intf.relsend_to_dts(msg)
    
    logging.info('waitfor_couplingtoend:: coupling ended; couplinginfo_dict=\n%s', pprint.pformat(couplinginfo_dict))
    
  def send_join_req(self):
    msg = {'type':'join_req',
           'data':''}
    self.userdts_intf.relsend_to_dts(msg)
  
  def close(self):
    self.userdts_intf.close()
    #
    for sch_req_id in self.sinfo_dict:
      for qtorecver in self.sinfo_dict[sch_req_id]['qtorecver_list']:
        qtorecver.put('STOP')
    #
    logging.info('close:: all session recver threads joined.')
    
    for i in range(len(self.recver_thread_list)):
      self.queue_torecvers.put('STOP')
    #
    logging.info('close:: all dummy recver threads joined.')
    
    logging.info('consumer:: closed.')
  
  def start_recvers(self):
    for port in self.cl_port_list:
      addr = (self.cl_ip, port)
      recver = Receiver(in_queue = self.queue_torecvers,
                        laddr = addr,
                        proto = self.proto,
                        rx_type = self.rx_type,
                        file_url = 'rx_over_%s.dat' % port,
                        logto = self.logto )
      recver.start()
      self.recver_thread_list.append(recver)
    #
  
  def test(self):
    self.send_join_req()
    #self.start_recvers()
    '''
    data_ = {'sch_req_id': 0,
             'parism_level': 1,
             'p_tp_dst': [6000] }
    self.welcome_s(data_)
    '''
    
def main(argv):
  intf = cl_port_list_ = dtst_port = dtsl_ip = dtsl_port = proto = rx_type = logto = None
  cl_port_list = []
  try:
    opts, args = getopt.getopt(argv,'', \
    ['intf=','cl_port_list=','dtst_port=','dtsl_ip=','dtsl_port=','proto=','rx_type=','logto='])
  except getopt.GetoptError:
    print 'transit.py --intf=<> --cl_port_list=lport1,lport2, ... --dtst_port=<>', \
          '--dtsl_port=<> --dtsl_ip=<> --proto=<> --rx_type=<> --logto=<>'
    sys.exit(2)

  #Initializing global variables with command line options
  for opt, arg in opts:
    if opt == '--intf':
      intf = arg
    elif opt == '--cl_port_list':
      cl_port_list_ = arg
    elif opt == '--dtst_port':
      dtst_port = int(arg)
    elif opt == '--dtsl_ip':
      dtsl_ip = arg
    elif opt == '--dtsl_port':
      dtsl_port = int(arg)
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
    elif opt == '--logto':
      logto = arg
  #
  for port in cl_port_list_.split(','):
    cl_port_list.append(int(port))
  #where to log, console or file
  if logto == 'file':
    logging.basicConfig(filename='logs/c.log',filemode='w',level=logging.DEBUG)
  elif logto == 'console':
    logging.basicConfig(level=logging.DEBUG)
  else:
    raise CommandLineOptionError('Unexpected logto', logto)
  #
  cl_ip = get_addr(intf)
  c = Consumer(cl_ip = cl_ip,
               cl_port_list = cl_port_list,
               dtsl_ip = dtsl_ip,
               dtsl_port = dtsl_port,
               dtst_port = dtst_port,
               proto = proto,
               rx_type = rx_type,
               logto = logto )
  #
  c.test()
  #
  raw_input('Enter\n')
  c.close()
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

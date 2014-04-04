#!/usr/bin/python

import sys,json,logging,getopt,commands
from errors import CommandLineOptionError
from control_comm_intf import ControlCommIntf
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
    '''0:start, 1:joined to dts, 2:ready to recv s_data'''
    self.state = 0
    #for control comm
    self.cci = ControlCommIntf()
    self.cci.reg_commpair(sctag = 'c-dts',
                          proto = 'udp',
                          _recv_callback = self._handle_recvfromdts,
                          s_addr = (self.cl_ip,self.dtst_port),
                          c_addr = (self.dtsl_ip,self.dtsl_port) )
  
  def _handle_recvfromdts(self, msg):
    #msg = [type_, data_]
    [type_, data_] = msg
    if type_ == 'join_reply':
      if self.state != 0:
        logging.error('join_reply: unexpected cur_state=%s', self.state)
        return
      #
      if data_ == 'welcome':
        self.state = 1
        logging.info('joined to dts :) data_=%s', data_)
        #immediately start s_recving_servers
        self.start_recvers()
      elif data_ == 'sorry':
        logging.info('cannot join to dts :( data_=%s', data_)
  
  def start_recvers(self):
    if self.state != 1:
      logging.error('stream_sdata: unexpected cur_state=%s', self.state)
      return
    #
    for port in self.cl_port_list:
      addr = (self.cl_ip, port)
      recver = Receiver(laddr = addr,
                        proto = self.proto,
                        rx_type = self.rx_type,
                        file_url = 'rx_%s.dat' % port,
                        logto = self.logto )
      logging.info('recver started at addr=%s', addr)
    #
    self.state = 2
  
  def send_join_req(self):
    if self.state != 0:
      logging.error('send_join_req: unexpected cur_state=%s', self.state)
      return
    #
    msg = json.dumps({'type':'join_req',
                      'data':''})
    self.cci.send_to_client('c-dts',msg)
  
  def test(self):
    self.send_join_req()
    """
    self.state = 1
    self.start_recvers()
    """
  
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

  #Initializing global variables with comman line options
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
      if arg == 'file' or arg == 'dummy':
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
  c.test()
  #
  raw_input('Enter')
  
if __name__ == "__main__":
  main(sys.argv[1:])
  

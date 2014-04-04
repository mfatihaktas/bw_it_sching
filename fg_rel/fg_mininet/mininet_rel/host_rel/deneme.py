#!/usr/bin/python

import mmap,os,pprint,threading,time,thread,Queue,logging,subprocess
from multiprocessing import Process
from sender import Sender

def main():
  htbdir = '/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel'
  peth0dir_1 = '/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel/p-eth0_1'
  peth0dir_2 = '/home/ubuntu/mininet/mininet_rel/host_rel/tc_rel/htb_rel/p-eth0_2'
  #setup 10Mbps
  try:
    cli_o = subprocess.check_output(['%s/%s' % (htbdir,'run.sh'),
                                     'minstop','p' ])
    cli_o = subprocess.check_output(['%s/%s' % (htbdir,'run.sh'),
                                     'conf','p','1' ])
  except subprocess.CalledProcessError as e:
    print 'ERR=%s\n' % e.output
  print 'setup 10Mbps'
  #
  queue_tosender = Queue.Queue(0)
  ds = Sender(in_queue = queue_tosender,
              dst_addr = ('10.0.0.111', 6000),
              proto = 'tcp',
              datasize = 100,
              tx_type = 'file',
              file_url = 'ltx.dat',
              logto = 'console' )
  ds.start()
  #
  time.sleep(4) #to let half of the file_tx to finish
  #setup 5Mbps
  try:
    cli_o = subprocess.check_output(['%s/%s' % (htbdir,'run.sh'),
                                     'minstop','p' ])
    cli_o = subprocess.check_output(['%s/%s' % (htbdir,'run.sh'),
                                     'conf','p','2' ])
  except subprocess.CalledProcessError as e:
    print 'ERR=%s' % e.output
  print 'setup 5Mbps'
  #
  raw_input('Enter\n')
  queue_tosender.put('stop')
  '''
  #p = Process(target=somework())
  #p.start()
  t1 = threading.Thread(target=somework)
  t2 = threading.Thread(target=somework)
  t1.start()
  t2.start()
  #thread.start_new_thread(somework)
  print 'here'
  '''
  '''
  file_obj = open('deneme.dat', 'w')
  file_obj.write('BOF\n')
  file_obj.close()
  file_obj2 = open('deneme.dat', 'r+')
  mm = mmap.mmap(fileno = file_obj2.fileno(),
                 length = 0,
                 access = mmap.ACCESS_WRITE )
  print 'mm.size()=%s' % mm.size()
  #
  newsize = 16
  mm.resize(newsize)
  for i in range(0, newsize/4):
    mm.write('***%s' % i)
  #
  for i in range(0, newsize/4):
    print 'mm[i*4:(i+1)*4]=%s' % mm[i*4:(i+1)*4]
    #if i != newsize/4:
    #  mm.seek(4, os.SEEK_CUR)
  #
  flush_r = mm.flush()
  if flush_r == 0:
    print 'mm is flushed successfully'
  #
  print 'mm.read(mm.size())=%s' % mm.read(mm.size())
  print 'mm[:]=%s' % mm[:]
  #
  file_obj.close()
  mm.close()
  '''
  #
  #r = os.remove('deneme1.txt')
  #print 'r=%s' % r
'''
def somework():
  time.sleep(1)
  print 'somework::1'
  time.sleep(1)
  print 'somework::2'
  time.sleep(1)
  print 'somework::3'

def dict_modify():
  dict_ = {'info':{'a':1, 'b':2},
           '1':1, '2':2, '3':3}
  print 'dict_=%s' % pprint.pformat(dict_)
  #
  print 'modify info;'
  info=dict_['info']
  info['c']=3
  first = dict_['1']
  first = 11
  #
  print 'dict_=%s' % pprint.pformat(dict_)
'''





if __name__ == "__main__":
  main()
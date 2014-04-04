#!/usr/bin/python

import mmap, os

def main():
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
  #
  #r = os.remove('deneme1.txt')
  #print 'r=%s' % r







if __name__ == "__main__":
  main()
#!/usr/bin/python
import numpy as np

num_sessions = 11

val_type_dict = {0: 'tight',
                 1: 'loose',
                 2: 'dataflow' }

s_list = np.random.uniform(0, 3, num_sessions)
datasize_list = np.random.uniform(10, 100, num_sessions)

opt_list = []
for i in range(num_sessions):
  mean = 1.5*datasize_list[i]
  var = 0.1*mean
  opt_list.append( int(np.random.normal(mean, var)) )

print 'Id \t Type \t Datasize \t Opt time'
for i, s in enumerate(s_list):
  print '%s \t %s \t %s \t %s' % (i, val_type_dict[int(s)], int(datasize_list[i]), opt_list[i] )
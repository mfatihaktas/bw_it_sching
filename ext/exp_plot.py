import subprocess

class ExpPlotter(object):
  def __init__(self):
    pass
  
  def rows_to_columns(self, furl):
    list_ = []
    max_ = 0
    with open(furl, 'r') as f:
      for line in f:
        #print 'line=%s' % line
        token_list = line.strip(' \n').split(' ')
        #print 'token_list=%s' % token_list
        if len(token_list) > max_:
          max_ = len(token_list)
        #
        list_.append(token_list)
      #
    #
    #print 'max_=%s' % max_
    #print 'list_=\n%s' % pprint.pformat(list_)
    #
    str_ = ''
    for lnum in range(max_):
      for rowtoken_list in list_:
        try:
          str_ += rowtoken_list[lnum] + ' '
        except IndexError:
          str_ += '0.00000000000' + ' '
        #
      #
      str_ += '\n'
    #
    f = open(furl, 'w')
    f.truncate()
    f.write(str_)
    f.close()
  
  def write_expdatafs(self, couplingdoneinfo_dict, outf1url, resid_rescapalloc_dict, outf2basename):
    '''
    1:sch_req_id  2:recvedsize  3:slacktime  4:couplingdur  5:couplingdur_relerr  
    6:recvedsizewithf1  7:recvedpercwithf1  8:recvedsizewithf2  9:recvedpercwithf2
    10: joinrr_time 11: schingrr_time 12: sching_overhead
    '''
    maxnumitfuncs = 2
    outf1 = open(outf1url, 'w')
    
    for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items():
      #1:5
      infostr = str(sch_req_id) + ' ' + \
                str(float(couplingdoneinfo['overall']['recvedsize'])/(1024**2)) + ' ' + \
                str(couplingdoneinfo['overall']['idealtrans_time']) + ' ' + \
                str(couplingdoneinfo['overall']['coupling_dur']) + ' ' + \
                str(abs(couplingdoneinfo['overall']['couplingdur_relerr'])) + ' '
      #6:9
      for func,size in couplingdoneinfo['coupling_done']['recvedsizewithfunc_dict'].items():
        infostr += str(float(size)/(1024**2)) + ' ' + str(couplingdoneinfo['overall']['recvedpercentwithfunc_dict'][func]) + ' '
      
      for i in range(maxnumitfuncs-len(couplingdoneinfo['coupling_done']['recvedsizewithfunc_dict'])):
        infostr += '0' + ' ' + '0' + ' '
      #10:
      infostr += str(abs(couplingdoneinfo['session_done']['joinrr_time'])) + ' ' +\
                 str(abs(couplingdoneinfo['session_done']['schingrr_time'])) + ' ' +\
                 str(abs(couplingdoneinfo['overall']['sching_overhead'])) + ' '
      # 
      infostr += '\n'
      outf1.write(infostr)
    #
    outf1.close()
    #
    for res_id, rescapalloc_dict in resid_rescapalloc_dict.items():
      outf2url = outf2basename+str(res_id)+'.dat'
      outf2 = open(outf2url, 'w')
      #
      infostr = ''
      for sching_id, rescapalloc in rescapalloc_dict.items():
        salloc_str = None
        if 'bw_salloc_dict' in rescapalloc:
          salloc_str = 'bw_salloc_dict'
        elif 'proc_salloc_dict' in rescapalloc:
          salloc_str = 'proc_salloc_dict'
        #
        for s_id, salloc in rescapalloc[salloc_str].items():
          infostr += str(salloc) + ' '
        #
        infostr += '\n'
      # 
      outf2.write(infostr)
      outf2.close()
      self.rows_to_columns(outf2url)
    #
  
  def plot_sizerel(self, datafurl, outfurl, nums, yrange):
    pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
    pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
    pipe.stdin.write('set output "%s"\n' % outfurl)
    #pipe.stdin.write('set title "Coupling data size for each session" \n')
    pipe.stdin.write('set xlabel "Session Id"\n')
    pipe.stdin.write('set ylabel "Datasize (MB)"\n')
    #pipe.stdin.write('set auto x\n')
    pipe.stdin.write('set xrange [-1:%s] \n' % (int(nums)+1) )
    pipe.stdin.write('set yrange [0:%s] \n' % yrange)
    #pipe.stdin.write('set boxwidth 0.6 absolute\n')
    pipe.stdin.write('set grid\n')
    pipe.stdin.write('set boxwidth 0.2 absolute\n')
    pipe.stdin.write('set key inside right top vertical Right noreverse noenhanced autotitles nobox\n')
    #pipe.stdin.write('set style data histogram\n')
    #pipe.stdin.write('set style fill solid 1.00 border -1\n')
    pipe.stdin.write('set style fill solid border -1\n')
    pipe.stdin.write('set style fill pattern border\n')
    pipe.stdin.write('set samples 11\n')
    #pipe.stdin.write('set xtics rotate out\n')
    pipe.stdin.write('plot "%s" using 2:xtic(1) w boxes fs pattern 1 lc rgb "#000000" title "total size"' % datafurl + \
                   ', "" using 6 w boxes fs pattern 2 lc rgb "#696969" title "fft"' + \
                   ', "" using 8 w boxes fs pattern 3 lc rgb "#7F7F7F" title "upsample-plot"\n' )
    #
  
  def plot_timerel(self, datafurl, outfurl, nums, yrange):
    pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
    pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
    pipe.stdin.write('set output "%s"\n' % outfurl)
    #pipe.stdin.write('set title "Coupling time for each session" \n')
    pipe.stdin.write('set xlabel "Session Id"\n')
    pipe.stdin.write('set ylabel "Time (sec)"\n')
    pipe.stdin.write('set y2label "Relative Error"\n')
    
    pipe.stdin.write('set xrange [-1:%s] \n' % (int(nums)+1) )
    pipe.stdin.write('set yrange [0:%s] \n'  % yrange )
    pipe.stdin.write('set y2range [0:5] \n')
    
    pipe.stdin.write('set ytics nomirror \n')
    pipe.stdin.write('set y2tics nomirror border \n')
    
    pipe.stdin.write('set grid\n')
    pipe.stdin.write('set boxwidth 0.2 absolute\n')
    pipe.stdin.write('set key inside right top vertical Right noreverse noenhanced autotitles nobox\n')
    pipe.stdin.write('set style fill solid border -1\n')
    pipe.stdin.write('set style fill pattern border\n')
    pipe.stdin.write('set samples 11\n')
    pipe.stdin.write('plot "%s" using 3:xtic(1) w points linewidth 2 lc rgb "#000000" title "slack time"' % datafurl + \
                     ', "" using 4 w points linewidth 2 lc rgb "#696969" title "coupling time"' + \
                     ', "" using 5 axes x1y2 w points pointsize 2 lc rgb "#7F7F7F" title "rel-err"\n' )
    #
  def plot_overheadrel(self, datafurl, outfurl, nums, yrange):
    #10: joinrr_time 11: schingrr_time 12: sching_overhead
    pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
    pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
    pipe.stdin.write('set output "%s"\n' % outfurl)
    #pipe.stdin.write('set title "" \n')
    pipe.stdin.write('set xlabel "Session Id"\n')
    pipe.stdin.write('set ylabel "Time (sec)"\n')
    pipe.stdin.write('set y2label "Overhead"\n')
    
    pipe.stdin.write('set xrange [-1:%s] \n' % (int(nums)+1) )
    pipe.stdin.write('set yrange [0:%s] \n'  % yrange )
    pipe.stdin.write('set y2range [0:5] \n')
    
    pipe.stdin.write('set ytics nomirror \n')
    pipe.stdin.write('set y2tics nomirror border \n')
    
    pipe.stdin.write('set grid\n')
    pipe.stdin.write('set boxwidth 0.2 absolute\n')
    pipe.stdin.write('set key inside right top vertical Right noreverse noenhanced autotitles nobox\n')
    pipe.stdin.write('set style fill solid border -1\n')
    pipe.stdin.write('set style fill pattern border\n')
    pipe.stdin.write('set samples 11\n')
    pipe.stdin.write('plot "%s" using 11:xtic(1) w points linewidth 2 lc rgb "#000000" title "sching rtt"' % datafurl + \
                     ', "" using 10 w points linewidth 2 lc rgb "#696969" title "join rtt"' + \
                     ', "" using 12 axes x1y2 w points pointsize 2 lc rgb "#7F7F7F" title "overhead"' + \
                     ', 1 w l lw 1 lc rgb "#000000" title "rtt" \n' )
  
  def plot_resallocrel(self, datafurl, outfurl, numsching, yrange, resunit):
    pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
    pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
    pipe.stdin.write('set output "%s"\n' % outfurl)
    pipe.stdin.write('set xlabel "Scheduling Id"\n')
    pipe.stdin.write('set ylabel "Resource Capacity (%s)"\n' % resunit)
    
    pipe.stdin.write('set xrange [-0.5:%s] \n' % (int(numsching)+1) )
    pipe.stdin.write('set yrange [0:%s] \n'  % yrange )
    pipe.stdin.write('set xtics 1\n')
    
    pipe.stdin.write('set style data histogram\n')
    pipe.stdin.write('set style histogram columnstacked\n')
    pipe.stdin.write('set boxwidth 0.2 absolute\n')
    pipe.stdin.write('set style fill solid border -1\n')
    pipe.stdin.write('set style fill pattern border\n')
    pipe.stdin.write('set samples 11\n')
    
    str_ = 'plot "%s" using 1' % datafurl
    for n in range(numsching-1):
      str_ += ', "" using %s' % (n+2)
    #
    pipe.stdin.write( str_+'\n' )
    
def main():
  pass

if __name__ == "__main__":
  main()

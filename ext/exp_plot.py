import subprocess

class ExpPlotter(object):
  def __init__(self):
    pass
  
  def write_expdatafs(self, couplingdoneinfo_dict, outfurl):
    '''
    1:sch_req_id  2:recvedsize  3:slacktime  4:couplingdur  5:couplingdur_relerr  
    6:recvedsizewithf1  7:recvedpercwithf1  8:recvedsizewithf2  9:recvedpercwithf2
    10: joinrr_time 11: schingrr_time 12: sching_overhead
    '''
    outf = open(outfurl, 'w')
    
    for sch_req_id, couplingdoneinfo in couplingdoneinfo_dict.items():
      #1:5
      infostr = str(sch_req_id) + ' ' + \
                str(float(couplingdoneinfo['overall']['recvedsize'])/(1024**2)) + ' ' + \
                str(couplingdoneinfo['overall']['idealtrans_time']) + ' ' + \
                str(couplingdoneinfo['overall']['coupling_dur']) + ' ' + \
                str(couplingdoneinfo['overall']['couplingdur_relerr']) + ' '
      #6:9
      for func,size in couplingdoneinfo['coupling_done']['recvedsizewithfunc_dict'].items():
        infostr += str(float(size)/(1024**2)) + ' ' + str(couplingdoneinfo['overall']['recvedpercentwithfunc_dict'][func]) + ' '
      #10:
      infostr += str(couplingdoneinfo['session_done']['joinrr_time']) + ' ' +\
                 str(couplingdoneinfo['session_done']['schingrr_time']) + ' ' +\
                 str(couplingdoneinfo['overall']['sching_overhead']) + ' '
      #
      infostr += '\n'
      outf.write(infostr)
    #
    outf.close()
  
  def plot_sizerel(self, datafurl, outfurl, nums, yrange):
    pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
    pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
    pipe.stdin.write('set output "%s"\n' % outfurl)
    #pipe.stdin.write('set title "Coupling data size for each session" \n')
    pipe.stdin.write('set xlabel "Session number"\n')
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
    pipe.stdin.write('set xlabel "Session number"\n')
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
    pipe.stdin.write('plot "%s" using 3:xtic(1) w points lc rgb "#000000" title "slack time"' % datafurl + \
                     ', "" using 4 w points lc rgb "#696969" title "coupling time"' + \
                     ', "" using 5 axes x1y2 w points lc rgb "#7F7F7F" title "relative err"\n' )
    #

def main():
  pass

if __name__ == "__main__":
  main()

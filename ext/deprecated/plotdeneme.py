import subprocess,os

def plot_sizerel(datafurl, outfurl, nums, yrange):
  pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
  pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
  pipe.stdin.write('set output "%s"\n' % outfurl)
  pipe.stdin.write('set title "Coupling data size for each session" \n')
  #pipe.stdin.write('set auto x\n')
  pipe.stdin.write('set xrange [-1:%s] \n' % int(nums)+1 )
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

def plot_timerel(datafurl, outfurl, nums, yrange):
  pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
  pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
  pipe.stdin.write('set output "%s"\n' % outfurl)
  pipe.stdin.write('set title "Coupling data size for each session" \n')
  pipe.stdin.write('set xrange [-1:%s] \n' % int(nums)+1 )
  pipe.stdin.write('set yrange [0:%s] \n') % yrange
  pipe.stdin.write('set grid\n')
  pipe.stdin.write('set boxwidth 0.2 absolute\n')
  pipe.stdin.write('set key inside right top vertical Right noreverse noenhanced autotitles nobox\n')
  pipe.stdin.write('set style fill solid border -1\n')
  pipe.stdin.write('set style fill pattern border\n')
  pipe.stdin.write('set samples 11\n')
  pipe.stdin.write('plot "%s" using 2:xtic(1) w boxes fs pattern 1 lc rgb "#000000" title "total size"' % datafurl + \
                   ', "" using 6 w boxes fs pattern 2 lc rgb "#696969" title "fft"' + \
                   ', "" using 8 w boxes fs pattern 3 lc rgb "#7F7F7F" title "upsample-plot"\n' )
  #

def main():
  plot_sizerel('deneme.dat', 'sizerel.png', 3, 110)
  
  
if __name__ == "__main__":
  main()
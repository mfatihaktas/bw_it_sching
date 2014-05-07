import subprocess


def main():
  outfurl = "/home/ubuntu/pox/ext/logs/recvedsize_sid.png"
  datafurl = "/home/ubuntu/pox/ext/logs/deneme.dat"
  
  pipe = subprocess.Popen(['gnuplot'], shell = True, stdin=subprocess.PIPE)
  pipe.stdin.write("set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n")
  pipe.stdin.write('set output "recvedsize_sid.png"\n')
  pipe.stdin.write('set title "Coupling data size for each session" \n')
  #pipe.stdin.write('set auto x\n')
  pipe.stdin.write('set xrange [-1:5] \n')
  pipe.stdin.write('set yrange [0:110] \n')
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
  fformat = '%lf '*8+'%lf'
  pipe.stdin.write('plot "deneme.dat" using 2:xtic(1) "%s" w boxes fs pattern 1 lc rgb "#000000" title "total size"' % fformat + \
                   ', "" using 6 "%s" w boxes fs pattern 2 lc rgb "#696969" title "fft"' % fformat + \
                   ', "" using 8 "%s" w boxes fs pattern 3 lc rgb "#7F7F7F" title "upsample-plot"\n' % fformat )
  
if __name__ == "__main__":
  main()


import subprocess


def main():
  pipe = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
  pipe.stdin.write('set output "/home/ubuntu/pox/ext/logs/plotdeneme.png"\n')
  pipe.stdin.write('set xrange [0:10]; set yrange [-2:2]\n')
  pipe.stdin.write('plot sin(x)\n')
  #pipe.stdin.write('quit\n')

if __name__ == "__main__":
  main()


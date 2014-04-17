//for get_fifodata()
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <assert.h> 
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h> 
#include <math.h>

//#define _POSIX_SOURCE
#include <sys/stat.h>
#include <float.h>

#include <fftw3.h>
//mfa added
#include <stdint.h>
#include <time.h>
#include <sys/time.h>
#include <getopt.h>
#include <pthread.h>

#define MIN(a,b) (((a) < (b)) ? (a) : (b))
#define MAX(a,b) (((a) > (b)) ? (a) : (b))
#define DUMP(fmt, ...) fprintf(stdout, ">>> "fmt"\n", ## __VA_ARGS__)

/*
 * Pre-defined size
 */

#ifndef DIMX
#define DIMX 24
#endif

#ifndef DIMY
#define DIMY 8
#endif

#ifndef SCALE
#define SCALE 8
#endif

/*
 * FFTW
 */

double fftw_abs(const fftw_complex x)
{
    
    return sqrt(x[0]*x[0] + x[1]*x[1]);
}

void do_fft(double r, uint64_t len, size_t dimx, size_t dimy, double*** mat){ //double (*mat)[dimy][dimx]
    double *vec = malloc(sizeof(double) * len);
    fftw_complex *out;
    fftw_plan p0, p1;

    int N = (len/2) + 1;
    out = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * N);

    for (size_t ix = 0; ix < dimx; ix++){
      for (size_t iy = 0; iy < dimy; iy++){
        for (size_t it = 0; it < len; it++)
            vec[it] = mat[it][ix][iy];
          
        p0 = fftw_plan_dft_r2c_1d(len, vec, out, FFTW_ESTIMATE);
        fftw_execute(p0);

        double maxmag = 0.0;
        for (size_t i = 0; i < N; i++)
        {
            double m = fftw_abs(out[i]);
            if (m > maxmag) 
                maxmag = m;
        }

        //DUMP("(%ld, %ld) maxmag: %g", ix, iy, maxmag);

        // Remove noise
        for (size_t i = 0; i < N; i++)
        {
            out[i][0] = trunc(out[i][0]/maxmag/r)*maxmag*r;
            out[i][1] = trunc(out[i][1]/maxmag/r)*maxmag*r;
        }

        p1 = fftw_plan_dft_c2r_1d(len, out, vec, FFTW_ESTIMATE);
        fftw_execute(p1);

        /*
          for (size_t it = 0; it < len; it++)
          {
          printf("mat(%ld,%ld,%ld) %g %g\n", 
          it, iy, ix, mat[it][iy][ix], vec[it]/(double)len);
          }
        */
        /*
        printf("vec=\n");
        for (size_t it = 0; it < len; it++)
        {
          printf("vec[%ld]=%g", it, vec[it]/(double)len);
        }
        */
        // Reconstruct from fft (note: scale)
        for (size_t it = 0; it < len; it++)
            mat[it][ix][iy] = vec[it]/(double)len;

        fftw_destroy_plan(p0);
        fftw_destroy_plan(p1);
      }
    }
    fftw_free(out);
    free(vec);
}

/*
 * Bicubic interpolation functions
 */
double cubicInterpolate(double p[4], double x)
{
  return p[1] + 0.5 * x*(p[2] - p[0] + 
                         x*(2.0*p[0] - 5.0*p[1] + 4.0*p[2] - p[3] + 
                            x*(3.0*(p[1] - p[2]) + p[3] - p[0])));
}

double bicubicInterpolate (double p[4][4], double x, double y) 
{
	double arr[4];
	arr[0] = cubicInterpolate(p[0], y);
	arr[1] = cubicInterpolate(p[1], y);
	arr[2] = cubicInterpolate(p[2], y);
	arr[3] = cubicInterpolate(p[3], y);
	return cubicInterpolate(arr, x);
}
//do_upsampling(size_t dimx, size_t dimy, double X[][dimy],
//                   size_t scale, size_t dimx2, size_t dimy2, double Y[][dimy2]){
void do_upsampling(size_t dimx, size_t dimy, double** X,
                   size_t scale, size_t dimx2, size_t dimy2, double** Y){
  assert(dimy2 == scale*dimy);
  assert(dimx2 == scale*dimx);
  //printf("do_upsampling:: from (x,y)=(%d,%d) to (X,Y)=(%d,%d)\n", dimx,dimy, dimx2,dimy2);
  double p[4][4];

  for (size_t j=0; j<dimy; j++) 
      for (size_t i=0; i<dimx; i++)
          for (size_t jk=0; jk<scale; jk++)
              for (size_t ik=0; ik<scale; ik++)
              {
                  size_t jj = j*scale + jk;
                  size_t ii = i*scale + ik;

                  for (size_t t2=0; t2<4; t2++)
                      for (size_t t1=0; t1<4; t1++)
                      {
                          int64_t o1 = i + t1 - 1;
                          int64_t o2 = j + t2 - 1;

                          if (o1 < 0) o1=0;
                          if (o2 < 0) o2=0;
                          if (o1 > dimx-1) o1 = dimx;
                          if (o2 > dimy-1) o2 = dimy;

                          p[t2][t1] = X[o2][o1];
                      }
                  
                  //DUMP("%ld %ld", jj, ii);
                  Y[ii][jj] = bicubicInterpolate(p, (double)jk/scale, (double)ik/scale);
              }
}

/*
 * Generate PNG plot
 */
void do_plot(const char *outdir, size_t len, size_t dimx, size_t dimy, double*** X)
{
    FILE *pipe = popen("gnuplot", "w");

    double m1=DBL_MAX, m2=-DBL_MAX;

    for (size_t t=0; t<len; t++)
      for (size_t i=0; i<dimx; i++)
        for (size_t j=0; j<dimy; j++){
          if (m1 > X[t][i][j])  m1 = X[t][i][j];
          if (m2 < X[t][i][j])  m2 = X[t][i][j];
        }

    DUMP("[min, max] = [%g, %g]:", m1, m2);

    for (size_t t=0; t<len; t++){
      fprintf(pipe, "set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n");
      fprintf(pipe, "set output '%s/ecei-%07ld.png'\n", outdir, t);
      fprintf(pipe, "set view map\n");
      fprintf(pipe, "set xrange [0:%ld]\n", dimy-1);
      fprintf(pipe, "set yrange [0:%ld] reverse\n", dimx-1);
      fprintf(pipe, "set cbrange [%g:%g]\n", m1, m2);
      fprintf(pipe, "set datafile missing \"nan\"\n");
      fprintf(pipe, "splot '-' matrix with image\n");

      for (size_t i=0; i<dimx; i++){
        for (size_t j=0; j<dimy; j++){
          fprintf(pipe, "%g ", X[t][i][j]);
        }
        fprintf(pipe, "\n");
      }

      fprintf(pipe, "e\n");
      fprintf(pipe, "e\n");
      fflush (pipe);

      //printf ("Press [Enter] to continue . . .");
      //fflush (stdout);
      //getchar ();
    }
}

/* MFA functions */
void print_3dmat(const char* matname, uint64_t len, size_t dimx, size_t dimy, double*** mat){ //double mat[][dimy][dimx]
  printf("print_3dmat:: matname=%s, len=%d, dimx=%d, dimy=%d\n", matname, len, dimx, dimy);
  for (uint64_t t = 0; t < len; t++){
    printf("t=%lld\n", t);
    for (uint64_t i = 0; i < dimx; i++){
      for (uint64_t j = 0; j < dimy; j++){
        printf("%2.3f,", mat[t][i][j]);
      }
      printf("\n");
    }
    printf("\n");
  }
}

void print_2dmat(const char* matname, size_t dimx, size_t dimy, double** mat){ //double mat[dimx][dimy]
  printf("print_2dmat:: matname=%s, dimx=%d, dimy=%d\n", matname, dimx, dimy);
  for (uint64_t i = 0; i < dimx; i++){
    printf("row%d:", i);
    for (uint64_t j = 0; j < dimy; j++){
      printf("%2.2f,", mat[i][j]);
    }
    printf("\n");
  }
}

double** alloc_2dmat(size_t dimx, size_t dimy) {
  double** mat;  
  mat = (double**) malloc(dimx*sizeof(double*));  
  for (int i = 0; i < dimx; i++)  
     mat[i] = (double*) malloc(dimy*sizeof(double));  
  return mat;  
}

#define AFSIZE (sizeof(double) + 1) //+1 for floating point
#define IMGSIZE DIMX*DIMY*AFSIZE //floats
#define NIMGACHUNK 10
#define CHUNKSIZE IMGSIZE*NIMGACHUNK

char* read_chunk(char* basefifoname, int chunk_index){
  char ci_str[10];
  sprintf(ci_str, "%d", chunk_index);
  
  char fifoname[30];
  strcpy(fifoname, basefifoname);
  strcat(fifoname, ci_str);
  //
  //printf("fifoname=%s\n", fifoname);
  
  mkfifo(fifoname, 0666);
  printf("read_chunk:: made fifoname=%s\n", fifoname);
  int fd = open(fifoname, O_RDONLY);
  printf("read_chunk:: opened fifoname=%s\n", fifoname);
  char* chunk = (char*) malloc(CHUNKSIZE+1);
  read(fd, chunk, CHUNKSIZE);
  chunk[CHUNKSIZE]='\0';
  printf("read_chunk:: chunk read from fifoname=%s\n", fifoname);
  close(fd);
  //unlink(fifoname);
  
  return chunk;
}

double*** convert_chunk_to3dmat(char* chunk){
  double*** mat3d = (double***) malloc(NIMGACHUNK*sizeof(double**));
  
  char* chunk_wp = chunk;
  char animgdata[IMGSIZE];
  char afloatdata[AFSIZE+1];
  for (uint64_t i=0; i<NIMGACHUNK; i++){
    memcpy((char*)animgdata, (char*)chunk_wp, IMGSIZE);
    chunk_wp += IMGSIZE;
    char* animgdata_wp = animgdata;
    
    double** mat2d = alloc_2dmat(DIMX, DIMY);
    for (uint64_t j = 0; j < DIMX; j++){
      for (uint64_t k = 0; k < DIMY; k++){
        memcpy((char*)afloatdata, (char*)animgdata_wp, AFSIZE);
        animgdata_wp += AFSIZE;
        
        afloatdata[AFSIZE] = '\0';
        mat2d[j][k] = atof(afloatdata);
      }
    }
    mat3d[i] = mat2d;
  }
  free(chunk);
  
  return mat3d;
}

void write_chunk(char* basefifoname, int chunk_index, size_t chunksize, char* chunk){
  char ci_str[10];
  sprintf(ci_str, "%d", chunk_index);
  
  char fifoname[30];
  strcpy(fifoname, basefifoname);
  strcat(fifoname, ci_str);
  //
  int fd = open(fifoname, O_WRONLY);
  printf("write_chunk:: opened fifoname=%s\n", fifoname);
  write(fd, chunk, chunksize);
  printf("write_chunk:: wrote chunk to fifoname=%s\n", fifoname);
  if (close(fd) != 0){
    perror("Error with close(fd)");
    return;
  }
  unlink(fifoname);
}

char* convert_3dmat_tochunk(double*** mat3d){
  char* chunk = (char*) malloc(CHUNKSIZE+1);
  char* chunk_wp = chunk;
  
  for (uint64_t i=0; i<NIMGACHUNK; i++){
    for (uint64_t j = 0; j < DIMX; j++){
      for (uint64_t k = 0; k < DIMY; k++){
        char afstr[AFSIZE];
        sprintf(afstr, "%2.6f", mat3d[i][j][k]);
        //chunk[i*IMGSIZE+j*DIMY*AFSIZE+i*AFSIZE]
        memcpy((char*)chunk_wp, (char*)afstr, AFSIZE);
        chunk_wp += AFSIZE;
      }
    }
  }
  free(mat3d);
  
  chunk[CHUNKSIZE]='\0';
  return chunk;
}

int STOPFLAG = 0;
void* run_fftproc(){
  printf("run_fftproc:: started\n");
  double ratio = 1.0E-6;
  
  int datafifo_id = 0;
  while (!STOPFLAG){
    char* chunk = read_chunk("fifo/fft_datafifo", datafifo_id);
    //printf("chunk=%s\n", chunk);
    
    double*** mat3d = convert_chunk_to3dmat(chunk);
    //print_3dmat((char*)"mat3d", NIMGACHUNK, DIMX, DIMY, mat3d);
    
    //do_fft(double r, NIMGACHUNK, DIMX, DIMY, mat3d);
    
    char* chunk_ = convert_3dmat_tochunk(mat3d);
    //printf("chunk_=%s\n", chunk_);
    
    write_chunk("fifo/fft_data_fifo", datafifo_id, CHUNKSIZE, chunk_);
    
    datafifo_id += 1;
  }
  
}

int main (int argc, char** argv)
{
  //char* datafname = "deneme.bp";
  char* datafname;
  char* outdir;
  char* compfname;
  int c;
  while (1){
    static struct option long_options[] =
    {
      {"outdir",  required_argument, 0, 'o'},
      {0, 0, 0, 0}
    };
     /* getopt_long stores the option index here. */
     int option_index = 0;
  
     c = getopt_long (argc, argv, "d:",
                      long_options, &option_index);
     /* Detect the end of the options. */
     if (c == -1)
       break;
    
    switch (c){
      case 0:
        printf ("option %s", long_options[option_index].name);
        if (optarg)
          printf (" with arg %s\n", optarg);
          break;
      case 'o':
        outdir = optarg;
        printf ("option -o with value `%s'\n", optarg);
        break;
      case '?':
        /* getopt_long already printed an error message. */
        break;
      default:
        abort ();
    }
  }
  //
  pthread_t fft_thread, upsampling_thread, plotting_thread;

  if (pthread_create( &fft_thread, NULL, &run_fftproc, NULL) != 0){
    perror("Error with pthread_create");
  }
  //run_fftproc();
  printf("Enter\n");
  scanf("...");
  STOPFLAG = 1;
  return 0;
}
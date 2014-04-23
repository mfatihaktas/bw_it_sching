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
#include <sys/socket.h>
#include <netinet/in.h>
#include <stdio.h>
#include <errno.h>

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

double fftw_abs(const fftw_complex x){
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
  //printf("do_fft:: done.\n");
}

/*
 * Bicubic interpolation functions
 */
double cubicInterpolate(double p[4], double x){
  return p[1] + 0.5 * x*(p[2] - p[0] + 
                         x*(2.0*p[0] - 5.0*p[1] + 4.0*p[2] - p[3] + 
                            x*(3.0*(p[1] - p[2]) + p[3] - p[0])));
}

double bicubicInterpolate (double p[4][4], double x, double y) {
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
                          if (o1 > dimx-1) o1 = dimx-1;
                          if (o2 > dimy-1) o2 = dimy-1;

                          p[t1][t2] = X[o1][o2];
                      }
                  
                  //DUMP("%ld %ld", jj, ii);
                  Y[ii][jj] = bicubicInterpolate(p, (double)ik/scale, (double)jk/scale);
              }

  //printf("do_upsampling:: done.\n");
}

/*
 * Generate PNG plot
 */
void do_plot(const char *outdir, size_t len, size_t dimx, size_t dimy, double*** X)
{
    double m1=DBL_MAX, m2=-DBL_MAX;

    for (size_t t=0; t<len; t++)
      for (size_t i=0; i<dimx; i++)
        for (size_t j=0; j<dimy; j++){
          if (m1 > X[t][i][j])  m1 = X[t][i][j];
          if (m2 < X[t][i][j])  m2 = X[t][i][j];
        }

    //DUMP("[min, max] = [%g, %g]:", m1, m2);

    for (size_t t=0; t<len; t++){
      FILE *pipe = popen("gnuplot", "w");
      fprintf(pipe, "set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n");
      fprintf(pipe, "set output '%s/ecei-%03ld.png'\n", outdir, t);
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
  printf("print_3dmat:: matname=%s, len=%zd, dimx=%zd, dimy=%zd\n", matname, len, dimx, dimy);
  for (uint64_t t = 0; t < len; t++){
    printf("t=%lld\n", (long long)t);
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
  printf("print_2dmat:: matname=%s, dimx=%zd, dimy=%zd\n", matname, dimx, dimy);
  for (size_t i = 0; i < dimx; i++){
    printf("row%zd:", i);
    for (size_t j = 0; j < dimy; j++){
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

double*** alloc_3dmat(uint64_t len, size_t dimx, size_t dimy) {
  double*** mat;
  mat = (double***) malloc(len*sizeof(double**));
  for (uint64_t i = 0; i < len; i++)
     mat[i] = alloc_2dmat(dimx, dimy);
  return mat; 
}

#define AFSIZE (sizeof(double) + 1) //+1 for floating point
#define IMGSIZE DIMX*DIMY*AFSIZE //floats
#define NIMGACHUNK 10
#define CHUNKSIZE IMGSIZE*NIMGACHUNK
#define SCALE 8
#define CHUNKSIZE64 SCALE*SCALE*CHUNKSIZE
#define CHUNKSIZE10 10*CHUNKSIZE
#define DIMX_ DIMX*SCALE
#define DIMY_ DIMY*SCALE

//0:fft, 1:upsample, 2:plot, 3:upsampleplot
#define numfs 4
int connfd[numfs];
struct sockaddr_in cliaddr[numfs];
socklen_t clilen[numfs];
int listenfd[numfs];
struct sockaddr_in servaddr[numfs];
int port[numfs] = {8000, 8001, 8002, 8003};

void* init_chunkrw_sock(void* fi){
  int i = atoi((char*)fi);
  
  listenfd[i] = socket(AF_INET,SOCK_STREAM,0);
  if (listenfd[i] == -1){
    printf("init_chunkrw_sock:: Error while creating socket; fi=%d, errno=%d\n",i,errno);
      exit(0);
  }
  int on = 1;
  setsockopt( listenfd[i], SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on) );
  
  bzero(&servaddr[i],sizeof(servaddr[i]));
  servaddr[i].sin_family = AF_INET;
  servaddr[i].sin_addr.s_addr=htonl(INADDR_ANY);
  servaddr[i].sin_port=htons(port[i]);
  bind(listenfd[i],(struct sockaddr *)&servaddr[i],sizeof(servaddr[i]));
  printf("init_chunkrw_socks:: listening over port=%d.\n", port[i]);
  listen(listenfd[i],1);

  clilen[i]=sizeof(cliaddr[i]);
  connfd[i] = accept(listenfd[i],(struct sockaddr *)&cliaddr[i],&clilen[i]);
  printf("init_chunkrw_socks:: for func%d, connfd=%d.\n", i, connfd[i]);
}

char* read_chunk(char* func, int fi, int chunksize){
  char* chunk = (char*) malloc(chunksize);
  int readsize = 0;
  
  char* chunk_wp = chunk;
  char* temp = (char*) malloc(chunksize);
  while (readsize < chunksize){
    int readsize_ = recvfrom(connfd[fi],temp,chunksize,0,(struct sockaddr *)&cliaddr[fi],&clilen[fi]);
    if (readsize_ == 0){
      printf("read_chunk:: %s conn is closed at other side, partial_readsize=%d\n", func, readsize_);
      close(connfd[fi]);
      return NULL;
    }
    else if (readsize_ == -1)
    {
      //error (1, 0, "reading from server: %s", SOCK_STRERROR (SOCK_ERRNO));
      printf("read_chunk:: Error while reading socket; func=%s, errno=%d\n",func,errno);
      exit(0);
    }
    //printf("read_chunk:: func=%s, partial_readsize=%d\n", func, readsize_);
    readsize += readsize_;
    memcpy(chunk_wp, temp, readsize_);
    chunk_wp += readsize_;
  }
  chunk_wp = NULL;
  free(temp);
  
  printf("read_chunk:: func=%s, readsize=%d\n", func, readsize);
  
  //close(connfd);
  
  return chunk;
}

void write_chunk(char* func, int fi, int chunksize, char* chunk){
  sendto(connfd[fi],chunk,chunksize,0,(struct sockaddr *)&cliaddr[fi],sizeof(cliaddr[fi]));
  printf("write_chunk:: func=%s, wrotesize=%d\n", func, chunksize);
  free(chunk);
}

void write_chunk_tofile(char* outdir, char* fname, size_t chunksize, char* chunk){
  char wholefname[50];
  strcpy(wholefname, outdir);
  strcat(wholefname, fname);
  //
  FILE* fp = fopen(wholefname, "w");
  if (fp == NULL){
    perror ("Error opening file");
    return;
  }
  fwrite(chunk,1,chunksize,fp);
  printf("write_chunk_tofile:: wrote to wholefname=%s, chunksize=%zd\n", wholefname, chunksize);
  free(chunk);
}

double*** convert_chunk_to3dmat(int chunksize, char* chunk, size_t len, size_t dimx, size_t dimy){
  double*** mat3d = (double***) malloc(len*sizeof(double**));
  
  char* chunk_wp = chunk;
  size_t imgsize = dimx*dimy*AFSIZE;
  char animgdata[imgsize];
  char afloatdata[AFSIZE+1];
  for (uint64_t i=0; i<len; i++){
    memcpy((char*)animgdata, (char*)chunk_wp, imgsize);
    chunk_wp += imgsize;
    char* animgdata_wp = animgdata;
    
    double** mat2d = alloc_2dmat(dimx, dimy);
    for (uint64_t j = 0; j < dimx; j++){
      for (uint64_t k = 0; k < dimy; k++){
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

char* convert_3dmat_tochunk(size_t len, size_t dimx, size_t dimy, double*** mat3d, int chunksize){
  char* chunk = (char*) malloc(chunksize+1);
  char* chunk_wp = chunk;
  for (size_t i=0; i<len; i++){
    for (size_t j = 0; j < dimx; j++){
      for (size_t k = 0; k < dimy; k++){
        char afstr[AFSIZE];
        sprintf(afstr, "%2.6f", mat3d[i][j][k]);
        //chunk[i*IMGSIZE+j*DIMY*AFSIZE+i*AFSIZE]
        memcpy((char*)chunk_wp, (char*)afstr, AFSIZE);
        chunk_wp += AFSIZE;
        //printf("i=%zd, j=%zd, k=%zd\n", i,j,k);
      }
    }
  }
  
  //free
  for (size_t k=0; k<len; k++){
    for (size_t i = 0; i < dimx; i++){
        free(mat3d[k][i]);
    }
    free(mat3d[k]);
  }
  free(mat3d);
  
  chunk[chunksize]='\0';
  return chunk;
}

double** convert_3dmat_2dmat(size_t len, size_t dimx, size_t dimy, double*** mat3d){
  double** mat2d = alloc_2dmat(dimx, dimy);
  for (size_t i = 0; i < dimx; i++){
    for (size_t j = 0; j < dimy; j++){
      mat2d[i][j] = 0;
    }
  }
  
  for (size_t k=0; k<len; k++){
    for (size_t i = 0; i < dimx; i++){
      for (size_t j = 0; j < dimy; j++){
        mat2d[i][j] += mat3d[k][i][j];
      }
    }
  }
  
  for (size_t i = 0; i < dimx; i++){
    for (size_t j = 0; j < dimy; j++){
      mat2d[i][j] = mat2d[i][j]/len;
    }
  }
  
  //free
  for (size_t k=0; k<len; k++){
    for (size_t i = 0; i < dimx; i++){
        free(mat3d[k][i]);
    }
    free(mat3d[k]);
  }
  free(mat3d);
  
  return mat2d;
}

char* doplot_returnchunk(const char *outdir, size_t len, size_t dimx, size_t dimy, double*** X){
  size_t chunksize = CHUNKSIZE*len;
  char* chunk = (char*)malloc(chunksize);
  char* chunk_wp = chunk;
  //
  double m1=DBL_MAX, m2=-DBL_MAX;
  for (size_t t=0; t<len; t++)
    for (size_t i=0; i<dimx; i++)
      for (size_t j=0; j<dimy; j++){
        if (m1 > X[t][i][j])  m1 = X[t][i][j];
        if (m2 < X[t][i][j])  m2 = X[t][i][j];
      }
  for (size_t t=0; t<len; t++){
    FILE *pipe = popen("gnuplot", "w");
    fprintf(pipe, "set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n");
    fprintf(pipe, "set output '%s/ecei-%03ld.png'\n", outdir, t);
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
    fclose(pipe);
    
    //read plotdata
    char plotname[50];
    char plottailname[8];
    strcpy(plotname, outdir);
    strcat(plotname, (char*)"ecei-");
    sprintf(plottailname, "%03ld", t);
    strcat(plotname, plottailname);
    strcat(plotname, (char*)".png");
    //printf("doplot_returnchunk:: converting %s\n", plotname);
    
    FILE* plotp = fopen(plotname, "r");
    if (plotp == NULL || ferror(plotp)){
      perror ("Error opening file");
      return NULL;
    }
    
    char* plotdata = (char*) malloc(CHUNKSIZE);
    
    fseek(plotp, 0L, SEEK_END);
    size_t plotsize = ftell(plotp);
    //printf("doplot_returnchunk:: plotsize=%zd\n", plotsize);
    fseek(plotp, 0L, SEEK_SET);
    size_t readsize = fread(plotdata,1,plotsize,plotp);
    //printf("doplot_returnchunk:: readsize=%zd\n", readsize);
    if (feof(plotp)){
      printf("doplot_returnchunk:: reading; EOF reached\n");
    }
    else if (ferror(plotp)){
      perror("doplot_returnchunk:: reading; Error occured\n");
    }
    fclose(plotp);
    memcpy(chunk_wp, plotdata, CHUNKSIZE);
    chunk_wp += CHUNKSIZE;
    free(plotdata);
    plotp = NULL;
    plotdata = NULL;
    /*
    if(remove(plotname) != 0)
      perror( "Error deleting file" );
    */
  }
  chunk_wp = NULL;
  //printf("doplot_returnchunk:: done\n");
  return chunk;
}

void do_bigplot(const char *outdir, size_t len, size_t dimx, size_t dimy, double*** X){
  double m1=DBL_MAX, m2=-DBL_MAX;
  for (size_t t=0; t<len; t++)
    for (size_t i=0; i<dimx; i++)
      for (size_t j=0; j<dimy; j++){
        if (m1 > X[t][i][j])  m1 = X[t][i][j];
        if (m2 < X[t][i][j])  m2 = X[t][i][j];
      }
  //
  FILE *pipe = popen("gnuplot", "w");
  fprintf(pipe, "set term png size 2000,1000\n"); //size 2800,1400
  fprintf(pipe, "set output '%s/mal.png'\n", outdir);
  fprintf(pipe, "set multiplot layout %d,%d\n", 2, 5);
  for (size_t t=0; t<len; t++){
    //fprintf(pipe, "set output '%s/mal.png'\n", outdir);
    fprintf(pipe, "set title \"%ld\"\n", t);
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
    fprintf(pipe, "\n");
  }
  fprintf(pipe, "unset multiplot\n");
  fflush(pipe);
  fclose(pipe);
}

char* do_plotfor2dmat_returnchunk(const char *outdir, size_t dimx, size_t dimy, double** X, size_t chunksize){
  char* chunk = (char*)malloc(chunksize);
  //
  double m1=DBL_MAX, m2=-DBL_MAX;
  for (size_t i=0; i<dimx; i++)
    for (size_t j=0; j<dimy; j++){
      if (m1 > X[i][j])  m1 = X[i][j];
      if (m2 < X[i][j])  m2 = X[i][j];
    }

  FILE *pipe = popen("gnuplot", "w");
  fprintf(pipe, "set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n");
  fprintf(pipe, "set output '%s/ecei-for2d.png'\n", outdir);
  fprintf(pipe, "set view map\n");
  fprintf(pipe, "set xrange [0:%ld]\n", dimy-1);
  fprintf(pipe, "set yrange [0:%ld] reverse\n", dimx-1);
  fprintf(pipe, "set cbrange [%g:%g]\n", m1, m2);
  fprintf(pipe, "set datafile missing \"nan\"\n");
  fprintf(pipe, "splot '-' matrix with image\n");

  for (size_t i=0; i<dimx; i++){
    for (size_t j=0; j<dimy; j++){
      fprintf(pipe, "%g ", X[i][j]);
    }
    fprintf(pipe, "\n");
  }

  fprintf(pipe, "e\n");
  fprintf(pipe, "e\n");
  fflush (pipe);
  fclose(pipe);
  
  //free
  for (size_t i=0; i<dimx; i++){
    free(X[i]);
  }
  free(X);
  //
  char plotname[50];
  strcpy(plotname, outdir);
  strcat(plotname, (char*)"ecei-for2d.png");
  //printf("do_plotfor2dmat_returnchunk:: converting %s\n", plotname);
  
  FILE* plotp = fopen(plotname, "r");
  if (plotp == NULL || ferror(plotp)){
    perror ("Error opening file");
    return NULL;
  }
  
  fseek(plotp, 0L, SEEK_END);
  size_t plotsize = ftell(plotp);
  //printf("do_plotfor2dmat_returnchunk:: plotsize=%zd\n", plotsize);
  fseek(plotp, 0L, SEEK_SET);
  size_t readsize = fread(chunk,1,plotsize,plotp);
  //printf("do_plotfor2dmat_returnchunk:: readsize=%zd\n", readsize);
  if (feof(plotp)){
    printf("do_plotfor2dmat_returnchunk:: reading; EOF reached\n");
  }
  else if (ferror(plotp)){
    perror("do_plotfor2dmat_returnchunk:: reading; Error occured\n");
  }
  fclose(plotp);
  
  if(remove(plotname) != 0)
    perror( "Error deleting file" );
  
  return chunk;
}

/* Thread functions */
int STOPFLAG = 0;
void* run_fft(void* stpdst){
  printf("run_fft:: started\n");
  init_chunkrw_sock((void*)"0");
  //
  double ratio = 1.0E-6;
  
  while (!STOPFLAG){
    char* chunk = read_chunk((char*)"fft", 0, CHUNKSIZE);
    if (chunk == NULL){
      printf("run_fft:: chunk is returned NULL! Aborting...\n");
      return NULL;
    }
    //char* chunk = read_chunk(datafifo_basename, datafifo_id, CHUNKSIZE);
    //printf("chunk=%s\n", chunk);
    
    double*** mat3d = convert_chunk_to3dmat(CHUNKSIZE, chunk, NIMGACHUNK, DIMX, DIMY);
    //print_3dmat((char*)"mat3d", NIMGACHUNK, DIMX, DIMY, mat3d);
    
    do_fft(ratio, NIMGACHUNK, DIMX, DIMY, mat3d);
    
    char* chunk_ = convert_3dmat_tochunk(NIMGACHUNK, DIMX, DIMY, mat3d, CHUNKSIZE);
    //printf("chunk_=%s\n", chunk_);
    
    write_chunk((char*)"fft", 0, CHUNKSIZE, chunk_);
    //write_chunk(data_fifo_basename, datafifo_id, CHUNKSIZE, chunk_);
  }
}

void* run_upsample(void* stpdst){
  printf("run_upsample:: started\n");
  init_chunkrw_sock((void*)"1");
  //
  while (!STOPFLAG){
    char* chunk = read_chunk((char*)"upsample", 1, CHUNKSIZE);
    if (chunk == NULL){
      printf("run_upsample:: chunk is returned NULL! Aborting...\n");
      return NULL;
    }
    //char* chunk = read_chunk(datafifo_basename, datafifo_id, CHUNKSIZE);
    //printf("chunk=%s\n", chunk);
    
    double*** mat3d = convert_chunk_to3dmat(CHUNKSIZE, chunk, NIMGACHUNK, DIMX, DIMY);
    //print_3dmat((char*)"mat3d", NIMGACHUNK, DIMX, DIMY, mat3d);
    
    double*** mat3d_ = alloc_3dmat(NIMGACHUNK, DIMX_, DIMY_);
    for (int i=0; i<NIMGACHUNK; i++) {
        do_upsampling(DIMX, DIMY, (double**)mat3d[i], SCALE, 
                      DIMX_, DIMY_, (double**)mat3d_[i]);
    }
    //print_3dmat((char*)"mat3d_", NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    char* chunk_ = convert_3dmat_tochunk(NIMGACHUNK, DIMX_, DIMY_, mat3d_, CHUNKSIZE64);
    //printf("chunk_=%s\n", chunk_);
    
    write_chunk((char*)"upsample", 1, CHUNKSIZE64, chunk_);
    //write_chunk(data_fifo_basename, datafifo_id, CHUNKSIZE64, chunk_);
  }
}

void* run_plot(void* stpdst){
  printf("run_plot:: started\n");
  init_chunkrw_sock((void*)"2");
  //
  while (!STOPFLAG){
    char* chunk = read_chunk((char*)"plot", 2, CHUNKSIZE64);
    if (chunk == NULL){
      printf("run_plot:: chunk is returned NULL! Aborting...\n");
      return NULL;
    }
    //printf("chunk=%s\n", chunk);
    
    double*** mat3d_ = convert_chunk_to3dmat(CHUNKSIZE64, chunk, NIMGACHUNK, DIMX_, DIMY_);
    //print_3dmat((char*)"mat3d_", NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    
    //char* chunk_ = doplot_returnchunk((char*)"plots/", NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    //char* chunk_ = do_bigplot((char*)"plots", NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    double** mat2d_ = convert_3dmat_2dmat(NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    char* chunk_ = do_plotfor2dmat_returnchunk((char*)"plots/", DIMX_, DIMY_, mat2d_, CHUNKSIZE);
    //do_plot((char*)"plots/", NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    
    //char* chunk_ = convert_plots_tochunk((char*)"plots/", (char*)"ecei-", NIMGACHUNK);
    //write_chunk_tofile((char*)"fifo/plot/", (char*)"checkfile.png", CHUNKSIZE, char* chunk){
    
    write_chunk((char*)"plot", 2, CHUNKSIZE, chunk_);
  }
}

void* run_upsampleplot(void* stpdst){
  printf("run_upsampleplot:: started\n");
  init_chunkrw_sock((void*)"3");
  //
  while (!STOPFLAG){
    char* chunk = read_chunk((char*)"upsampleplot", 3, CHUNKSIZE);
    if (chunk == NULL){
      printf("run_upsampleplot:: chunk is returned NULL! Aborting...\n");
      return NULL;
    }
    //printf("chunk=%s\n", chunk);
    //upsample
    double*** mat3d = convert_chunk_to3dmat(CHUNKSIZE, chunk, NIMGACHUNK, DIMX, DIMY);
    
    double*** mat3d_ = alloc_3dmat(NIMGACHUNK, DIMX_, DIMY_);
    for (int i=0; i<NIMGACHUNK; i++) {
        do_upsampling(DIMX, DIMY, (double**)mat3d[i], SCALE, 
                      DIMX_, DIMY_, (double**)mat3d_[i]);
    }
    //plot
    double** mat2d_ = convert_3dmat_2dmat(NIMGACHUNK, DIMX_, DIMY_, mat3d_);
    char* chunk_ = do_plotfor2dmat_returnchunk((char*)"plots/", DIMX_, DIMY_, mat2d_, CHUNKSIZE);
    
    write_chunk((char*)"upsampleplot", 3, CHUNKSIZE, chunk_);
  }
}

int main (int argc, char** argv)
{
  char* stpdst;
  int c;
  while (1){
    static struct option long_options[] =
    {
      {"stpdst",  required_argument, 0, 's'},
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
      case 's':
        stpdst = optarg;
        printf ("option -s with value `%s'\n", optarg);
        break;
      case '?':
        /* getopt_long already printed an error message. */
        break;
      default:
        abort ();
    }
  }
  
  pthread_t fft_thread, upsampleplot_thread;
  if ((pthread_create( &fft_thread, NULL, &run_fft, (void*)stpdst ) != 0) ||
      (pthread_create( &fft_thread, NULL, &run_upsampleplot, (void*)stpdst ) != 0)){
    perror("Error with pthread_create");
  }
  
  /*
  pthread_t fft_thread, upsample_thread, plot_thread, upsampleplot_thread;
  if ((pthread_create( &fft_thread, NULL, &run_fft, (void*)stpdst ) != 0) ||
      (pthread_create( &upsample_thread, NULL, &run_upsample, (void*)stpdst ) != 0) ||
      (pthread_create( &fft_thread, NULL, &run_plot, (void*)stpdst ) != 0) ||
      (pthread_create( &fft_thread, NULL, &run_upsampleplot, (void*)stpdst ) != 0)){
    perror("Error with pthread_create");
  }
  */
  //
  printf("Enter\n");
  scanf("...");
  STOPFLAG = 1;
  for (int i=0; i<numfs; i++){
    close(connfd[i]);
  }
  return 0;
}
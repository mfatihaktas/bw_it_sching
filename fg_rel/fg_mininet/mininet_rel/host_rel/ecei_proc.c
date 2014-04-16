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
//
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

#ifndef DIMLX
#define DIMLX 24
#endif

#ifndef SCALE
#define SCALE 8
#endif


/* Deprecated */
/*
void 2dmat_tofile(FILE * datafilep, size_t dimx, size_t dimy, double** mat){
  for (uint64_t j = 0; j < dimy; j++){
    for (uint64_t i = 0; i < dimx; i++){
      fprintf(datafilep, "%f", mat[j][i]);
    }
  }
}

void dummyfill_mat(uint64_t len, size_t dimy, size_t dimx, double (*mat)[dimy][dimx])
{
  srand(time(NULL));
  for (uint64_t t = 0; t < len; t++){
    for (uint64_t i = 0; i < dimx; i++){
      for (uint64_t j = 0; j < dimy; j++){
        mat[t][j][i] = rand() % 100 + 1;
      }
    }
  }
}

*/

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
        printf("%2.2f,", mat[t][i][j]);
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

double*** alloc_3dmat(uint64_t len, size_t dimx, size_t dimy) {
  double*** mat;
  mat = (double***) malloc(len*sizeof(double**));
  for (uint64_t i = 0; i < len; i++)
     mat[i] = alloc_2dmat(dimx, dimy);
  return mat; 
}

#define DSIZE (sizeof(double) + 1) //+1 for floating point
#define IMGSIZE DIMX*DIMY //doubles

char* get_next2dmatdata(FILE * datafilep){
  /*
  int size = DSIZE*IMGSIZE+1;
  printf("DSIZE=%d\n", DSIZE);
  printf("IMGSIZE=%d\n", IMGSIZE);
  printf("size=%d\n", size);
  char* buffer = (char*) malloc(size-1);
  fgets(buffer, size, datafilep);
  buffer[size] = '\0';
  printf("get_next2dmatdata:: buffer=\n%s\n", buffer);
  *imgdata = buffer;
  */
  int size = DSIZE*IMGSIZE+1;
  char* buffer = (char*) malloc(size-1);
  size_t result = fread((char*)buffer,DSIZE,IMGSIZE,datafilep);
  if (result != IMGSIZE){
    fputs ("Reading error\n",stderr); exit (0);
  }
  buffer[size] = '\0';
  //printf("get_next2dmatdata:: buffer=\n%s\n", buffer);
  return buffer;
}

double** get_next2dmat(FILE * datafilep, size_t dimx, size_t dimy){
  char* imgdata = get_next2dmatdata(datafilep);
  char* man_imgdata = imgdata;
  //printf("get_next2dmat:: imgdata=\n%s\n", imgdata);
  
  //double** temp_mat = malloc(sizeof(double)*IMGSIZE);
  double** mat = alloc_2dmat(dimx, dimy);
  char temp[DSIZE+1];
  
  int counter = 0;
  for (uint64_t i = 0; i < DIMX; i++){
    for (uint64_t j = 0; j < DIMY; j++){
      memcpy( (char*)temp, (char*)man_imgdata, DSIZE );
      //strncpy(temp, manp_imgdata, DSIZE);
      temp[DSIZE] = '\0';
      man_imgdata += DSIZE;
      //printf("(i,j)=(%d, %d); counter=%d, temp=s:%s, f:%f\n", i,j, counter, temp,atof(temp));
      mat[i][j] = atof(temp);
      counter++;
    }
  }
  free(imgdata);
  return mat;
}

double*** get_next3dmat(FILE * datafilep, uint64_t len, size_t dimx, size_t dimy){
  double*** mat = (double***) malloc(len*sizeof(double**));
  
  for (uint64_t i=0; i<len; i++){
    mat[i] = get_next2dmat(datafilep, dimx, dimy);
  }
  
  return mat;
}

void do_pipeline(uint64_t len, size_t dimx, size_t dimy, FILE* datafilep){
  rewind(datafilep);
  double*** matX = get_next3dmat(datafilep, len, dimx, dimy);
  //print_3dmat("matX", len, dimx, dimy, matX);
  
  // Step #1 - FFT
  printf(">>> fft\n");
  double ratio = 1.0E-6; //1.0E-1;
  do_fft(ratio, len, dimx, dimy, matX);
  //print_3dmat("matX", len, dimx, dimy, matX);
  /*
  // Step #2 - Upsampling
  printf(">>> resize\n");
  int step = 1;
  int leny = len/step;
  
  //double (*matY)[dimx*SCALE][dimy*SCALE];
  //matY = malloc (leny * sizeof(*matY));
  size_t DIMX_ = dimx*SCALE;
  size_t DIMY_ = dimy*SCALE;
  double*** matY =  alloc_3dmat(leny, dimx*SCALE, dimy*SCALE);
  for (int i=0; i<leny; i++) {
      do_upsampling(dimx, dimy, (double**)matX[i*step], SCALE, 
                    DIMX_, DIMY_, (double**)matY[i]);
  }
  //print_3dmat("matY", leny, DIMX_, DIMY_, (double***)matY);
  
  // Step #3 - Plotting
  printf(">>> plot\n");
  char* outdir = "images";
  
  do_plot(outdir, len, DIMX_, DIMY_, matY);
  //do_plot(outdir, len, dimx, dimy, matX);
  free(matY);
  */
  free(matX);
}

void deneme(size_t len, FILE* datafilep){
  struct timeval ts, te;
  double elapsed_t;
  printf("deneme:: started.\n");
  
  gettimeofday(&ts, NULL);
  do_pipeline(len, DIMX, DIMY, datafilep);
  gettimeofday(&te, NULL);
    
  elapsed_t = (te.tv_sec - ts.tv_sec) * 1000.0;      // sec to ms
  elapsed_t += (te.tv_usec - ts.tv_usec) / 1000.0;   // us to ms
  elapsed_t = elapsed_t/1000.0; //msec to sec
  printf("deneme:: done, elapsed_t=%fsec\n", elapsed_t);
}

void comp_analysis(const char* compfdir, const char* compfname, FILE* datafilep){
  char whole_compfname[100];
  strcpy(whole_compfname, compfdir);
  strcat(whole_compfname, compfname);
  
  printf("comp_analysis:: whole_compfname=%s\n", whole_compfname);
  
  FILE* compfilep = fopen (whole_compfname,"w+");
  if (compfilep == NULL){
    perror ("Error opening file");
    exit(0);
  }
  //
  struct timeval ts, te;
  double elapsed_t;
  printf("comp_analysis:: started.\n");
  
  //do whatever...
  uint64_t len;
  for (len = 100; len<10000; len+=100){
    printf("for len=%d\n", len);
    gettimeofday(&ts, NULL);
    //
    do_pipeline(len, DIMX, DIMY, datafilep);
    //
    gettimeofday(&te, NULL);
    
    elapsed_t = (te.tv_sec - ts.tv_sec) * 1000.0;      // sec to ms
    elapsed_t += (te.tv_usec - ts.tv_usec) / 1000.0;   // us to ms
    elapsed_t = elapsed_t/1000.0; //msec to sec
    printf("elapsed_t=%fsec\n", elapsed_t);
    
    fprintf(compfilep, "%d %f\n", len, elapsed_t);
  }
  fclose(compfilep);
  printf("comp_analysis:: ended.\n");
  
  //get_companalysisplot(data_out_dir, "fft.dat", "fft");
}

void get_companalysisplot(const char* data_out_dir, const char* datafname, const char* funcname){
  printf("get_companalysisplot:: started\n");
  
  FILE *pipe = popen("gnuplot", "w");
  fprintf(pipe, "set term png enhanced font '/usr/share/fonts/liberation/LiberationSans-Regular.ttf' 12\n");
  fprintf(pipe, "set output '%s/%s_comp.png'\n", data_out_dir, funcname);
  fprintf(pipe, "set title \"%s completion time vs. len\"\n", funcname);
  fprintf(pipe, "set xtic auto\n");
  fprintf(pipe, "set ytic auto\n");
  fprintf(pipe, "plot \"%s/%s\" using 1:2 title 'Column' with linespoints", data_out_dir, datafname);
  
  //fprintf(pipe, "e\n");
  fflush (pipe);
  
  printf("get_companalysisplot:: ended\n");
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
      {"datafname",  required_argument, 0, 'd'},
      {"outdir",  required_argument, 0, 'o'},
      {"compfname",  required_argument, 0, 'c'},
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
      case 'd':
        datafname = optarg;
        printf ("option -d with value `%s'\n", optarg);
        break;
      case 'o':
        outdir = optarg;
        printf ("option -o with value `%s'\n", optarg);
        break;
      case 'c':
        compfname = optarg;
        printf ("option -c with value `%s'\n", optarg);
        break;
      case '?':
        /* getopt_long already printed an error message. */
        break;
      default:
        abort ();
    }
  }
  
  FILE* datafilep = fopen (datafname , "r");
  if (datafilep == NULL){
    perror ("Error opening file");
    exit(0);
  }
  
  
  struct timeval ts, te;
  double elapsed_t;
  
  gettimeofday(&ts, NULL);
  deneme(50000, datafilep);
  gettimeofday(&te, NULL);
    
  elapsed_t = (te.tv_sec - ts.tv_sec) * 1000.0;      // sec to ms
  elapsed_t += (te.tv_usec - ts.tv_usec) / 1000.0;   // us to ms
  elapsed_t = elapsed_t/1000.0; //msec to sec
  printf("done, celapsed_t=%fsec\n", elapsed_t);
  
  //comp_analysis(outdir, compfname, datafilep);
  
  //char* data_out_dir = "/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/companalysis";
  //get_companalysisplot(outdir, compfname, "fft");
  
  /*
  double** matX;
  matX = get_next2dmat(datafilep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  free(matX);
  
  matX = get_next2dmat(datafilep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  free(matX);
  */
  /*
  double** matX = get_next2dmat(datafilep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  
  double** matY = alloc_2dmat(DIMX*SCALE, DIMY*SCALE);
  
  do_upsampling(DIMX, DIMY, matX, SCALE,
                DIMX*SCALE, DIMY*SCALE, matY);
  printf(">>>after upsampling\n");
  print_2dmat(DIMX*SCALE, DIMY*SCALE, (double**)matY);
  */
  
  /*
  uint64_t len = 20;
  double*** matX = get_next3dmat(datafilep, len, DIMX, DIMY);
  //print_3dmat("matX", len, DIMX, DIMY, matX);
  
  // Step #1 - FFT
  double ratio = 1.0E-6; //1.0E-1;
  do_fft(ratio, len, DIMX, DIMY, matX);
  //print_3dmat("matX", len, DIMX, DIMY, matX);
  
  // Step #2 - Upsampling
  printf(">>> resize\n");
  int step = 1;
  int leny = len/step;
  
  //double (*matY)[DIMX*SCALE][DIMY*SCALE];
  //matY = malloc (leny * sizeof(*matY));
  size_t DIMX_ = DIMX*SCALE;
  size_t DIMY_ = DIMY*SCALE;
  double*** matY =  alloc_3dmat(leny, DIMX*SCALE, DIMY*SCALE);
  for (int i=0; i<leny; i++) {
      do_upsampling(DIMX, DIMY, (double**)matX[i*step], SCALE, 
                    DIMX_, DIMY_, (double**)matY[i]);
  }
  //print_3dmat("matY", leny, DIMX_, DIMY_, (double***)matY);
  
  // Step #3 - Plotting
  printf(">>> plot\n");
  char* outdir = "images";
  
  do_plot(outdir, len, DIMX_, DIMY_, matY);
  //do_plot(outdir, len, DIMX, DIMY, matX);
  free(matX);
  free(matY);
  */
  
  return 0;
}

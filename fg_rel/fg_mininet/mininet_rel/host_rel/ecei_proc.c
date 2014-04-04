#include <assert.h> 
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h> 
#include <math.h>

#define _POSIX_SOURCE
#include <sys/stat.h>
#include <float.h>

#include <fftw3.h>
//mfa added
#include <stdint.h>
#include <time.h>
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
void 2dmat_tofile(FILE * filep, size_t dimx, size_t dimy, double** mat){
  for (uint64_t j = 0; j < dimy; j++){
    for (uint64_t i = 0; i < dimx; i++){
      fprintf(filep, "%f", mat[j][i]);
    }
  }
}

double*** alloc_3dmat(uint64_t len, size_t dimx, size_t dimy) {
  double*** mat;
  mat = (double***) malloc(len*sizeof(double**));
  for (uint64_t i = 0; i < len; i++)
     mat[i] = alloc_2dmat(dimx, dimy);
  return mat; 
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

    printf(">>> fft\n");
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
                   size_t scale, size_t dimx2, size_t dimy2, double Y[][dimy2]){
    assert(dimy2 == scale*dimy);
    assert(dimx2 == scale*dimx);

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
                    Y[jj][ii] = bicubicInterpolate(p, (double)jk/scale, (double)ik/scale);
                }
}

/* MFA functions */
void print_3dmat(uint64_t len, size_t dimx, size_t dimy, double*** mat){ //double mat[][dimy][dimx]
  printf("print_3dmat:: len=%d, dimx=%d, dimy=%d\n", len, dimx, dimy);
  for (uint64_t t = 0; t < len; t++){
    printf("t=%lld\n", t);
    for (uint64_t i = 0; i < dimx; i++){
      for (uint64_t j = 0; j < dimy; j++){
        printf("%2.2f , ", mat[t][i][j]);
      }
      printf("\n");
    }
    printf("\n");
  }
}

void print_2dmat(size_t dimx, size_t dimy, double** mat){ //double mat[dimx][dimy]
  printf("print_2dmat:: dimx=%d, dimy=%d\n", dimx, dimy);
  for (uint64_t i = 0; i < dimx; i++){
    for (uint64_t j = 0; j < dimy; j++){
      printf("%2.2f , ", mat[i][j]);
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

#define DSIZE (sizeof(double) + 1) //+1 for floating point
#define IMGSIZE DIMX*DIMY //doubles

char* get_next2dmatdata(FILE * filep){
  /*
  int size = DSIZE*IMGSIZE+1;
  printf("DSIZE=%d\n", DSIZE);
  printf("IMGSIZE=%d\n", IMGSIZE);
  printf("size=%d\n", size);
  char* buffer = (char*) malloc(size-1);
  fgets(buffer, size, filep);
  buffer[size] = '\0';
  printf("get_next2dmatdata:: buffer=\n%s\n", buffer);
  *imgdata = buffer;
  */
  int size = DSIZE*IMGSIZE+1;
  char* buffer = (char*) malloc(size-1);
  size_t result = fread((char*)buffer,DSIZE,IMGSIZE,filep);
  if (result != IMGSIZE){
    fputs ("Reading error\n",stderr); exit (0);
  }
  buffer[size] = '\0';
  //printf("get_next2dmatdata:: buffer=\n%s\n", buffer);
  return buffer;
}

double** get_next2dmat(FILE * filep, size_t dimx, size_t dimy){
  char* imgdata = get_next2dmatdata(filep);
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

double*** get_next3dmat(FILE * filep, uint64_t len, size_t dimx, size_t dimy){
  //double*** mat = alloc_3dmat(len, dimx, dimy);
  double*** mat = (double***) malloc(len*sizeof(double**));
  
  for (uint64_t i=0; i<len; i++){
    mat[i] = get_next2dmat(filep, dimx, dimy);
  }
  
  return mat;
}

int main (int argc, char ** argv)
{
  char* fname = "deneme.bp";
  //char* fname = "/media/portable_large/ecei_data.bp";
  
  FILE* filep = fopen (fname , "r");
  if (filep == NULL){
    perror ("Error opening file");
    exit(0);
  }
  /*
  double** matX;
  matX = get_next2dmat(filep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  free(matX);
  
  matX = get_next2dmat(filep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  free(matX);
  */
  
  double** matX = get_next2dmat(filep, DIMX, DIMY);
  print_2dmat(DIMX, DIMY, matX);
  
  //double** matY = alloc_2dmat(DIMX*SCALE, DIMY*SCALE);
  double matY[DIMX*SCALE][DIMY*SCALE];
  do_upsampling(DIMX, DIMY, matX, SCALE, 
                DIMX*SCALE, DIMY*SCALE, matY);
  print_2dmat(DIMX*SCALE, DIMY*SCALE, matX);
  /*
  uint64_t len = 5;
  double*** matX = get_next3dmat(filep, len, DIMX, DIMY);
  print_3dmat(len, DIMX, DIMY, matX);
  
  // Step #1 - FFT
  double ratio = 1.0E-1; //1.0E-6;
  do_fft(ratio, len, DIMX, DIMY, matX);
  //print_3dmat(len, DIMX, DIMY, matX);
  
  // Data to write
  int NX, NY;
  double *data;
  
  NX = DIMX;
  NY = DIMY;
  len = len;
  
  data = (double *)matX;
  
  // Step #2 - Upsampling
  
  printf(">>> resize\n");
  int step = 1;
  DUMP("step : %d", step);
  int leny = len/step;
  double (*matY)[DIMX*SCALE][DIMY*SCALE];
  matY = malloc (leny * sizeof(*matY));
  
  
  for (int i=0; i<leny; i++) {
      do_upsampling(DIMX, DIMY, matX[i*step], SCALE, 
                    DIMX*SCALE, DIMY*SCALE, matY[i]);
  
      print_2dmat(DIMX*SCALE, DIMY*SCALE, (double**)matY[i]);
  }
  NX = DIMX*SCALE;
  NY = DIMY*SCALE;
  len = leny;
  data = (double *)matY;
  
  //print_3dmat(leny, NX, NY, (double***)matY);
  
  free(matX);
  free(matY);
  */
  
  /*
  //
  
  int rank, size;
  int step = 100;
  double ratio = 1.0E-1; //1.0E-6;
  
  double (*mat)[DIMY][DIMX];
  //Step #0 - Load data
  // ECEI data layout: len-by-DIMY-by-DIMX
  uint64_t len = 10;
  mat = malloc (len * sizeof(*mat));
  dummyfill_mat(len, DIMY, DIMX, mat);
  
  print_3dmat(len, DIMY, DIMX, mat);
  //Step #1 - FFT
  do_fft(ratio, len, DIMY, DIMX, mat);
  
  print_3dmat(len, DIMY, DIMX, mat);
  //do_background(1000, step, len, DIMY, DIMX, mat);
  //Step #2 - Resize
  
  //Step #3 - Plotting
  */
  return 0;
}

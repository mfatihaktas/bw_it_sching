/* fscanf example */
#include <stdio.h>
#include <time.h>
#include <stdlib.h>

#define FILESIZE 100000 //doubles

int main ()
{
  time_t t;
  FILE * pFile;
  char* fname = (char*) "deneme.bp"; //"/cac/u01/mfa51/Desktop/deneme.bp";
  
  ///*
  pFile = fopen (fname,"w+");
  
  srand((unsigned) time(&t));
  
  unsigned int i;
  for (i=0; i<FILESIZE; i++){
    fprintf(pFile, "%f", (double)(rand() % 90 + 10));
  }
  rewind (pFile);
  //float f1, f2;
  //fscanf (pFile, "%f", &f1);
  //fscanf (pFile, "%f", &f2);
  fclose (pFile);
  //printf ("f1=%f\nf2=%f",f1,f2);
  //*/
  
  /*
  pFile=fopen(fname,"r");
  if(pFile==NULL)
    return 1;
  
  int size = 1*sizeof(double);
  //double* buffer = (double*) malloc(sizeof(double)*size);
  char* buffer = (char*) malloc(size);
  
  size_t result = fread(buffer,1,size,pFile);
  if (result != size){
    fputs ("Reading error\n",stderr); exit (0);
  }
  
  printf(">>>buffer=\n");
  printf("%s\n",buffer);
  */
  return 0;
}
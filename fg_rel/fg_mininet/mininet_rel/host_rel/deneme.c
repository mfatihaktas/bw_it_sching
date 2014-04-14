/* fscanf example */
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define BUFFSIZE 10 //1024

char* get_data(FILE* datafp){
  char* buffer = (char*) malloc(BUFFSIZE+1);
  size_t numcharsread = fread((char*)buffer,1,BUFFSIZE,datafp);
  //printf("get_data:: numcharsread=%d", numcharsread);
  if (numcharsread != BUFFSIZE){
    fputs ("Reading error\n",stderr); exit (0);
  }
  buffer[BUFFSIZE]='\0';
  return buffer;
}

int main ()
{
  /*
  FILE* read_fp = fopen (stdin , "r");
  if (read_fp == NULL){
    perror ("Error opening file");
    exit(0);
  }
  */
  printf("here\n");
  char* stdin_data = get_data((FILE*) stdin);
  printf("stdin_data=%s\n", stdin_data);
  
  return 0;
}
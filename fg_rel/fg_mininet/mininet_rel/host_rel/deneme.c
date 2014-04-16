//for get_stdindata()
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
//for get_fifodata()
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
//
#define BUFFSIZE 10 //1024

char* get_stdindata(FILE* datafp){
  char* buffer = (char*) malloc(BUFFSIZE+1);
  size_t numcharsread = fread((char*)buffer,1,BUFFSIZE,datafp);
  //printf("get_stdindata:: numcharsread=%d", numcharsread);
  if (numcharsread != BUFFSIZE){
    fputs ("Reading error\n",stderr); exit (0);
  }
  buffer[BUFFSIZE]='\0';
  return buffer;
}

char* get_fifodata(int fd){
  char* buf = (char*) malloc(BUFFSIZE+1);
  read(fd, buf, BUFFSIZE);
  buf[BUFFSIZE]='\0';
  
  return buf;
}


int main ()
{
  //char* stdin_data = get_stdindata((FILE*) stdin);
  //printf("stdin_data=%s\n", stdin_data);
  
  int fd;
  char* myfifo = (char*) "myfifo";
  mkfifo(myfifo, 0666);
  fd = open(myfifo, O_RDONLY);
  
  char* fifodata = get_fifodata(fd);
  printf("fifodata=%s\n", fifodata);
  close(fd);
  
  return 0;
}
CC = gcc
OPTS = 

# 
.PHONY: all clean

IDIR = include
ODIR = obj

INC = -I$(IDIR)
LIB = -lm

APPS := sim

all: ${APPS}

sim: $(ODIR)/poisson_simulation_prb.o $(ODIR)/poisson_simulation.o
	$(CC) $(OPTS) -o $@ $^ $(INC) $(LIB)
	
$(ODIR)/%.o: %.c
	$(CC) $(OPTS) -c -o $@ $< $(INC) $(LIB)

clean:
	rm -f $(ODIR)/*.o ${APPS} *.txt
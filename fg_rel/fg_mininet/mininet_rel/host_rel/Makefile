FFTWDIR=/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/ecei_proc

eceiproc_sf=ecei_proc.c
eceiproc_tf=eceiproc

eceiproc: $(eceiproc_sf)
		gcc -std=gnu99 -o $(eceiproc_tf) $< -L$(FFTWDIR)/lib -I$(FFTWDIR)/include -lfftw3 -lm

clean:
		rm -rf *o $(eceiproc_tf)

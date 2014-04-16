FFTWDIR=/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/fftw3
#FFTWDIR=/media/mehmet/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/fftw3

eceiproc_sf=ecei_proc.c
eceiproc_tf=eceiproc
eceiproc2_sf=ecei_proc2.c
eceiproc2_tf=eceiproc2

eceiproc: $(eceiproc_sf)
		gcc -std=gnu99 -o $(eceiproc_tf) $< -L$(FFTWDIR)/lib -I$(FFTWDIR)/include -lfftw3 -lm

eceiproc2: $(eceiproc2_sf)
		gcc -std=gnu99 -o $(eceiproc2_tf) $< -L$(FFTWDIR)/lib -I$(FFTWDIR)/include -lfftw3 -lm

clean:
		rm -rf *o $(eceiproc_tf) $(eceiproc2_tf)

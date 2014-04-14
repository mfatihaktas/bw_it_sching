FFTWDIR=/media/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/ecei_proc
#FFTWDIR=/media/mehmet/portable_large/cb_sim_rel/fg_rel/fg_mininet/mininet_rel/host_rel/ecei_proc

eceiproc_sf=ecei_proc.c
eceiproc_tf=eceiproc
mymodule_sf=myModule.c
mymodule_tf=myModule.dylib

eceiproc: $(eceiproc_sf)
		gcc -std=gnu99 -o $(eceiproc_tf) $< -L$(FFTWDIR)/lib -I$(FFTWDIR)/include -lfftw3 -lm

mymodule: $(mymodule_sf)
		gcc -dynamiclib -I/usr/include/python2.3/ -lpython2.3 -o $(mymodule_tf) $<

clean:
		rm -rf *o $(eceiproc_tf) $(mymodule_tf_tf)

#!/bin/bash
make runfv
./runfv
#run-parts --regex '^r.*sh$' --arg 'cli' ~/git_repo/pox
#./pox.py openflow.of_01 --port=8001 my_controller

#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Create (if not exists) directory of IPs
ips_dir="$DETER_HOME/ips"
rm -r $ips_dir
mkdir -p $ips_dir

# Write topology file
in_topo="$ips_dir/topo.ns"
(cat $DETER_HOME/topologies/coap_topology.ns) > $in_topo

# Prepare output file of ips
ipsfile="$ips_dir/ips.txt"
touch $ipsfile
python storeips_helper.py -i $in_topo -o $ipsfile
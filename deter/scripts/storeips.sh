#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Create (if not exists) directory of IPs and clean it
mkdir -p $IPS_HOME
rm $IPS_HOME/*

# Copy current experiment's topology file
(cat $DETER_HOME/topologies/coap_topology.ns) > $IPS_TOPO

# Prepare output file of ips
touch $IPS_FILE
python storeips_helper.py -i $IPS_TOPO -o $IPS_FILE
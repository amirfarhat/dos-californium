#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Copy the ifconfig
ifconfig_file="$TMP/ifconfig.txt"
ifconfig > $ifconfig_file

# Record short hostname and 
my_hostname=$(hostname | awk '{split($0, a, "."); print a[1]}')
my_ip=$(bash $SCRIPTS_HOME/fetchips.sh proxy)

# Find all interfaces which hold my IP address and collect them comma-separated
my_interfaces=$(\
  grep --no-group-separator -B 1 $my_ip $ifconfig_file \
  | sed -n 'p;n' \
  | awk 'BEGIN { ORS="," } {split($0,a,":"); print a[1];}' \
  | sed 's/.$//' \
)

# Output host to interface mapping
echo "$my_hostname $my_interfaces"
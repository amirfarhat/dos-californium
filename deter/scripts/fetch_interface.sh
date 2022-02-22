#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Record short hostname
my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')

# Fetch the interface associated with the above hostname
interface=$(\
  grep "$my_hostname" $INTERFACES_FILE \
  | awk '{ ORS="" } \
         { split($0, a, " "); print a[2]; }'
)

# Output the interface without a newline at the end
echo -n "$interface"
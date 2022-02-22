#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Create and wipe the contents of the file which will store interface information
touch $INTERFACES_FILE
rm $INTERFACES_FILE
touch $INTERFACES_FILE

for host_name in ${HOST_NAMES[@]}; do
  # Fetch the host-to-interface mapping from the host
  interface_mapping=$(ssh $RUN_USER@$host_name "$SCRIPTS_HOME/get_interfaces.sh")
  
  # Expect one "useful" interface per host on the deter virtual network
  num_commas=$(echo "$interface_mapping" | tr -cd "," | wc -c)
  if [[ $num_commas -gt 0 ]]; then
    echo "Found more than one interface per host: $interface_mapping"
    exit 1
  fi

  # Append this interface mapping to the interfaces file
  echo "$interface_mapping" >> $INTERFACES_FILE
done
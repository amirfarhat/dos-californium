#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

usage() {
  cat <<EOM
  Usage:
    $(basename $0) [OPTIONAL src] dst
    src - the host name from the perspective of which the requester wishes to get the ip address for the hostname `dst`
    dst - the host name whose IP address if of interest to fetching
EOM
  exit 1
}

# Parse inputs
src=""
dst=""
if [[ ! -z $1 ]] && [[ ! -z $2 ]]; then
  # Case two inputs
  src=$1
  dst=$2
elif [[ ! -z $1 ]]; then
  # Case one input
  src=`hostname | awk -F. '{print $1}'` # src is current host
  dst=$1
else
  # Case no inputs
  usage
fi

cd $DETER_HOME
python $SCRIPTS_HOME/fetchips_helper.py --src $src --dst $dst --ipsfile $IPS_FILE
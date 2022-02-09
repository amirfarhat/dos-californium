#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/californium/deter/scripts/config.sh
source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Options
while getopts ":v" opt; do
  case "$opt" in
    "v") _V=1;;
  esac
done

# Debug printer
function log () {
  if [[ $_V -eq 1 ]]; then
    printf "$@"
  fi
}

sudo mkdir -p $TMP_DATA

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running attacker_tcpdump...\n"
  screen -d -m sudo $BIN_HOME/run_tcpdump.sh attacker
fi

log "Running attacker_flood...\n"
screen -d -m sudo $BIN_HOME/attacker_flood.sh

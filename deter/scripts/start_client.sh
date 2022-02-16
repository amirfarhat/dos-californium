#!/bin/bash

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

log "Preparing client configuration..."
bash $BIN_HOME/prepare_californium_configuration.sh $CLIENT_PROPERTIES_FILE $HOME/$CLIENT_PROPERTIES_FILE_NAME "${CLIENT_PROPERTIES[*]}" COAP.
log "Done!"

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running client tcpdump...\n"
  screen -d -m sudo $BIN_HOME/run_tcpdump.sh client
fi

log "Running client...\n"
screen -d -m sudo $BIN_HOME/client_run.sh
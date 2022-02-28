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

OPLOG=$TMP_DATA/proxy_ops.log
sudo touch $OPLOG

# Determine properties file based on DTLS toggle
properties_file=""
modified_properties_file=""
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  properties_file="$DTLS_PROXY_PROPERTIES_FILE"
  modified_properties_file="$HOME/$DTLS_PROXY_PROPERTIES_FILE_NAME"
else
  properties_file="$PROPERTIES_FILE"
  modified_properties_file="$HOME/$PROPERTIES_FILE_NAME"
fi

log "Preparing proxy configuration..."
bash $BIN_HOME/prepare_californium_configuration.sh $properties_file $modified_properties_file "${PROXY_PROPERTIES[*]}" DOS.
log "Done!\n"

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running proxy tcpdump...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/run_tcpdump.sh
fi

if [[ $MONITOR_PROXY_CPU -eq 1 ]]; then
  log "Running proxy CPU monitor...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/monitor_cpu.sh $PROXY_DURATION $CPU_SAMPLING_INTERVAL $TMP_DATA/$PROXY_CPU_FILENAME
fi

if [[ $MONITOR_PROXY_MEMORY -eq 1 ]]; then
  log "Running proxy memory monitor...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/monitor_memory.sh $PROXY_DURATION $TMP_DATA/$PROXY_MEMORY_FILENAME
fi

log "Running proxy...\n"
sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/proxy_run.sh
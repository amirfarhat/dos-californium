#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Ensure the server goes through setup
bash $SCRIPTS_HOME/node_setup.sh

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
  log "Running origin_server tcpdump...\n"
  screen -d -m sudo $BIN_HOME/run_tcpdump.sh origin_server
fi

if [[ $MONITOR_ORIGIN_SERVER_CPU -eq 1 ]]; then
  log "Running origin server CPU monitor...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/monitor_cpu.sh $ORIGIN_SERVER_DURATION $CPU_SAMPLING_INTERVAL $TMP_DATA/$ORIGIN_SERVER_CPU_FILENAME
fi

if [[ $MONITOR_ORIGIN_SERVER_MEMORY -eq 1 ]]; then
  log "Running origin server memory monitor...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/monitor_memory.sh $ORIGIN_SERVER_DURATION $TMP_DATA/$ORIGIN_SERVER_MEMORY_FILENAME
fi

log "Running origin server...\n"
screen -d -m sudo $BIN_HOME/origin_server_run.sh
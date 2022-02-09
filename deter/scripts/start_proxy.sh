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

log "Preparing proxy configuration..."
$BIN_HOME/prepare_proxy_configuration.sh
log "Done!"

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running proxy tcpdump...\n"
  sudo screen -c $UTILS_HOME/oplog.conf -d -m -L sudo $BIN_HOME/run_tcpdump.sh proxy

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
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

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')
sudo mkdir -p $TMP_DATA

# Create empty attacker ops log
OPLOG="$TMP_DATA/${my_hostname}_ops.log"
sudo touch $OPLOG
sudo rm $OPLOG
sudo touch $OPLOG

# Create attacker ops log configuration
OPLOG_CONF="$HOME/$my_hostname.oplog.conf"
sudo touch $OPLOG_CONF
sudo rm $OPLOG_CONF
sudo touch $OPLOG_CONF
echo "logfile $OPLOG"  >> $OPLOG_CONF
echo "logfile flush 1" >> $OPLOG_CONF
echo "log on"          >> $OPLOG_CONF

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running attacker_tcpdump...\n"
  sudo screen -c $OPLOG_CONF -d -m -L sudo $BIN_HOME/run_tcpdump.sh
fi

log "Running attacker_flood...\n"
sudo screen -c $OPLOG_CONF -d -m -L sudo $BIN_HOME/attacker_flood.sh

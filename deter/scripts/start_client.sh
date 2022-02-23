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

# Create empty client ops log
OPLOG="$TMP_DATA/${my_hostname}_ops.log"
sudo touch $OPLOG
sudo rm $OPLOG
sudo touch $OPLOG

# Create client ops log configuration
OPLOG_CONF="$HOME/$my_hostname.oplog.conf"
sudo touch $OPLOG_CONF
sudo rm $OPLOG_CONF
sudo touch $OPLOG_CONF
echo "logfile $OPLOG"  >> $OPLOG_CONF
echo "logfile flush 1" >> $OPLOG_CONF
echo "log on"          >> $OPLOG_CONF

log "Preparing client configuration..."
bash $BIN_HOME/prepare_californium_configuration.sh $CLIENT_PROPERTIES_FILE $HOME/$CLIENT_PROPERTIES_FILE_NAME "${CLIENT_PROPERTIES[*]}" COAP.
log "Done!\n"

if [[ $TCPDUMP -eq 1 ]]; then
  log "Running client tcpdump...\n"
  sudo screen -c $OPLOG_CONF -d -m -L sudo $BIN_HOME/run_tcpdump.sh
fi

log "Running client...\n"
sudo screen -c $OPLOG_CONF -d -m -L sudo $BIN_HOME/client_run.sh
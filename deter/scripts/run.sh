#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Options
while getopts ":vn:x:" opt; do
  case "$opt" in
    "v") _V=1;;
    "n") _N=$OPTARG;;
    "x") _EXP_NAME=$OPTARG;;
  esac
done

# Check options
if [[ $_N -le 0 ]]; then
  echo "Expect positive number of runs, got $_N"
  exit 1
fi
if [[ -z $_EXP_NAME ]]; then
  echo "Expect nonempty experiment name"
  exit 1
fi


# Debug printer
function log () {
  if [[ $_V -eq 1 ]]; then
    printf "$@"
  fi
}

# Start internal IP discovery service
bash $SCRIPTS_HOME/storeips.sh

# Record the interfaces for each device
bash $SCRIPTS_HOME/record_interfaces.sh

printf "Using hosts: %s\n" "${HOST_NAMES[@]}"
printf "Using clients: %s\n" "${CLIENTS[@]}"

log "[CHECKPOINT] Starting experiment $_EXP_NAME\n"
log "[CHECKPOINT] Running $_N trials\n"

# Create experiment's data directory
experiment_dir=$EXPDATA_HOME/$_EXP_NAME
mkdir -p $experiment_dir
log "[CHECKPOINT] Created experiment directory $experiment_dir\n"

# Before beginning the experiment, check that the server's configuration file is up-to-date
if ssh $RUN_USER@$ORIGIN_SERVER_NAME "cmp -s /etc/apache2/apache2.conf $UTILS_HOME/apache2.conf"; then
  echo "[INFO] Server apache2.conf config ok!"
else
  echo "[INFO] Server apache2.conf config out of date"
  exit 1
fi
if ssh $RUN_USER@$ORIGIN_SERVER_NAME "cmp -s /etc/apache2/mods-available/mpm_event.conf $UTILS_HOME/mpm_event.conf"; then
  echo "[INFO] Server mpm_event.conf config ok!"
else
  echo "[INFO] Server mpm_event.conf config out of date"
  exit 1
fi


# Create experiment runs' data directories
for ((i=1; i<=$_N; i++)); do
  run_data_dir="$experiment_dir/$i"
  log "Creating $run_data_dir ...\n"
  mkdir -p $run_data_dir
done
log "[CHECKPOINT] Created experiment run directories\n"

# Create metadata about the experiment
metadata="$experiment_dir/metadata"
log "Creating metadata directory $metadata ...\n"
mkdir -p $metadata

# Record copies of: 1) config, 2) expinfo, 3) topology
cat $SCRIPTS_HOME/config.sh > $metadata/config.sh
expinfo -a MIT-DoS coap-setup > $metadata/expinfo.txt
cat $TOPOLOGIES_HOME/coap_topology.ns > $metadata/topo.ns

# Launch experiment runs sequentially
for ((i=1; i<=$_N; i++)); do
  log "[CHECKPOINT] Starting experiment trial $i\n"
  run_data_dir="$experiment_dir/$i"

  # Kill all detached remote sessions
  for host_name in ${HOST_NAMES[@]}; do
    log "[SETUP] Killing detached sessions on $host_name...\n"
    ssh $RUN_USER@$host_name "sudo $BIN_HOME/kill_detached.sh"
    log "OK\n"
  done

  # Receiver
  log "[LAUNCH] Starting receiver...\n"
  ssh $RUN_USER@$RECEIVER_NAME "sudo $SCRIPTS_HOME/start_receiver.sh -v"
  log "OK\n"
  
  # Origin server
  log "[LAUNCH] Starting origin server...\n"
  ssh $RUN_USER@$ORIGIN_SERVER_NAME "sudo $SCRIPTS_HOME/start_origin_server.sh -v"
  log "OK\n"

  # Proxy
  log "[LAUNCH] Starting proxy...\n"
  ssh $RUN_USER@$PROXY_NAME "sudo $SCRIPTS_HOME/start_proxy.sh -v"
  log "OK\n"

  log "[SETUP] Pausing for $PAUSE_TIME seconds...\n"
  sleep $PAUSE_TIME
  log "OK\n"

  # Clients
  if [[ $RUN_CLIENTS -eq 1 ]]; then
    for c in ${CLIENTS[@]}; do
      log "[LAUNCH] Starting client $c...\n"
      ssh $RUN_USER@$c "sudo $SCRIPTS_HOME/start_client.sh -v"
    done
    log "OK\n"
  fi

  # Attacker
  if [[ $RUN_ATTACKER -eq 1 ]]; then
    log "[LAUNCH] Starting attackers...\n"
    ssh $RUN_USER@$ATTACKER_NAME "sudo $SCRIPTS_HOME/start_attacker.sh -v"
    log "OK\n"
  fi

  # Inline countdown timer
  sleep_amt=$(( $PROXY_DURATION ))
  log "[SETUP] Waiting for $sleep_amt seconds...\n"
  secs=$sleep_amt
  while [ $secs -gt 0 ]; do
    echo -ne "$secs\033[0K\r"
    sleep 1
    : $((secs--))
  done
  log "OK\n"

  sleep_amt=$(( $WAIT_TIME ))
  log "[SETUP] Waiting for $sleep_amt seconds...\n"
  secs=$sleep_amt
  while [ $secs -gt 0 ]; do
    echo -ne "$secs\033[0K\r"
    sleep 1
    : $((secs--))
  done
  log "OK\n"

  # Move data files from tmp into the corresponding data run directory
  for host_name in ${HOST_NAMES[@]}; do
    log "[CHECKPOINT] Moving data from $host_name to $run_data_dir...\n"
    ssh $RUN_USER@$host_name "sudo $BIN_HOME/move_data.sh $run_data_dir"
    log "OK\n"
  done
done

# Zip experiment directory for super fast network transfer
log "[SETUP] Zipping data files...\n"
cd $experiment_dir
cd ..
zip -r $_EXP_NAME.zip $_EXP_NAME
log "OK\n"

log "[CHECKPOINT] Finished experiment!\n"

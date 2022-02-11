#!/bin/bash

DEFAULT_POLL_INTERVAL_SEC=0.225

usage() {
  cat <<EOM
  Usage:
    $(basename $0) listen_duration_sec outfile [poll_interval_sec]
    listen_duration_sec - the duration of time to monitor memory for (e.g., run for 20 [sec])
    outfile             - the name of the file to write output to
    poll_interval_sec   - OPTIONAL the interval in sec to poll record the memory usage (e.g., poll every 0.5 [sec]). Default is ${DEFAULT_POLL_INTERVAL_SEC} sec
EOM
  exit 0
} 

listen_duration_sec=$1
outfile=$2
poll_interval_sec=$3

check_present() {
  file_to_check=$1
  if [[ -z $file_to_check ]]; then
    basename_file="$(basename $file_to_check)"
    echo "Cannot find file $basename_file"
    exit 1
  fi
}

# Check that expected inputs are passed in to script
if [[ -z "$listen_duration_sec" ]] || [[ -z "$outfile" ]]; then
  usage;
  exit 1
fi

# Set the default poll duration
if [[ -z "$poll_interval_sec" ]] || [[ -z "$outfile" ]]; then
  poll_interval_sec=$DEFAULT_POLL_INTERVAL_SEC
fi

do_monitoring() {
  while true; do
      timestamp=$(date +%s)
      total_mem_usage_mb=$(free --mega | tr '\n' ' ' | awk '{print $9}')
      echo "${timestamp},${total_mem_usage_mb}" >> $outfile
      sleep $poll_interval_sec
  done
}

# Run monitoring in the background
do_monitoring &
monitor_pid=$!

sleep $listen_duration_sec

kill $monitor_pid
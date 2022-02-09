#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

duration=$1
sampling_interval=$2
cpu_filename=$3

usage() {
  cat <<EOM
  Usage:
    $(basename $0) duration sampling_interval cpu_filename
    duration          - the duration of time to monitor cpu for (e.g., run for 20 [sec])
    sampling_interval - the interval in sec to poll recording the cpu usage (e.g., poll every 0.5 [sec])
    cpu_filename      - the name of the file to write output to
EOM
  exit 0
}

# Check that expected inputs are passed in to script
if [[ -z "$duration" ]] || [[ -z "$sampling_interval" ]] || [[ -z "$cpu_filename" ]]; then
  usage;
  exit 1
fi

rm -f $cpu_filename

# Note the starting time of the processing
start_timestamp=$(date +%s)

# To limit top output, since we only care about the header, -p 0 monitors only pid 0
timeout $duration top -b -d $sampling_interval -p 0 > $cpu_filename

# Append start timestamp and sampling interval
echo "start_timestamp $start_timestamp" >> $cpu_filename
echo "sampling_interval_sec $sampling_interval" >> $cpu_filename
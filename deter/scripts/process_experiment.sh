#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) expname
    expname - the name of the experiment that this script will process. Should have either
              .zip file extension, or should have no extension at all.
EOM
}

# Check that expected inputs are passed in to the script
expname=$1
if [[ -z "$expname" ]]; then
  usage;
  exit 1
elif [[ $expname == *.* ]] && [[ $expname != *.zip ]]; then
  usage;
  exit 1
fi

# Produce zipped and unzipped experiment names
if [[ $expname == *.zip ]]; then
  zipped_expname="$expname"
  unzipped_expname=""${expname%.zip}""
else
  zipped_expname="$expname.zip"
  unzipped_expname="$expname"
fi

# Scp experiment data from deter if not there already
exp_dir="$DATA_DIR/$unzipped_expname"
zipped_exp_file="$DATA_DIR/$zipped_expname"
if [[ -z $zipped_exp_file ]]; then
  echo "$zipped_expname not found locally. Fetching from deter..."
  scp -r amirf@users.deterlab.net:$REMOTE_EXP_DIR/$zipped_expname $DATA_DIR
  if [[ $? != 0 ]]; then
    echo "SCP failed with code $?"
    exit $?
  fi
fi

# | Step 0 | Unzip (if not already) experiment files
unzip -n $zipped_exp_file -d $DATA_DIR

# | Step 1 | Consolidate configuration into a single config file
check_present $exp_dir/metadata/topo.ns
check_present $exp_dir/metadata/expinfo.txt
check_present $exp_dir/metadata/config.sh

# Make and clear output config file
joined_config=$exp_dir/metadata/config.json
touch $joined_config
> $joined_config

# Expose evaluated variables in the environment
set -a
source $exp_dir/metadata/config.sh
set +a

# Compute nuumber of trials by subtracting single metadata directory
num_dirs="$(find $exp_dir/* -maxdepth 0 -type d | wc -l)"
num_trials="$(($num_dirs - 1))"

python3 $SCRIPTS_DIR/consolidate_config.py -n $unzipped_expname \
                                           -t $exp_dir/metadata/topo.ns \
                                           -e $exp_dir/metadata/expinfo.txt \
                                           -c $exp_dir/metadata/config.sh \
                                           -r $num_trials \
                                           -o $joined_config

# Determine if we run the experiment using HTTPS
run_proxy_with_https=$(cat $joined_config | jq -r '.run_proxy_with_https')
origin_server_keylogfile_name=$(cat $joined_config | jq -r '.origin_server_keylogfile_name')
proxy_keylogfile_name=$(cat $joined_config | jq -r '.proxy_keylogfile_name')
dummy_keylogfile="$HOME/dummy_keylogfile.txt"
sudo touch $dummy_keylogfile
sudo chmod 666 $dummy_keylogfile

# | Step 2 | Parse (if not exists) tcpdumps
parse_tcpdumps() {
  process_dump_and_log() {
    d=$1
    p=$2
    k=$3
    t=$4
    bd=$(basename $d)
    echo "$bd" >> $t
    (time bash $SCRIPTS_DIR/process_tcpdump.sh $d $p $k) &>> $t
  }

  pids=()
  temp_files=()
  for D in $exp_dir/*; do
    bd="$(basename $D)"
    if [[ -d $D && $bd != "metadata" ]]; then
      # Process (if not already processed) the tcpdumps
      for dump_file in $D/*_dump.pcap; do
        basename_dump=$(basename $dump_file)
        processed_dump_file="$dump_file.out"
        processed_connections_file="$dump_file.connections.out"

        # Fetch corresponding keylogfile if the experiment uses TLS
        keylog_file=$dummy_keylogfile
        if [[ $run_proxy_with_https -eq 1 ]]; then
          echo $basename_dump
          if [[ $basename_dump == "proxy_dump.pcap" ]]; then
            keylog_file=$D/$proxy_keylogfile_name
          elif [[ $basename_dump == "server_dump.pcap" ]]; then
            keylog_file=$D/$origin_server_keylogfile_name
          else
            (:)
          fi
        fi

        if [[ ! -f $processed_dump_file ]]; then
          echo "Processing coap & http in $bd/`basename $dump_file`..."
          # Transform the tcpdump fully for coap & http
          tf=$(mktemp)
          temp_files+=($tf)
          (process_dump_and_log $dump_file $processed_dump_file $keylog_file $tf) &
          pids+=($!)
        fi

        # if [[ ! -f $processed_connections_file ]]; then
        echo "Processing tcp in $bd/`basename $dump_file`..."
        # Compress key TCP connections events
        (bash $SCRIPTS_DIR/process_connections.sh $dump_file $processed_connections_file $keylog_file) &
        pids+=($!)
        # fi
      done
    fi
  done
  # And wait for all processing to finish
  for pid in "${pids[@]}"; do
    wait $pid
  done
  echo "Parsed tcpdumps"
}
time parse_tcpdumps
for tf in ${temp_files[@]}; do
  cat $tf
  rm $tf
done

# | Step 3 | Collect CPU and Memory usage from devices
metric_infiles=""
metric_outfile="$exp_dir/$unzipped_expname.metrics.csv"
for D in $exp_dir/*; do
  bd="$(basename $D)"
  if [[ -d $D && $bd != "metadata" ]]; then
    for metric_file in $D/*.metric.out; do
      if [[ -f $metric_file ]]; then
        metric_infiles+="$metric_file;"
      fi
    done
  fi
done
python3 $SCRIPTS_DIR/metric_processor.py -i $metric_infiles -o $metric_outfile

# | Step 4.1 | Transform experiment data to be DB-ready
transform_data() {
  pids=()
  for D in $exp_dir/*; do
    bd="$(basename $D)"
    if [[ -d $D && $bd != "metadata" ]]; then
      # Collect input files for processing
      infiles=""
      nice_infiles=""
      for processed_dump_file in $D/*_dump.pcap.out; do
        infiles+="$processed_dump_file;"
        nice_infiles+="`basename $processed_dump_file`,"
      done
      # Process all input files into one file
      # If not already processed before
      outfile="$D/$unzipped_expname.parquet"
      httpoutfile="$D/http_response_codes.json"
      coapoutfile="$D/coap_response_codes.json"
      if [[ ! -f $outfile ]]; then
        echo "Processing tcpdumps in $bd..."
        (python3 $SCRIPTS_DIR/transform_experiment_data.py -i $infiles -o $outfile -c $joined_config -r $httpoutfile -a $coapoutfile) &
        pids+=($!)
      fi
    fi
  done
  # And wait for all processing to finish
  for pid in "${pids[@]}"; do
    wait $pid
  done
  echo "Transformed data"
}
time transform_data

# | Step 4.2 | Transform connection data to be DB-ready
transform_connections() {
  pids=()
  for D in $exp_dir/*; do
    bd="$(basename $D)"
    if [[ -d $D && $bd != "metadata" ]]; then
      # Collect input files for processing
      infiles=""
      nice_infiles=""
      for processed_connections_file in $D/*.connections.out; do
        infiles+="$processed_connections_file;"
        nice_infiles+="`basename $processed_connections_file`,"
      done
      # Process all input files into one file
      # If not already processed before
      outfile="$D/$unzipped_expname.connections.parquet"
      # if [[ ! -f $outfile ]]; then
      echo "Processing connections in $bd..."
      (python3 $SCRIPTS_DIR/transform_experiment_connections.py -i $infiles -o $outfile -c $joined_config) &
      pids+=($!)
      # fi
    fi
  done
  # And wait for all processing to finish
  for pid in "${pids[@]}"; do
    wait $pid
  done
  echo "Transformed connections"
}
time transform_connections

# | Step 4.3 | Transform experiment metrics to be DB-ready
echo "Processing metrics..."
python3 $SCRIPTS_DIR/transform_experiment_metrics.py -m $metric_outfile
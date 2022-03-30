#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) expname
    expname - the name of the experiment whose data this script will clean. Can
              only be the string name of an experiment with an already processed
              data directory.
EOM
}
# Check that expected inputs are passed in to the script
expname=$1
if [[ -z "$expname" ]]; then
  usage;
  exit 1
elif [[ $expname == *.zip ]]; then
  usage;
  exit 1
fi

# Check that the experiment's directory exists
exp_dir="$DATA_DIR/$expname"
check_directory_exists $exp_dir usage

for D in $exp_dir/*; do
  if [[ -d $D ]]; then
    # Main processed data file
    for main_data_file in $D/$expname.*; do
      log_remove_file $main_data_file
    done

    # Aggregated metrics file
    for main_data_file in $exp_dir/*.metrics.*; do
      log_remove_file $main_data_file
    done

    # # Processed dumps
    # for processed_dump in $D/*.out; do
    #   log_remove_file $processed_dump
    # done
    
    # Csvs
    for general_csv_file in $D/*.csv; do
      log_remove_file $general_csv_file
    done

    # Json
    for json_file in $D/*.json; do
      log_remove_file $json_file
    done

    # Shell
    for shell_file in $D/*.sh; do
      log_remove_file $shell_file
    done

    # Text
    for text_file in $D/*.txt; do
      log_remove_file $text_file
    done

    # Network Simulator Topology
    for ns_file in $D/*.ns; do
      log_remove_file $ns_file
    done
  fi
done
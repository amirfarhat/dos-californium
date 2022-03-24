#!/bin/bash

# Require that CF_HOME is set
if [[ -z "$CF_HOME" ]]; then
  echo "CF_HOME is empty or unset"  
  exit 1
fi

log_remove() {
  file=$1
  if [[ -f $file ]]; then
    echo "Removing `basename $file`..."
    rm $file
  fi
}

DATA_DIR=$CF_HOME/deter/expdata/real/final
SCRIPTS_DIR=$CF_HOME/deter/scripts

experiment_name=$1

# Construct full path to experiment directory
exp_dir="$DATA_DIR/$experiment_name"

cd $SCRIPTS_DIR

for D in $exp_dir/*; do
  if [[ -d $D ]]; then
    for main_data_file in $D/$experiment_name.*; do
      log_remove $main_data_file
    done

    # # Processed dumps
    # for processed_dump in $D/*.out; do
    #   log_remove $processed_dump
    # done
    
    # Csvs
    for general_csv_file in $D/*.csv; do
      log_remove $general_csv_file
    done

    # Json
    for json_file in $D/*.json; do
      log_remove $json_file
    done

    # Shell
    for shell_file in $D/*.sh; do
      log_remove $shell_file
    done

    # Text
    for text_file in $D/*.txt; do
      log_remove $text_file
    done

    # Network Simulator
    for ns_file in $D/*.ns; do
      log_remove $ns_file
    done
  fi
done
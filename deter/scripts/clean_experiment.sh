#!/bin/bash

# Require that CF_HOME is set
if [[ -z "$CF_HOME" ]]; then
  echo "CF_HOME is empty or unset"  
  exit 1
fi

DATA_DIR=$CF_HOME/deter/expdata/real/final
SCRIPTS_DIR=$CF_HOME/deter/scripts

experiment_name=$1

# Construct full path to experiment directory
exp_dir="$DATA_DIR/$experiment_name"

cd $SCRIPTS_DIR

for D in $exp_dir/*; do
  if [[ -d $D ]]; then
    echo "Looking for processed files in `basename $D`..."

    # Processed dumps
    for processed_dump in $D/*.out; do
      echo "Removing `basename $processed_dump`..."
      rm $processed_dump
    done
    
    # Csvs
    for dump_csv in $D/*.csv; do
      echo "Removing `basename $dump_csv`..."
      rm $dump_csv
    done

    # Json
    for json_file in $D/*.json; do
      echo "Removing `basename $json_file`..."
      rm $json_file
    done

    # Shell
    for shell_file in $D/*.sh; do
      echo "Removing `basename $shell_file`..."
      rm $shell_file
    done

    # Text
    for text_file in $D/*.txt; do
      echo "Removing `basename $text_file`..."
      rm $text_file
    done

    # Network Simulator
    for ns_file in $D/*.ns; do
      echo "Removing `basename $ns_file`..."
      rm $ns_file
    done
  fi
done
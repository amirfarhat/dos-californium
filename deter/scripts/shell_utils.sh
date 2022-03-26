#!/bin/bash

# Require that CF_HOME is set
if [[ -z "$CF_HOME" ]]; then
  echo "CF_HOME is empty or unset"  
  exit 1
fi

# Helper to check if a supplied file exists
check_present() {
  file_to_check=$1
  if [[ -z $file_to_check ]]; then
    basename_file="$(basename $file_to_check)"
    echo "Cannot find file $basename_file"
    exit 1
  fi
}

# Helper to check if a supplied directory exists
check_directory_exists() {
  directory_to_check=$1
  callback=$2
  if [[ ! -d $directory_to_check ]]; then
    basename_directory="$(basename $directory_to_check)"
    if [[ ! -z "$callback" ]]; then
      $callback
      echo ""
    fi
    echo "Cannot find directory \"$basename_directory\""
    exit 1
  fi
}

# Helper to verbosely remove an existing file
log_remove_file() {
  file=$1
  if [[ -f $file ]]; then
    rm $file
    echo "Removed `basename $file`"
  fi
}

DATA_DIR=$CF_HOME/deter/expdata/real/final
SCRIPTS_DIR=$CF_HOME/deter/scripts
TOPOS_DIR=$CF_HOME/deter/topologies

REMOTE_EXP_DIR="/proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/expdata"

mkdir -p $DATA_DIR
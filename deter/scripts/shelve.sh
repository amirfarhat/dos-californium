#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) -e exp_name_inputs
    exp_name_inputs - the names of the experiment that this script will process.
EOM
}

# Parse command line arguments
while getopts e: opt; do
  case $opt in
    e) exp_name_inputs=$OPTARG;;
    *) usage
       exit 1;;
  esac
done

# Check that expected inputs are passed in to the script
if [[ -z "$exp_name_inputs" ]]; then
  usage;
  exit 1
fi

# Split input exp_names by comma into bash array exp_name_inputs_array
readarray -td, exp_name_inputs_array <<<"$exp_name_inputs,"; unset 'exp_name_inputs_array[-1]';

# Assert that there are no zip files in supplied names
for e in ${exp_name_inputs_array[@]}; do
  if [[ $e == *.zip ]]; then
    echo "Experiment $e is a .zip file, this is not allowed"
    exit 1
  fi
done

for e in ${exp_name_inputs_array[@]}; do
  for exp_dir in $(find $DATA_DIR/$e -maxdepth 1 -type d 2> /dev/null | sort); do
    exp_name=$(basename $exp_dir)
    if [[ -f "$DATA_DIR/$exp_name.zip" ]]; then
      rm -rf "$DATA_DIR/$exp_name"
      # echo "$DATA_DIR/$exp_name"
    fi
  done
done
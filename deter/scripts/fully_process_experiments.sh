#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) -e exp_name_inputs -d db_name -n no_fetch_experiments -c clean_before_processing
    exp_name_inputs         - the names of the experiment that this script will process. Should
                              be comma-separated. Supports the use of wildcard in names. Experiment
                              names must not be zipped or compressed.
    db_name                 - the name of the database we should insert experiments' data into
    no_fetch_experiments    - flag to determine whether data must be fetched from deter
    clean_before_processing - flag to determine whether data must be fetched from deter
EOM
}

# Parse command line arguments
no_fetch_experiments=0
clean_before_processing=0
while getopts e:d:nc opt; do
  case $opt in
    e) exp_name_inputs=$OPTARG;;
    d) db_name=$OPTARG;;
    n) no_fetch_experiments=1;;
    c) clean_before_processing=1;;
    *) usage
       exit 1;;
  esac
done

# Check that expected inputs are passed in to the script
if [[ -z "$exp_name_inputs" ]] || [[ -z "$db_name" ]]; then
  usage;
  exit 1
fi

# Split input exp_names by comma into bash array exp_name_inputs_array
readarray -td, exp_name_inputs_array <<<"$exp_name_inputs,"; unset 'exp_name_inputs_array[-1]';

# Assert that there are no zip files
for e in ${exp_name_inputs_array[@]}; do
  if [[ $e == *.zip ]]; then
    echo "Experiment $e is a .zip file, this is not allowed"
    exit 1
  fi
done

# Fetch all experiments from deter
if [[ $no_fetch_experiments == 0 ]]; then
  printf -v scp_target "$REMOTE_EXP_DIR/%s.zip " "${exp_name_inputs_array[@]}"
  echo "$scp_target"
  scp -r amirf@users.deterlab.net:"$scp_target" $DATA_DIR
fi

# Collect all experiment directories and names found
exp_dirs_found=()
exp_names_found=()
for e in ${exp_name_inputs_array[@]}; do
  for exp_dir in $(find $DATA_DIR/$e -maxdepth 0 -type d); do
    exp_name=$(basename $exp_dir)
    exp_dirs_found+=($exp_dir)
    exp_names_found+=($exp_name)
  done
done

# Prompt the user whether they wish to process all experiments
echo "Found the following experiments:"
for i in ${!exp_names_found[@]}; do
  num=$(($i+1))
  echo "    $num. ${exp_names_found[$i]}"
done
echo -n "Do you wish include all the above experiments? [y/n]: "
read process_all_found_exps

# Determine the subset of experiments which to process
exp_dirs_to_process=()
if [[ -z "$process_all_found_exps" ]] || [[ $process_all_found_exps == "y" ]]; then
  # If the user accepts all experiments, note that
  exp_dirs_to_process=${exp_dirs_found[@]}
else
  # Otherwise, allow the user to choose the subset 
  # of experiments to process
  for i in ${!exp_dirs_found[@]}; do
    num=$(($i+1))
    exp_dir=$(echo "${exp_dirs_found[$i]}")
    exp_name=$(basename $exp_dir)
    echo -n "Include $num. $exp_name? [y/n]: "
    read process_exp_flag
    if [[ -z "$process_exp_flag" ]] || [[ $process_exp_flag == "y" ]]; then
      exp_dirs_to_process+=($exp_dir)
    fi
  done
fi

# Clean all selected experiments to fresh starting state
if [[ $clean_before_processing == 1 ]]; then
  echo ""
  echo -n "Cleaning all experiments..."
  for exp_dir in ${exp_dirs_to_process[@]}; do
    exp_name=$(basename $exp_dir)
    bash $SCRIPTS_DIR/clean_experiment.sh $exp_name 1> /dev/null
  done
  echo "Done"
fi

process_exp() {
  exp_dir=$1
  exp_name=$(basename $exp_dir)
  echo "    Processing $exp_name..."
  bash $SCRIPTS_DIR/process_experiment.sh $exp_name 1> /dev/null
}

insert_exp_to_db() {
  exp_dir=$1
  exp_name=$(basename $exp_dir)
  echo "    Adding $exp_name to DB..."
  bash $SCRIPTS_DIR/add_exp_to_db.sh -n -e $exp_name -d $db_name 1> /dev/null
}

time (
  echo ""
  echo "Processing experiments:"
  pids=()
  for exp_dir in ${exp_dirs_to_process[@]}; do
    process_exp $exp_dir &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do
    wait $pid
  done
)

time (
  echo ""
  echo "Adding to DB:"

  quietly_bootstrap_db $db_name

  pids=()
  for exp_dir in ${exp_dirs_to_process[@]}; do
    insert_exp_to_db $exp_dir &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do
    wait $pid
  done
)
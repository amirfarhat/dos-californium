#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) -e exp_name_inputs -d db_name -n no_fetch_experiments -c clean_before_processing -f use_file_based_grouping -s skip_grouping -h clickhouse
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
use_file_based_grouping=0
skip_grouping=0
clickhouse=0
while getopts e:d:ncfsh opt; do
  case $opt in
    e) exp_name_inputs=$OPTARG;;
    d) db_name=$OPTARG;;
    n) no_fetch_experiments=1;;
    c) clean_before_processing=1;;
    f) use_file_based_grouping=1;;
    s) skip_grouping=1;;
    h) clickhouse=1;;
    *) usage
       exit 1;;
  esac
done

# Check that expected inputs are passed in to the script
if [[ -z "$exp_name_inputs" ]] || [[ -z "$db_name" ]]; then
  usage;
  exit 1
fi

# Make directory to store the groupping's logs
group_logging_dir="/home/ubuntu/group_logging"
if [[ $use_file_based_grouping == 1 ]]; then
  log_dir="$group_logging_dir/file_$db_name"
else
  log_dir="$group_logging_dir/db_$db_name"
fi
mkdir -p $log_dir

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
  scp -r amirf@users.deterlab.net:"$scp_target" $DATA_DIR
fi

# Collect all experiment directories and names found
exp_dirs_found=()
exp_names_found=()
for e in ${exp_name_inputs_array[@]}; do
  num_dirs_found=$(find $DATA_DIR/$e -maxdepth 0 -type d 2> /dev/null | wc -l)
  if [[ $num_dirs_found == 0 ]]; then
    num_zips_found=$(find $DATA_DIR/$e.zip -maxdepth 0 -type f 2> /dev/null | wc -l)
    if [[ $num_zips_found == 0 ]]; then
      echo "Experiment $e not found. Fetch the experiment from deter using the no_fetch_experiments flag"
      exit 1
    else
      for exp_zip in $(find $DATA_DIR/$e.zip -maxdepth 0 -type f); do
        exp_name=$(basename $exp_zip)
        exp_dirs_found+=($exp_zip)
        exp_names_found+=($exp_name)
      done
    fi
  else
    for exp_dir in $(find $DATA_DIR/$e -maxdepth 0 -type d); do
      exp_name=$(basename $exp_dir)
      exp_dirs_found+=($exp_dir)
      exp_names_found+=($exp_name)
    done
  fi
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

main() {
  process_exp() {
    exp_dir=$1
    exp_name=$(basename $exp_dir)
    echo "    Processing $exp_name..."
    (time bash $SCRIPTS_DIR/process_experiment.sh $exp_name) &> "$log_dir/process_$exp_name.log"
  }

  group_experiments_to_db() {
    exp_name_inputs=$1

    if [[ $clickhouse == 1 ]]; then
      bootstrap_clickhouse $db_name
      bash $SCRIPTS_DIR/group_experiments_to_clickhouse.sh -n -e $exp_name_inputs -d $db_name
    else
      quietly_bootstrap_db $db_name
      bash $SCRIPTS_DIR/group_experiments_to_db.sh -n -e $exp_name_inputs -d $db_name
    fi
  }

  group_experiments_to_file() {
    exp_name_inputs=$1
    bash $SCRIPTS_DIR/group_experiments_to_file.sh -n -e $exp_name_inputs -d $db_name
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
      # Waiting on a specific PID makes the wait command return with the exit
      # status of that process. Because of the 'set -e' setting, any exit status
      # other than zero causes the current shell to terminate with that exit
      # status as well.
      wait $pid
    done
  )

  if [[ $skip_grouping == 0 ]]; then
    time (
      echo ""
      echo "Grouping experiments:"

      if [[ $use_file_based_grouping == 1 ]]; then
        group_experiments_to_file $exp_name_inputs
      else
        group_experiments_to_db $exp_name_inputs
        echo "Running analyze"
        time run_analyze_on_db $db_name
      fi
    )
  fi
}

( time main ) 2>&1 | tee "$log_dir/main.log"
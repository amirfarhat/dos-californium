#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) -e exp_name_inputs -d db_name -n no_bootstrap -a analyze
    exp_name_inputs - the name of the experiment with processed data to insert into the DB db_name. 
                      May be a directory name or a zipped file name.
    db_name         - the name of the database we should insert exp_name's data into
    no_bootstrap    - flag which specifies whether this script should create and bootstrap the DB
    analyze         - flag which specifies whether this script should run ANALYZE after insertion
EOM
} >&2

# Parse command line arguments
no_bootstrap=0
analyze=0
while getopts e:d:na opt; do
  case $opt in
    e) exp_name_inputs=$OPTARG;;
    d) db_name=$OPTARG;;
    n) no_bootstrap=1;;
    a) analyze=1;;
    *) usage
       exit 1;;
  esac
done

# Check that expected inputs are passed in to script
if [[ -z "$exp_name_inputs" ]] || [[ -z "$db_name" ]] || [[ -z "$no_bootstrap" ]] || [[ -z "$analyze" ]]; then
  usage;
  exit 1
fi

# Split input exp_names by comma into bash array exp_name_inputs_array
readarray -td, exp_name_inputs_array <<<"$exp_name_inputs,"; unset 'exp_name_inputs_array[-1]';

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

exp_dirs=""
for ed in ${exp_dirs_found[@]}; do
  exp_dirs+="$ed;"
done

if [[ $no_bootstrap == 0 ]]; then
  bootstrap_db $db_name
fi

group_dir="/home/ubuntu/$db_name"
mkdir -p $group_dir

python3 $SCRIPTS_DIR/send_experiment_group_to_file.py -i $exp_dirs -d $group_dir
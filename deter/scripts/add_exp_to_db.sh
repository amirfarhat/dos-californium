#!/bin/bash

source $(find ~/*californium -name shell_utils.sh)

usage() {
  cat <<EOM
  Usage:
    $(basename $0) -e exp_name -d db_name -n no_bootstrap
    exp_name     - the name of the experiment with processed data to insert into the DB db_name. 
                   May be a directory name or a zipped file name.
    db_name      - the name of the database we should insert exp_name's data into
    no_bootstrap - flag which specifies whether this script should create and bootstrap the DB
EOM
} >&2

# Parse command line arguments
no_bootstrap=0
while getopts e:d:n opt; do
  case $opt in
    e) exp_name=$OPTARG;;
    d) db_name=$OPTARG;;
    n) no_bootstrap=1;;
    *) usage
       exit 1;;
  esac
done

# Check that expected inputs are passed in to script
if [[ -z "$exp_name" ]] || [[ -z "$db_name" ]] || [[ -z "$no_bootstrap" ]]; then
  usage;
  exit 1
fi

# Set experiment name to be the unzipped version
if [[ $exp_name == *.zip ]]; then
  zipped_exp_name="$exp_name"
  unzipped_exp_name=""${exp_name%.zip}""
else
  zipped_exp_name="$exp_name.zip"
  unzipped_exp_name="$exp_name"
fi
exp_name=$unzipped_exp_name

# Check that the experiment's directory exists
exp_dir="$DATA_DIR/$exp_name"
check_directory_exists $exp_dir usage

joined_config_path="$exp_dir/metadata/config.json"
check_present joined_config_path

metrics_file_path="$exp_dir/$exp_name.metrics.csv"
check_present metrics_file_path

if [[ $no_bootstrap == 0 ]]; then
  bootstrap_db $db_name
fi

# Send each trial's data to the DB
infiles=""
for D in $exp_dir/*; do
  bd="$(basename $D)"
  if [[ -d $D && $bd != "metadata" ]]; then
    inf="$D/$exp_name.parquet"
    infiles+="$inf;"
  fi
done
python3 $SCRIPTS_DIR/all_trials_read_send_to_db.py -i $infiles \
                                                   -c $joined_config_path \
                                                   -d $db_name \
                                                   -m $metrics_file_path
#!/bin/bash

usage() {
  cat <<EOM
  Usage:
    $(basename $0) expname dbname
    expname - the name of the experiment with processed data to insert into the DB dbname
    dbname  - the name of the database we should insert expname's data into
EOM
  exit 0
}

check_present() {
  file_to_check=$1
  if [[ -z $file_to_check ]]; then
    basename_file="$(basename $file_to_check)"
    echo "Cannot find file $basename_file"
    exit 1
  fi
}

# Check that expected inputs are passed in to script
expname=$1
dbname=$2
if [[ -z "$expname" ]] || [[ -z "$dbname" ]]; then
  usage;
  exit 1
fi

# Require that CF_HOME is set
if [[ -z "$CF_HOME" ]]; then
  echo "CF_HOME is empty or unset"  
  exit 1
fi

# Construct paths to data and scripts
DATA_DIR=$CF_HOME/deter/expdata/real/final
SCRIPTS_DIR=$CF_HOME/deter/scripts

# Find the directory containing this experiment
exp_dir="$DATA_DIR/$1"
if [[ ! -d $exp_dir ]]; then
  echo "Could not find experiment directory $exp_dir"
  exit 1
fi
expname=$(basename $exp_dir)

check_present $SCRIPTS_DIR/functions_and_procedures.sql
check_present $exp_dir/metadata/config.json

functions_and_procedures_path=$SCRIPTS_DIR/sql/functions_and_procedures.sql
joined_config=$exp_dir/metadata/config.json

# Create database if not exists
(sudo su postgres -c "psql template1 -c 'CREATE DATABASE ${dbname}'" || true) > /dev/null 2>&1
echo "Created DB ${dbname}"

# Bootstrap DB for experiments
python3 $SCRIPTS_DIR/bootstrap_db.py -d $dbname \
                                     -p $functions_and_procedures_path

# Send each trial's data to the DB
infiles=""
for D in $exp_dir/*; do
  bd="$(basename $D)"
  if [[ -d $D && $bd != "metadata" ]]; then
    inf="$D/$expname.parquet"
    infiles+="$inf;"
  fi
done
time python3 $SCRIPTS_DIR/all_trials_read_send_to_db.py -i $infiles \
                                                        -c $joined_config \
                                                        -d $dbname \
                                                        -m $exp_dir/$expname.metrics.csv
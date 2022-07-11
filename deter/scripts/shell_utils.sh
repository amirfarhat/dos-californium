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

DATA_DIR=$CF_HOME/deter/expdata/real/final
SCRIPTS_DIR=$CF_HOME/deter/scripts
SQL_DIR=$SCRIPTS_DIR/sql
REMOTE_EXP_DIR="/proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/expdata"

functions_and_procedures_path="$SCRIPTS_DIR/sql/functions_and_procedures.sql"
check_present functions_and_procedures_path

mkdir -p $DATA_DIR

# Helper to verbosely remove an existing file
log_remove_file() {
  file=$1
  if [[ -f $file ]]; then
    rm $file
    echo "Removed `basename $file`"
  fi
}

bootstrap_db() {
  db_name=$1

  # Create database if not exists
  (sudo su postgres -c "psql template1 -c 'CREATE DATABASE ${db_name}'" || true) > /dev/null 2>&1
  echo "Created DB ${db_name}"

  # Bootstrap DB for experiments
  python3 $SCRIPTS_DIR/bootstrap_db.py -d $db_name \
                                       -p $functions_and_procedures_path
}

bootstrap_clickhouse() {
  db_name=$1
  clickhouse_sql="$SQL_DIR/bootstrap_clickhouse.sql"
  python3 $SCRIPTS_DIR/bootstrap_clickhouse.py -d $db_name -s $clickhouse_sql
}

quietly_bootstrap_db() {
  db_name=$1
  bootstrap_db $db_name 1> /dev/null
}

run_analyze_on_db() {
  db_name=$1
  (sudo su postgres -c "psql ${db_name} -c 'ANALYZE'" || true) > /dev/null 2>&1
}

contains() {
  if [ -v '$2[$1]' ]; then
    return 0
  else
    return 1
  fi
}
#!/bin/bash

# source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh
source /Users/amirfarhat/workplace/research/dos-californium/deter/scripts/config.sh

# The base property file has some fields which should be modified by dynamic
# configuration, coming from config.sh. This scripts sets those fields in a new
# property file

usage() {
  cat <<EOM
  Usage:
    $(basename $0) property_file modified_property_file properties_array property_prefix
    property_file           - base configuration file to overwrite fields from
    modified_property_file  - new configuration file with overwritten fields
    properties_array        - bash array of the names of properties to overwrite
    property_prefix         - prefix of the property in the configutation file. "DOS." for proxy, "COAP." for client
EOM
}

# Check that expected inputs are passed in to script
property_file=$1
modified_property_file=$2
properties_array=$3
property_prefix=$4
if [[ -z "$property_file" ]] || [[ -z "$modified_property_file" ]] || [[ -z "$properties_array" ]] || [[ -z "$property_prefix" ]]; then
  usage;
  exit 1
fi

# Base property file must exist
check_file_exists $property_file

# Copy base property file into new file
touch $modified_property_file
rm $modified_property_file
touch $modified_property_file

# Create and wipe sed file
sed_script_file="/tmp/sed_scripts.sed"
touch $sed_script_file
rm $sed_script_file
touch $sed_script_file

for property in ${properties_array[@]}; do
  # Check that all properties are in config.sh and property files
  if [[ -z "$property" ]]; then
    echo "Config variable $property unset in config.sh"
    exit 1
  fi
  if ! grep -qF "$property" $property_file; then
    echo "Could not find $property in property file"
    exit 1
  fi

  # Add script for sed
  sed_string="s/$property_prefix$property=.*$/$property_prefix$property=${!property}/g"
  echo "$sed_string" >> $sed_script_file
done

# Instruct sed to replace the base property values with those from config.sh.
# Ignore sed's output to stdout, we only care about the file
(sed -f $sed_script_file $property_file | tee $modified_property_file) 1> /dev/null
#!/bin/bash

# source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh
source /home/ubuntu/dos-californium/deter/scripts/config.sh

# The base proxy configuration file has some fields which should be modified by dynamic
# configuration, coming from config.sh. This scripts sets those fields in the file at the
# proxy

proxy_config_file="$PROPERTIES_FILE"
modified_proxy_config_file="$HOME/$PROPERTIES_FILE_NAME"

if [[ ! -f "$proxy_config_file" ]]; then
  echo "Could not find proxy configuration file at $proxy_config_file"
  exit 1
fi

# Copy base configuration file to the proxy
touch $modified_proxy_config_file
rm $modified_proxy_config_file
touch $modified_proxy_config_file

# Create and wipe sed file
sed_script_file="/tmp/sed_scripts.sed"
touch $sed_script_file
rm $sed_script_file
touch $sed_script_file

for property in ${PROXY_PROPERTIES[@]}; do
  # Check that all proxy properties are in the config and property files
  if [[ -z "$property" ]]; then
    echo "Config variable $property unset in config.sh"
    exit 1
  fi
  if ! grep -qF "$property" $proxy_config_file; then
    echo "Could not find $property in proxy configuration file"
    exit 1
  fi

  # Add script for sed
  sed_string="s/DOS.$property=.*$/DOS.$property=${!property}/g"
  echo "$sed_string" >> $sed_script_file
done

# Instruct sed to replace the base proxy property values with those from the config.
# Ignore sed's output to stdout, we only care about the file
(sed -f $sed_script_file $proxy_config_file | tee $modified_proxy_config_file) 1> /dev/null
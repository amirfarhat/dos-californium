#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# The base proxy configuration file has some fields which should be modified by dynamic
# configuration, coming from config.sh. This scripts sets those fields in the file at the
# proxy

proxy_config_file="$UTILS_HOME/Californium.properties"
modified_proxy_config_file="$HOME/Californium.properties"

if [[ ! -f "$proxy_config_file" ]]; then
  echo "Could not find proxy configuration file at $proxy_config_file"
  exit 1
fi

# Copy base configuration file to the proxy
touch $modified_proxy_config_file

# Extract TCP_CONNECT_TIMEOUT flag
if [[ -z "$PROXY_REQUEST_TIMEOUT_MS" ]]; then
  echo "Config variable PROXY_REQUEST_TIMEOUT_MS unset in config.sh"
  exit 1
fi
if ! grep -qF "TCP_CONNECT_TIMEOUT" $proxy_config_file; then
  echo "Could not find TCP_CONNECT_TIMEOUT in proxy configuration file"
  exit 1
fi
timeout=$(grep "TCP_CONNECT_TIMEOUT=" $proxy_config_file | awk '{split($0, a, "="); print a[2]}')
timeout_string=$(echo "TCP_CONNECT_TIMEOUT=${timeout}")

# The proxy scales the timeout parameter by 4 to get the request timeout, so
# before the proxy picks up the timeout parameter, it is necessary to prescale
SCALED_TCP_CONNECT_TIMEOUT=`expr $PROXY_REQUEST_TIMEOUT_MS / 4`

# Swap TCP_CONNECT_TIMEOUT value with value from config into new config
sed_string="s/$timeout_string/TCP_CONNECT_TIMEOUT=${SCALED_TCP_CONNECT_TIMEOUT}/"
((sed "$sed_string" $proxy_config_file | tee $modified_proxy_config_file) 1> /dev/null)
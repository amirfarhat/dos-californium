#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

PROXY_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy`
ORIGIN_SERVER_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy originserver`

# Make sure there are no java procs running
while [[ ! -z `pgrep java` ]]; do
  next_pid=`pgrep java | tail -1`
  echo "Killing $next_pid..."
  sudo kill -9 $next_pid
  echo "Done"
done

numbered_client="$(hostname | awk '{print tolower($0)}' | tr "." "\n" | head -1)"
client_log="$TMP_DATA/$numbered_client.log"
sudo rm -f $client_log
sudo touch $client_log

# The proxy URI will different if the proxy uses DTLS or not
proxy_uri=""
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  proxy_uri="coaps://$PROXY_IP:$PROXY_DTLS_PORT/coaps2http"
else
  proxy_uri="coap://$PROXY_IP:$PROXY_COAP_PORT/coap2http"
fi

destination_uri=""
if [[ $RUN_PROXY_WITH_HTTPS -eq 1 ]]; then
  destination_uri="https://$ORIGIN_SERVER_IP:$ORIGIN_SERVER_HTTPS_PORT"
else
  destination_uri="http://$ORIGIN_SERVER_IP:$ORIGIN_SERVER_PORT"
fi

echo "Running client..."
((sudo java -jar $CF_PROXY_JAR DoSSynchronousCoapClient "$proxy_uri" "$destination_uri" "$NUM_CLIENT_MESSAGES") > $client_log 2>&1) &

# Wait until client pid shows up
while [[ -z `pgrep java` ]]; do
  sleep 0.1
done
client_pid=`pgrep java`
echo "Ran client with pid $client_pid..."

echo "Sleeping for $CLIENT_DURATION seconds..."
sleep $CLIENT_DURATION
echo "Woke up"

# Kill client
echo "Killing $client_pid..."
sudo kill -9 $client_pid
echo "Done"

# Kill all other java procs
while [[ ! -z `pgrep java` ]]; do
  next_pid=`pgrep java | tail -1`
  echo "Killing $next_pid..."
  sudo kill -9 $next_pid
  echo "Done"
done
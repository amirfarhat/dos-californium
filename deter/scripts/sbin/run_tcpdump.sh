#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

node_type=$1

if [[ $node_type == "proxy" ]]; then
  sleep_amt=$PROXY_DURATION
  rm -f $TMP_DATA/$PROXY_TCPDUMP
  touch $TMP_DATA/$PROXY_TCPDUMP
  eval "tcpdump -n -i any port '($ORIGIN_SERVER_PORT or $PROXY_COAP_PORT or $RECEIVER_COAP_PORT)' -w $TMP_DATA/$PROXY_TCPDUMP &"

elif [[ $node_type == "attacker" ]]; then
  sleep_amt=$PROXY_DURATION
  rm -f $TMP_DATA/$ATTACKER_TCPDUMP
  touch $TMP_DATA/$ATTACKER_TCPDUMP
  tcpdump -n -i any udp port $PROXY_COAP_PORT -w $TMP_DATA/$ATTACKER_TCPDUMP &

elif [[ $node_type = "origin_server" ]]; then
  sleep_amt=$ORIGIN_SERVER_DURATION
  rm -f $TMP_DATA/$ORIGIN_SERVER_TCPDUMP
  touch $TMP_DATA/$ORIGIN_SERVER_TCPDUMP
  tcpdump -n -i any port $ORIGIN_SERVER_PORT -w $TMP_DATA/$ORIGIN_SERVER_TCPDUMP &

elif [[ $node_type == "receiver" ]]; then
  sleep_amt=$RECEIVER_DURATION
  rm -f $TMP_DATA/$RECEIVER_TCPDUMP
  touch $TMP_DATA/$RECEIVER_TCPDUMP
  tcpdump -n -i any udp port $RECEIVER_COAP_PORT -w $TMP_DATA/$RECEIVER_TCPDUMP &

elif [[ $node_type == "client" ]]; then
  sleep_amt=$CLIENT_DURATION
  numbered_client="$(hostname | awk '{print tolower($0)}' | tr "." "\n" | head -1)"
  client_tcpdump="${numbered_client}_dump.pcap"
  rm -f $TMP_DATA/$client_tcpdump
  touch $TMP_DATA/$client_tcpdump
  tcpdump -n -i any udp port $PROXY_COAP_PORT -w $TMP_DATA/$client_tcpdump &

else
  echo "Unknown parameter"
  exit 1
fi

tcpdump_pid=$!

sleep $sleep_amt

sudo kill $tcpdump_pids
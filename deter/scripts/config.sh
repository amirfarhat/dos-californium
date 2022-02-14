#!/bin/bash

host_name=$(hostname | awk '{print tolower($0)}')

# Decide where home is, based on the current device host name
if [[ $host_name == *"deter"* ]]; then
  CF_HOME="/proj/MIT-DoS/exp/coap-setup/deps/dos-californium"
elif [[ $host_name == *"amir"* ]]; then
  CF_HOME="/Users/amirfarhat/workplace/research/dos-californium"
else
  CF_HOME="/home/ubuntu/dos-californium"
fi

# Home directories
DETER_HOME="$CF_HOME/deter"
IPS_HOME="$DETER_HOME/ips"
IPS_TOPO="$IPS_HOME/topo.ns"
IPS_FILE="$IPS_HOME/ips.txt"
SCRIPTS_HOME="$DETER_HOME/scripts"
BIN_HOME="$SCRIPTS_HOME/sbin"
TOPOLOGIES_HOME="$SCRIPTS_HOME/topologies"
EXPDATA_HOME="$DETER_HOME/expdata"
UTILS_HOME="$DETER_HOME/utils"
TMP="/tmp"
TMP_DATA="$TMP/data"

# Locations of specific files
CF_PROXY_JAR="$CF_HOME/demo-apps/run/cf-proxy2-3.2.0.jar"
PROPERTIES_FILE_NAME="DoSProxy.properties"
PROPERTIES_FILE="$UTILS_HOME/$PROPERTIES_FILE_NAME"

RUN_USER="amirf"

# Binary toggles
TCPDUMP=1
DO_PROXY_LOGGING=0
MONITOR_PROXY_CPU=1
MONITOR_PROXY_MEMORY=1
MONITOR_ORIGIN_SERVER_CPU=1
MONITOR_ORIGIN_SERVER_MEMORY=1
DO_JAVA_PROFILING=0
RUN_ATTACKER=0
RUN_CLIENTS=1

TOPOLOGY_NAME="newrealA"

# General tunable parameters
CPU_SAMPLING_INTERVAL=1
NUM_CLIENT_MESSAGES=100000000
NUM_CLIENTS=1
PROFILING_EVENT="cpu"
PROXY_HEAP_SIZE_MB="8000"
# Note these are not configurable from here -- go to the apache server's configuration
SERVER_CONNECTIONS=256
MAX_KEEP_ALIVE_REQUESTS=0 # 0 means infinite requests per connection. Anything larger terminates the connection when reaching that many requests

# Tunable durations
ORIGIN_SERVER_DURATION=120
PROXY_DURATION=120 
ATTACKER_START_LAG_DURATION=20
ATTACKER_DURATION=20
RECEIVER_DURATION=120
CLIENT_DURATION=100
PAUSE_TIME=5 # Pause time after launching infra
WAIT_TIME=10 # Wait time after experiment finishes

# Java Perf Profiling
FLAMEGRAPH_NAME="flamegraph.svg"
PROFILER_DIR_NAME="async-profiler-1.8.4-linux-x64"
PROFILE_BINARY_NAME="$PROFILER_DIR_NAME.tar.gz"
PROFILE_BINARY_URL="https://github.com/jvm-profiling-tools/async-profiler/releases/download/v1.8.4/$PROFILE_BINARY_NAME"

# Origin server
ORIGIN_SERVER_NAME="originserver.coap-setup.MIT-DoS.isi.deterlab.net"
ORIGIN_SERVER_TCPDUMP="server_dump.pcap"
ORIGIN_SERVER_PERF="server_perf.data"
ORIGIN_SERVER_ACCESS_LOGNAME="server_access.log"
ORIGIN_SERVER_ERROR_LOGNAME="server_error.log"
ORIGIN_SERVER_CPU_FILENAME="server.cpu.metric.out"
ORIGIN_SERVER_MEMORY_FILENAME="server.memory.metric.out"
ORIGIN_SERVER_PORT=80

# Receiver
RECEIVER_NAME="receiver.coap-setup.MIT-DoS.isi.deterlab.net"
RECEIVER_TCPDUMP="receiver_dump.pcap"
RECEIVER_COAP_PORT="5683"

# Attacker
ATTACKER_NAME="attacker.coap-setup.MIT-DoS.isi.deterlab.net"
ATTACKER_TCPDUMP="attacker_dump.pcap"
ATTACKER_PERF="attacker_perf.data"
ATTACKER_LOGNAME="attacker.log"
ATTACKER_SPOOFED_PORT=$RECEIVER_COAP_PORT

# Proxy
PROXY_NAME="proxy.coap-setup.MIT-DoS.isi.deterlab.net"
PROXY_TCPDUMP="proxy_dump.pcap"
PROXY_PERF="proxy_perf.data"
PROXY_LOGNAME="proxy.log"
PROXY_CPU_FILENAME="proxy.cpu.metric.out"
PROXY_MEMORY_FILENAME="proxy.memory.metric.out"
PROXY_COAP_PORT="5683"

# Proxy config found in properties file
NUM_PROXY_CONNECTIONS="50"
REQUEST_TIMEOUT="5[s]"
MAX_RETRIES="2"
KEEP_ALIVE_DURATION="5[s]"
REQUEST_RETRY_INTERVAL="1[s]"
REUSE_CONNECTIONS="true"
PROXY_PROPERTIES=(
  "NUM_PROXY_CONNECTIONS"
  "REQUEST_TIMEOUT"
  "MAX_RETRIES"
  "KEEP_ALIVE_DURATION"
  "REQUEST_RETRY_INTERVAL"
  "REUSE_CONNECTIONS"
)

# Clients
BASE_CLIENT_NAME_SUFFIX=".coap-setup.MIT-DoS.isi.deterlab.net"
CLIENTS=()
for ((i=1; i<=$NUM_CLIENTS; i++)); do 
  CLIENTS+=("client${i}${BASE_CLIENT_NAME_SUFFIX}");
done

# Collection of all hosts
HOST_NAMES=(
  "$ATTACKER_NAME"
  "$ORIGIN_SERVER_NAME"
  "$PROXY_NAME"
  "$RECEIVER_NAME"
  "${CLIENTS[@]}"
)
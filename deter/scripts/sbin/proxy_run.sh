#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Make sure there are no java procs running
while [[ ! -z `pgrep java` ]]; do
  next_pid=`pgrep java | tail -1`
  echo "Killing $next_pid..."
  sudo kill -9 $next_pid
done

# Clean previous data
sudo rm -f $TMP_DATA/$PROXY_LOGNAME
sudo rm -f $TMP_DATA/$FLAMEGRAPH_NAME

# Create log file
sudo touch $TMP_DATA/$PROXY_LOGNAME

# Proxy arguments to JVM
proxy_args="-Xmx${PROXY_HEAP_SIZE_MB}m"
if [[ $DO_JAVA_PROFILING -eq 1 ]]; then
  # Set kernel parameters to enable perf profiling
  sudo sysctl -w kernel.perf_event_paranoid=1
  sudo sysctl -w kernel.kptr_restrict=0
  proxy_args+=" -XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints"
fi

# Determine which proxy to run, based on the DTLS toggle
proxy_class=""
if [[ $RUN_PROXY_WITH_DTLS -eq 1 ]]; then
  proxy_class="DoSOptimizedDTLSProxy"
else
  proxy_class="DoSOptimizedForwardingProxy"
fi

# If we are running the proxy's egress with HTTPS, we must enable a java agent
# to log the TLS secrets for later decryption
keylog_javaagent=""
if [[ $RUN_PROXY_WITH_HTTPS -eq 1 ]]; then
  # Set up proxy keylogfile java agent for TLS
  proxy_keylogfile="$TMP_DATA/$PROXY_KEYLOGFILE_NAME"
  sudo touch $proxy_keylogfile
  sudo chmod 666 $proxy_keylogfile
  sudo bash -c "echo -n > $proxy_keylogfile"
  keylog_javaagent="-javaagent:$JSSL_KEYLOG_JAR==$proxy_keylogfile"
fi

# Run the proxy with proxy log
((sudo java $keylog_javaagent $proxy_args -jar $CF_PROXY_JAR $proxy_class) 2>&1 > $TMP_DATA/$PROXY_LOGNAME) &

# Wait until proxy pid shows up
while [[ -z `pgrep java` ]]; do
  sleep 0.1
done
sleep 1

# Get PID of proxy
proxy_pid=`pgrep java`
echo "Ran proxy with pid $proxy_pid..."

# Start profiler
if [[ $DO_JAVA_PROFILING -eq 1 ]]; then
  cd $UTILS_HOME/$PROFILER_DIR_NAME
  echo "Starting profiling..."
  sudo ./profiler.sh start -t -e $PROFILING_EVENT $proxy_pid
  cd ~
fi

echo "Sleeping for $PROXY_DURATION seconds..."
sleep $PROXY_DURATION
echo "Woke up"

if [[ $DO_JAVA_PROFILING -eq 1 ]]; then
  # Create and prepare the flamegraph svg
  sudo touch $TMP_DATA/$FLAMEGRAPH_NAME
  sudo chmod 666 $TMP_DATA/$FLAMEGRAPH_NAME

  # Stop profiling and dump output
  cd $UTILS_HOME/$PROFILER_DIR_NAME
  echo "Stopping profiling..."
  sudo ./profiler.sh stop -f $TMP_DATA/$FLAMEGRAPH_NAME --width 1500 --title $PROFILING_EVENT $proxy_pid
  cd ~
fi

# Kill proxy
echo "Killing $proxy_pid..."
sudo kill -9 $proxy_pid

# Kill all other java procs
while [[ ! -z `pgrep java` ]]; do
  next_pid=`pgrep java | tail -1`
  echo "Killing $next_pid..."
  sudo kill -9 $next_pid
done
#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

# Expect: Forked californium from source: https://github.com/amirfarhat/dos-californium
if [[ ! -d $CF_HOME ]]; then
  echo "Base CF package not found"
  exit 1
fi

# Get Java async profiler
if [[ ! -d $UTILS_HOME/$PROFILER_DIR_NAME  ]]; then
  cd $UTILS_HOME
  wget $PROFILE_BINARY_URL
  tar xzvf $PROFILE_BINARY_NAME
fi

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')

# Install utilities
sudo apt install -y iperf traceroute moreutils apache2 httpie linux-tools-generic linux-cloud-tools-generic linux-tools-4.15.0-112-generic linux-cloud-tools-4.15.0-112-generic openjdk-11-dbg

# Install Java: JDK, JRE
sudo apt install -y openjdk-11-jdk openjdk-11-jre

# Install pip and python-mbedtls
sudo apt install -y python3-pip
pip3 install -i https://fbsd-build.isi.deterlab.net/pypi/web/simple python-mbedtls

# Configure Apache HTTP Server
if [[ $my_hostname == "originserver" ]]; then
  sudo bash $SCRIPTS_HOME/setup_apache_http_server_ssl.sh
fi

# Set custom bashrc
yes | sudo cp $UTILS_HOME/.bashrc ~/.bashrc
source ~/.bashrc
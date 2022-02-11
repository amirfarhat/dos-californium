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

# Install utilities
sudo apt install -y iperf traceroute moreutils apache2 httpie linux-tools-generic linux-cloud-tools-generic linux-tools-4.15.0-112-generic linux-cloud-tools-4.15.0-112-generic openjdk-11-dbg

# Install Java: JDK, JRE
sudo apt install -y openjdk-11-jdk openjdk-11-jre

# Configure Apache
yes | sudo cp $UTILS_HOME/index.html /var/www/html/index.html
yes | sudo cp $UTILS_HOME/apache2.conf /etc/apache2/apache2.conf
yes | sudo cp $UTILS_HOME/.htaccess /var/www/html/.htaccess
# Enable rewrite module so that requests to any URL will return 200
sudo a2enmod rewrite
# Replace server's mpm_event configuration with our custom configuration file
sudo bash -c "echo -n > /etc/apache2/mods-available/mpm_event.conf"
sudo bash -c "cat $UTILS_HOME/mpm_event.conf > /etc/apache2/mods-available/mpm_event.conf"

# Set custom bashrc
yes | sudo cp $UTILS_HOME/.bashrc ~/.bashrc
source ~/.bashrc
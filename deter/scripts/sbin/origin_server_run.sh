#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')

# Clear server access and error logs
rm -f $TMP_DATA/$ORIGIN_SERVER_ACCESS_LOGNAME
touch $TMP_DATA/$ORIGIN_SERVER_ACCESS_LOGNAME
rm -f $TMP_DATA/$ORIGIN_SERVER_ERROR_LOGNAME
touch $TMP_DATA/$ORIGIN_SERVER_ERROR_LOGNAME

# Reset the previous keylog file to clean slate
server_keylogfile="$HOME/$my_hostname.keylogfile.txt"
sudo touch $server_keylogfile
sudo chmod 666 $server_keylogfile
sudo bash -c "echo -n > $server_keylogfile"

# Add libsslkeylog.so to the apache HTTP server. Note that we clear this override file 
# before adding the data. Further, we need to add write permissions to the service 
# configuration overrides in order to add libsslkeylog.so
apache_serviced_home="/etc/systemd/system/apache2.service.d"
sudo mkdir -p $apache_serviced_home
override_file="$apache_serviced_home/override.conf"
sudo touch $override_file
sudo chmod 666 $override_file
sudo bash -c "echo -n > $override_file"
echo "[Service]" >> $override_file
echo "Environment=LD_PRELOAD=/usr/local/lib/libsslkeylog.so" >> $override_file
echo -n "Environment=SSLKEYLOGFILE=$server_keylogfile" >> $override_file

# Refresh systemctl daemon for apache2
sudo systemctl daemon-reload

# Start server async, sleep, then kill
sudo /etc/init.d/apache2 start
sudo /etc/init.d/apache2 restart
sleep $ORIGIN_SERVER_DURATION
sudo /etc/init.d/apache2 stop

# Copy server access log
sudo cp /var/log/apache2/access.log $TMP_DATA/$ORIGIN_SERVER_ACCESS_LOGNAME
sudo rm /var/log/apache2/access.log

# Copy server error log
sudo cp /var/log/apache2/error.log $TMP_DATA/$ORIGIN_SERVER_ERROR_LOGNAME
sudo rm /var/log/apache2/error.log

# Copy server keylog file
sudo cp $server_keylogfile $TMP_DATA
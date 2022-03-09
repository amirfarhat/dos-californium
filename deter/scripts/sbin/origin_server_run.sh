#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')

# Clear server access and error logs
sudo mkdir -p $TMP_DATA
rm -f $TMP_DATA/$ORIGIN_SERVER_ACCESS_LOGNAME
touch $TMP_DATA/$ORIGIN_SERVER_ACCESS_LOGNAME
rm -f $TMP_DATA/$ORIGIN_SERVER_ERROR_LOGNAME
touch $TMP_DATA/$ORIGIN_SERVER_ERROR_LOGNAME

# Reset the previous keylog file to clean slate
server_keylogfile="$TMP_DATA/$ORIGIN_SERVER_KEYLOGFILE_NAME"
sudo touch $server_keylogfile
sudo chmod 666 $server_keylogfile
sudo bash -c "echo -n > $server_keylogfile"

# Add libsslkeylog.so to the apache HTTP server. systemd uses editor for overrides, so this is a
# hack to trick the systemd editor to accept input from stdin: https://bbs.archlinux.org/viewtopic.php?id=195782
echo -en "[Service]\nEnvironment=LD_PRELOAD=/usr/local/lib/libsslkeylog.so\nEnvironment=SSLKEYLOGFILE=$server_keylogfile" | sudo SYSTEMD_EDITOR=tee systemctl edit apache2

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
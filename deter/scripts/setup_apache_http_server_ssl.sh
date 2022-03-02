#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

my_hostname=$(hostname | awk '{ ORS="" } {split($0, a, "."); print a[1]}')

# Add main file the site will serve
yes | sudo cp $UTILS_HOME/index.html /var/www/html/index.html

# Add configuration files
yes | sudo cp $UTILS_HOME/apache2.conf /etc/apache2/apache2.conf
yes | sudo cp $UTILS_HOME/.htaccess /var/www/html/.htaccess

# Enable rewrite module so that requests to any URL will return 200
sudo a2enmod rewrite

# Replace server's mpm_event configuration with our custom configuration file
sudo bash -c "echo -n > /etc/apache2/mods-available/mpm_event.conf"
sudo bash -c "cat $UTILS_HOME/mpm_event.conf > /etc/apache2/mods-available/mpm_event.conf"

# Set up libsslkeylog.so to log SSL secret keys
cd $WS_NOTES_HOME
sudo apt install git make gcc libssl-dev
make -B
sudo install libsslkeylog.so /usr/local/lib/

# Add libsslkeylog.so to the apache HTTP server. Note that we need to add write permissions
# to the service configuration overrides in order to add libsslkeylog.so
override_file="/etc/systemd/system/apache2.service.d/override.conf"
touch $override_file
sudo bash -c "echo -n > $override_file"
sudo chmod 666 $override_file
echo "[Service]" >> $override_file
echo "Environment=LD_PRELOAD=/usr/local/lib/libsslkeylog.so" >> $override_file
echo -n "Environment=SSLKEYLOGFILE=/users/amirf/$my_hostname.keylogfile.txt" >> $override_file

# Copy SSL private key and certificate to server
yes | sudo cp $UTILS_HOME/apache-selfsigned.key /etc/ssl/private/apache-selfsigned.key
yes | sudo cp $UTILS_HOME/apache-selfsigned.crt /etc/ssl/certs/apache-selfsigned.crt

# Configure SSL to use key and certificate above
ssl_site="/etc/apache2/sites-available/default-ssl.conf"
sudo chmod 666 $ssl_site
sudo bash -c "echo -n > $ssl_site"
sudo bash -c "cat $UTILS_HOME/default-ssl.conf > $ssl_site"

# Enable ssl module so Apache HTTP server can speak HTTPS
sudo a2enmod ssl
sudo a2enmod headers
sudo a2ensite default-ssl
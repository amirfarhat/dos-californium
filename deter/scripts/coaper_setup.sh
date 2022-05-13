#!/bin/bash

# Assume we have a fresh 20.04 machine

# Install the code repo: might need ssh keys
cd ~
git clone https://github.com/amirfarhat/dos-californium
cd dos-californium
git checkout dos

# Install postgres 14
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get -y install postgresql-14

# Configure the postgres user to have total access to the database
# by opening the file /etc/postgresql/14/main/pg_hba.conf and editing
# the trust level of the local postgres user to trusted, by changing
# the configuration line from
# from
# > local all postgres peer
# to
# > local all postgres trust

# Then, you need to specify the password for the the postgres user.
# Our scripts use the password `coap`. To do this, you can open
# up a postgres terminal with psql and alter the password of the
# postgres user, as follows:
# > psql -U postgres template
# > ALTER ROLE postgres WITH PASSWORD 'coap';

# Finally, create the default database `experiments` using the command below.
# If it fails, make sure to read the comments above and run those to completion.
(sudo su postgres -c "psql template1 -c 'CREATE DATABASE experiments'" || true) > /dev/null 2>&1

# Install pip3
sudo apt install python3-pip

# Install numpy
pip3 install numpy

# Install jupyter
pip3 install jupyter

# Install psycopg2-binary
pip3 install psycopg2-binary

# Install pandas
pip3 install pandas

# Install plotly
pip3 install plotly

# Install seaborn
pip3 install seaborn

# Install polars
pip3 install polars

# Install modin for pandas
pip3 install modin
pip3 install "modin[all]"

# Install matplotlib
pip3 install matplotlib

# Install jq, pypy
sudo apt-get install -y jq pypy3

# Install tshark separately because it will prompt for a screen
sudo apt-get install tshark

# Install clickhouse
curl https://clickhouse.com/ | sh
sudo ./clickhouse install
pip3 install clickhouse-driver[lz4,zstd,numpy]
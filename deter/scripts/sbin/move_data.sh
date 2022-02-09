#!/bin/bash

source /proj/MIT-DoS/exp/coap-setup/deps/dos-californium/deter/scripts/config.sh

data_dir=$1

sudo mv $TMP_DATA/* $data_dir
#!/bin/bash

# Parse inputs
me=`basename "$0"`
input_file=$1
output_file=$2
keylog_file=$3
if [[ -z "$input_file" ]] || [[ -z "$output_file" ]] || [[ -z "$keylog_file" ]]; then
  echo "$me: Usage [input_file] [output_file] [keylog_file]"
  exit 1
fi

# Read the pre-shared key for decryption
psk=$(cat $PSK_FILE)

filter="tls || dtls || (tcp && !http)"

# Run tshark in the backend to handle parsing and 
# high-level protocol filtering
(tshark \
  -o dtls.psk:"$psk" \
  -o tls.keylog_file:"$keylog_file" \
  -r "$input_file" \
  -2 \
  -n \
  -R "$filter" \
  -t r \
  -T fields \
    -e _ws.col.Time \
    -e _ws.col.Source \
    -e _ws.col.Destination \
    -e tcp.srcport \
    -e tcp.dstport \
    -e _ws.col.Length \
    -e _ws.col.Protocol \
    -e tcp.flags.syn \
    -e tcp.flags.fin \
    -e _ws.col.Info \
  -E header=y \
  -E separator=";" \
  -E quote=d \
  -E occurrence=f) > $output_file
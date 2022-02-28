#!/bin/bash

source /home/ubuntu/dos-californium/deter/scripts/config.sh

# Parse inputs
me=`basename "$0"`
input_file=$1
output_file=$2
if [[ -z "$input_file" ]] || [[ -z "$output_file" ]]; then
  echo "$me: Usage [input_file] [output_file]"
  exit 1
fi

# Read the pre-shared key for decryption
psk=$(cat $PSK_FILE)

filter="coap || http"

# Run tshark in the backend to handle parsing and 
# high-level protocol filtering
(tshark \
  -o dtls.psk:"$psk" \
  -r "$input_file" \
  -2 \
  -n \
  -R "$filter" \
  -t e \
  -T fields \
    -e _ws.col.Time \
    -e _ws.col.Source \
    -e _ws.col.Destination \
    -e _ws.col.Protocol \
    -e _ws.col.Length \
    -e coap.type \
    -e coap.retransmitted \
    -e coap.code \
    -e coap.mid \
    -e coap.token \
    -e coap.opt.proxy_uri \
    -e http.request \
    -e http.request.method \
    -e http.request.full_uri \
    -e http.response \
    -e http.response.code \
    -e http.response.code.desc \
    -e http.response_for.uri \
  -E header=y \
  -E separator=";" \
  -E quote=d \
  -E occurrence=f) > "$output_file"
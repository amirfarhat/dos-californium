import os
import csv
import sys
import json
import argparse

from pprint import pprint

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-n', '--expname', dest='expname',
                      help='', action='store', type=str)
  parser.add_argument('-c', '--config', dest='config',
                      help='', action='store', type=str)
  parser.add_argument('-e', '--expinfo', dest='expinfo',
                      help='', action='store', type=str)
  parser.add_argument('-t', '--topo', dest='topo',
                      help='', action='store', type=str)
  parser.add_argument('-o', '--outconfig', dest='outconfig',
                      help='', action='store', type=str)
  parser.add_argument('-r', '--num-trials', dest='num_trials',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

def parse_topo(config_dict):
  # Parse each manually made IP
  NS_IP_PREFIX = "tb-set-ip $"
  with open(args.topo, "r") as f:
    for L in f:
      if L.startswith(NS_IP_PREFIX):
        # Case: IP addresses assigned to hosts
        dollar_host, ip = L.split()[1:]
        host = dollar_host.lstrip("$")
        
        # Write IP addr of this host
        config_dict.setdefault("hosts", dict())
        config_dict["hosts"].setdefault(host, dict())
        config_dict["hosts"][host]["ip"] = ip
      
      elif L.startswith("set attackrate"):
        parts = L.split()
        assert parts[1] == "attackrate"
        attackrate = parts[2]
        config_dict["attack_rate"] = attackrate.lower()

def parse_expinfo(config_dict):
  with open(args.expinfo, "r") as f:
    in_core_block = False
    for L in f:
      L = L.rstrip("\n")
      if L.startswith("Physical Node Mapping:"):
        in_core_block = True
        continue
      if in_core_block:
        if L.startswith("ID") or L.startswith("---------------"):
          continue
        elif L in {"\n", " ", ""}:
          in_core_block = False
          continue
        parts = L.split()
        if not parts[0].startswith("router"):
          host = parts[0]
          host_hw = parts[1]
          host_os = parts[2]
          config_dict["hosts"][host]["hardware"] = host_hw.lower()
          config_dict["hosts"][host]["operating_system"] = host_os.lower()

def parse_config(config_dict):
  config_dict["num_clients"] = os.environ["NUM_CLIENTS"]
  config_dict["topology_name"] = os.environ["TOPOLOGY_NAME"]
  config_dict["pause_time"] = os.environ["PAUSE_TIME"]
  config_dict["wait_time"] = os.environ["WAIT_TIME"]
  config_dict["server_connections"] = os.environ["SERVER_CONNECTIONS"]
  config_dict["proxy_heap_size_mb"] = os.environ["PROXY_HEAP_SIZE_MB"]
  config_dict["origin_server_duration"] = os.environ["ORIGIN_SERVER_DURATION"]
  config_dict["attacker_duration"] = os.environ["ATTACKER_DURATION"]
  config_dict["receiver_duration"] = os.environ["RECEIVER_DURATION"]
  config_dict["proxy_duration"] = os.environ["PROXY_DURATION"]
  config_dict["client_duration"] = os.environ["CLIENT_DURATION"]
  config_dict["attacker_start_lag_duration"] = os.environ["ATTACKER_START_LAG_DURATION"]
  config_dict["max_keep_alive_requests"] = os.environ.get("MAX_KEEP_ALIVE_REQUESTS", "100") # 100 for backwards compatibility

  config_dict["num_proxy_connections"] = os.environ["NUM_PROXY_CONNECTIONS"]
  config_dict["request_timeout"] = os.environ["REQUEST_TIMEOUT"]
  config_dict["max_retries"] = os.environ["MAX_RETRIES"]
  config_dict["keep_alive_duration"] = os.environ["KEEP_ALIVE_DURATION"]
  config_dict["request_retry_interval"] = os.environ["REQUEST_RETRY_INTERVAL"]
  config_dict["reuse_connections"] = os.environ["REUSE_CONNECTIONS"]

def main():
  config_dict = dict()
  config_dict["expname"] = args.expname
  config_dict["num_trials"] = args.num_trials

  # Populate config from different files
  parse_config(config_dict)
  parse_topo(config_dict)
  parse_expinfo(config_dict)

  # Write config to out config file
  with open(args.outconfig, 'w') as f:
    json.dump(config_dict, f)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
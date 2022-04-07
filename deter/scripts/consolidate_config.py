import os
import json
import argparse

from collections import defaultdict

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
  # Collect config variable names from the config script
  vars = set()
  with open(args.config, "r") as f:
    for L in f.readlines():
      L = L.rstrip("\n")
      if L.count("=") == 1:
        parts = L.split("=")
        variable = parts[0]
        if variable.startswith(" ") or variable.islower():
          continue
        vars.add(variable)
  
  # Define value fetcher for config variables exposed to the environment
  def get_variable_value(varname):
    try:
      value = os.environ[varname.upper()]
    except KeyError:
      return ""
    
    idx = value.find("[")
    if idx > -1:
      value = value[:idx]
    
    return value
    
  # Construct dispatch table which returns a fetcher/parser for each configuration variable
  dispatch_table = defaultdict(lambda : get_variable_value)
  dispatch_table["max_keep_alive_requests"] = lambda _: os.environ.get("MAX_KEEP_ALIVE_REQUESTS", "100") # 100 for backwards compatibility

  # Then populate our config dict using the dispatch table
  for varname in vars:
    config_dict[varname.lower()] = dispatch_table[varname](varname)

def main():
  config_dict = dict()
  config_dict["expname"] = args.expname
  config_dict["num_trials"] = args.num_trials

  # Populate config from different files
  parse_config(config_dict)
  parse_topo(config_dict)
  parse_expinfo(config_dict)

  # Zero out the attack rate if there is no attacker running
  if config_dict["run_attacker"] == "0":
    config_dict["attack_rate"] = "0mbps"

  # Write config to out config file
  with open(args.outconfig, 'w') as f:
    json.dump(config_dict, f)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
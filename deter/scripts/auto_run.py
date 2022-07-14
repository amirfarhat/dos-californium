#!/usr/bin/env python2

import os
import sys
import signal
import argparse
import itertools
from pprint import pprint

### You likely do not need to change the code
### anywhere in the blocks below, except where
### specified.

def parse_args():
  parser = argparse.ArgumentParser(description = '')
  parser.add_argument('-c', '--config', dest='config',
                      help='', action='store', type=str)
  parser.add_argument('-r', '--run', dest='run',
                      help='', action='store', type=str)
  args = parser.parse_args()
  args.scripts_dir = os.path.abspath(os.path.join(args.run, os.pardir))
  return args

def seralize(v):
  """
  Helper to serialize python types to bash types.
  """
  if isinstance(v, int):
    return str(v)
  elif isinstance(v, str):
    return '"' + v + '"'
  else:
    raise NotImplementedError("Cannot serialize type " + type(v) + " to bash script yet.")

def modify_config(exp_dict, config_file_path):
  """
  Overwrite the specified config file's config variable 
  values with values found to be in `exp_dict`. Keeps 
  all non-matching lines untouched.
  """
  out_lines = list()
  with open(config_file_path, 'r') as f:
    for L in f:
      parts = L.split("=")
      if len(parts) == 2 and parts[0] in exp_dict["config"]:
        # In this case, this line contains a configuration
        # variable whose value we want to set, so we set
        # the new value before proceeding.
        parts[1] = seralize(exp_dict["config"][parts[0]]) + os.linesep
      
      # Add the (potentially modified) config line to the
      # output lines.
      out_lines.append("=".join(parts))

  with open(config_file_path, "w") as f:
    f.writelines(out_lines)

def make_exp_name(base_exp_name, config_value_tuple):
  """
  Create and return experiment name based on concrete
  chosen values for varied configuration variables.
  """
  out = base_exp_name
  for i, (config_name, _) in enumerate(CONFIG_NAME_MAP_VALUE_PERTURBATIONS):
    config_value = config_value_tuple[i]
    out += "_" + CONFIG_NAME_MAP_GET_READABLE_VALUE_FUNC[config_name](config_value)
  return out

def make_experiment_runs():
  """
  Create and return a list of experiment runs, where each
  run is a dictionary mapping configuration variables names 
  to the values they should take on in their experiment run.
  """
  return [
    # Dictionary of core experiment metadata and 
    # varied configuration variables. 
    {
      "exp_name"  : make_exp_name(BASE_EXP_NAME, config_value_tuple),
      "num_trials": NUM_TRIALS,
      "config": {
        first_item(CONFIG_NAME_MAP_VALUE_PERTURBATIONS[i]): value
          for i, value in enumerate(config_value_tuple)
      }
    }
    for config_value_tuple in itertools.product(*map(second_item, CONFIG_NAME_MAP_VALUE_PERTURBATIONS))
  ]

# Extract the items of a tuple by position.
first_item  = lambda t: t[0]
second_item = lambda t: t[1]

def fmt_decimal(v):
  """
  >>> fmt_decimal(1)
  '1'
  >>> fmt_decimal(2)
  '2'
  >>> fmt_decimal(29)
  '29'
  >>> fmt_decimal(1.0)
  '1o0'
  >>> fmt_decimal(1.5)
  '1o5'
  >>> fmt_decimal(2.0)
  '2o0'
  >>> fmt_decimal(98.76)
  '98o76'
  """
  return "o".join(str(v).split("."))

def fmt_unitted(v):
  """
  >>> fmt_unitted("1[s]")
  '1sec'
  >>> fmt_unitted("2[s]")
  '2sec'
  >>> fmt_unitted("10[s]")
  '10sec'
  >>> fmt_unitted("99[s]")
  '99sec'
  >>> fmt_unitted("12.3[s]")
  '12o3sec'
  """
  return fmt_decimal(v).replace("[s]", "sec")

# Map a configuration variable name to a 
# single-argument function which converts its
# supplied configuration variable value argument
# to a human-readable equivalent.
CONFIG_NAME_MAP_GET_READABLE_VALUE_FUNC = {
  "RUN_ATTACKER"               : lambda v: {1: "withattacker" , 0: "noattacker"}[v],
  "RUN_PROXY_WITH_DTLS"        : lambda v: {1: "dtls" , 0: "coap"}[v],
  "RUN_PROXY_WITH_HTTPS"       : lambda v: {1: "https", 0: "http"}[v],
  "NUM_PROXY_CONNECTIONS"      : lambda v: "{}proxyconns".format(v),
  "PROXY_HEAP_SIZE_MB"         : lambda v: "{}MBheap".format(v),
  "NUM_CLIENTS"                : lambda v: "{}clients".format(v),
  "PROXY_DURATION"             : lambda v: "{}sec_proxy".format(v),
  "ATTACKER_DURATION"          : lambda v: "{}sec_attacker".format(v),
  "CLIENT_DURATION"            : lambda v: "{}sec_client".format(v),
  "REUSE_CONNECTIONS"          : lambda v: {"true": "reuseconns" , "false": "noconnreuse"}[v],
  "REQUEST_TIMEOUT"            : lambda v: "{}_pxyto".format(fmt_unitted(v)),
  "ACK_TIMEOUT"                : lambda v: "{}_ackto".format(fmt_unitted(v)),
  "ACK_TIMEOUT_SCALE"          : lambda v: "{}_acktoscale".format(fmt_decimal(v)),
  "ORIGIN_SERVER_DURATION"     : lambda v: "",
  "ATTACKER_START_LAG_DURATION": lambda v: "",
  "RECEIVER_DURATION"          : lambda v: "",
}

###
### Change the values for the variables below
###

# Map from configuration variable names to
# collections of the desired value ranges they
# should take on in a cartesian product.
# Aligner: https://www.browserling.com/tools/text-format-columns
CONFIG_NAME_MAP_VALUE_PERTURBATIONS = [
  # Clients
  ( "NUM_CLIENTS",                 [8] ),

  # Attack
  ( "RUN_ATTACKER",                [0, 1] ),

  # Proxy
  ( "PROXY_HEAP_SIZE_MB",          ["8000"] ),
  ( "NUM_PROXY_CONNECTIONS",       ["50"] ),
  ( "REQUEST_TIMEOUT",             ["5[s]"] ),
  ( "REUSE_CONNECTIONS",           ["true", "false"] ),

  # Transport protocols
  ( "RUN_PROXY_WITH_DTLS",         [0, 1] ),
  ( "RUN_PROXY_WITH_HTTPS",        [1] ),

  # Durations
  ( "ORIGIN_SERVER_DURATION",      [140] ),
  ( "PROXY_DURATION",              [140] ),
  ( "ATTACKER_START_LAG_DURATION", [30] ),
  ( "ATTACKER_DURATION",           [30] ),
  ( "RECEIVER_DURATION",           [140] ),
  ( "CLIENT_DURATION",             [120] ),
]

# Base name of the experiment to build on with
# varied configuration variable values, along
# with number of trials to run the experiment for.
BASE_EXP_NAME = "thesis_group_proxy_connection_reuse"
NUM_TRIALS    = 5

###
### The code below runs the main experiment
### loop by updating the configuration file
### then running the experiments with it.
###

def run_child(raw_run_args):
  try:
    os.system(raw_run_args)
  except KeyboardInterrupt:
    print("pid " + str(os.getpid()) + " interrupted. Exitting.")

def wait_for_child(child_pid):
  try:
    os.wait()
  except KeyboardInterrupt:
    print("Parent interrupted. Killing child pid " + str(child_pid) + " and exitting.")
    os.kill(child_pid, signal.SIGKILL)
  finally:
    sys.exit(0)

def main():
  args = parse_args()
  experiment_runs = make_experiment_runs()

  # Display the experiments and ask the user to review
  # them before moving forward with experiment running.
  for exp_dict in experiment_runs:
    pprint(exp_dict)
  user_input = raw_input("Do these " + str(len(experiment_runs)) + " experiments look OK? [y/n]? ").lower()
  if user_input == "n":
    sys.exit(0)

  for exp_dict in experiment_runs:
    # Modify config file in-place.
    modify_config(exp_dict, args.config)

    # Then run the experiment with the new config in
    # a child process and wait for it to finish before
    # starting the next experiment.
    raw_run_args = "bash {}  -v -n {} -x {}".format(
      args.run,
      str(NUM_TRIALS),
      exp_dict["exp_name"],
    )
    pid = os.fork()
    if pid == 0:
      run_child(raw_run_args)
    else:
      wait_for_child(pid)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
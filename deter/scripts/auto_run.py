#!/usr/bin/env python2

import os
import argparse
import itertools

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

# Map a configuration variable name to a 
# single-argument function which converts its
# supplied configuration variable value argument
# to a human-readable equivalent.
CONFIG_NAME_MAP_GET_READABLE_VALUE_FUNC = {
  "RUN_ATTACKER"        : lambda v: {1: "withattacker" , 0: "noattacker"}[v],
  "RUN_PROXY_WITH_DTLS" : lambda v: {1: "dtls" , 0: "coap"}[v],
  "RUN_PROXY_WITH_HTTPS": lambda v: {1: "https", 0: "http"}[v],
  "NUM_CLIENTS"         : lambda v: "{}clients".format(v),
}

###
### Change the values for the variables below
###

# Map from configuration variable names to
# collections of the desired value ranges they
# should take on in a cartesian product.
CONFIG_NAME_MAP_VALUE_PERTURBATIONS = [
  ("RUN_PROXY_WITH_DTLS" , range(2)),
  ("RUN_PROXY_WITH_HTTPS", range(2)),
  ("NUM_CLIENTS"         , range(1, 8+1, 1)),
  ("RUN_ATTACKER"        , [0]),
]

# Base name of the experiment to build on with
# varied configuration variable values, along
# with number of trials to run the experiment for.
BASE_EXP_NAME = "thesis_group_num_clients"
NUM_TRIALS    = 5

###
### The code below runs the main experiment
### loop by updating the configuration file
### then running the experiments with it.
###

def main():
  args = parse_args()

  for exp_dict in make_experiment_runs():
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
    if os.fork() == 0:
      os.system(raw_run_args)
    else:
      os.wait()

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
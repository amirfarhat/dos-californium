import io
import json
import argparse
import statistics

import polars as pl
import pandas as pd

from deter_utils import Timer
from deter_utils import database_experiment_fields
from deter_utils import cast_configuration_fields

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-d', '--groupdir', dest='groupdir',
                      help='', action='store', type=str)

  args = parser.parse_args()

  if args.infiles[-1] == ";":
    args.infiles = args.infiles[:-1]

  return args

args = parse_args()

# ----------------------------------------

def read_experiment_result_data(expname_map_config):
  """
  Read data in from all specified input files and return
  the result of concatenating the data together with some
  initial processing.
  """
  def read_exp_trial_dfs(expname):
    """
    This producedure loads experiment expname's data
    from all trials lazily into the trial_dfs list.
    """
    cfg = expname_map_config[expname]
    num_trials = int(cfg["num_trials"])
    base_dir_path = cfg["base_dir_path"]
    for t in range(1, num_trials + 1):
      trial_dir_path = f"{base_dir_path}/{t}"
      trial_data_path = f"{trial_dir_path}/{expname}.parquet"
      print(trial_data_path)
      df = (
        # For each trial, lazily read the trial data into memory.
        pl
        .scan_parquet(trial_data_path)
        .with_columns([
          # Note the trial number and experiment ID.
          pl.lit(t).alias("trial"),
          pl.lit(expname).alias("exp_id"),
        ])
      )
      trial_dfs.append(df)

  # Collect all experiment trial data lazily into memory.
  trial_dfs = list()
  for expname in expname_map_config:
    try:
      read_exp_trial_dfs(expname)
    except OSError:
      pass
  df = pl.concat(trial_dfs)

  # Assert that we read as many trials as we expect to.
  expected_num_trial_dfs = sum(int(cfg["num_trials"]) for _, cfg in expname_map_config.items())
  # assert len(trial_dfs) == expected_num_trial_dfs

  return df

def read_experiment_metrics(expname_map_config):
  """
  Read the metrics measured from all the experiments
  in the input configuration map. Returns a dataframe
  of all the metrics.
  """
  def read_exp_metric_dfs(expname):
    """
    This procedure adds a lazy dataframe to the metrics_df
    list corresponding to the metrics of experimenet expname.
    """
    cfg = expname_map_config[expname]
    base_dir_path = cfg["base_dir_path"]
    metrics_data_path = f"{base_dir_path}/{expname}.metrics.csv"
    df = (
      pl.scan_csv(metrics_data_path)

      # Note the experiment ID.
      .with_columns([
        pl.lit(expname).alias("exp_id")
      ])
      
      # Rename columns to match the result data names.
      .rename({
        "device_name": "node_type",
        "metric_name": "metric_type",
      })
    )
    metrics_dfs.append(df)

  # Collect all metrics from experiments into memory.
  metrics_dfs = list()
  for expname in expname_map_config:
    read_exp_metric_dfs(expname)
  return (
    pl.concat(metrics_dfs)
    .collect()
  )

def read_expname_map_config():
  """
  Read and return a mapping from experiment names
  to configuration dictionaries. The config is
  a consolidated config from data transformation stage.
  """
  # Read all experiments' configuration details into a 
  # dictionary in-memory.
  expname_map_config = dict()
  for i in args.infiles.split(";"):
    expname = i.split("/")[-1]
    with open(f"{i}/metadata/config.json", "r") as f:
      cfg = json.load(f)
      expname_map_config[expname] = cfg
      expname_map_config[expname]["base_dir_path"] = i
  return expname_map_config

def read_experiment_configurations():
  """
  Reads experiment configurations and returns both
  the dictionary and dataframe representation.
  """
  expname_map_config = read_expname_map_config()
  
  # Convert the relevant configuration parameters
  # to a dataframe for ease of use. We go through
  # pandas first because polars does not support
  # reading from dictionary.
  pandas_configuration_df = (
    pd.DataFrame.from_dict(expname_map_config, orient="index")
    .reset_index()
    .drop(columns=["index"])
    .rename(columns={
      "expname": "exp_id",
      "attack_rate": "attacker_rate",
    })
    .replace({
      "reuse_connections"   : {"true": True, "false": False},
      "run_proxy_with_dtls" : {"1": True, "0": False},
      "run_proxy_with_https": {"1": True, "0": False},
      "run_attacker"        : {"1": True, "0": False},
    })
  )
  configuration_df = (
    pl.from_pandas(pandas_configuration_df)
    .select(database_experiment_fields)
    .with_columns(cast_configuration_fields)
  )

  return configuration_df, expname_map_config

def write_experiment_group_data(configuration_df, lazy_result_data, metrics_df):
  """
  Writes the three kind of data (configuration, 
  metrics, and results) out to a single directory
  named with the input group name. All data written
  out is combined from all the input experiments.
  """
  with Timer("\tWriting configuration"):
    configuration_df.write_parquet(f"{args.groupdir}/configurations.parquet", statistics=True)

  with Timer("\tWriting metrics"):
    metrics_df.write_parquet(f"{args.groupdir}/metrics.parquet", statistics=True)

  with Timer("\tWriting result data", print_header=True):
    lazy_result_data.collect().write_parquet(f"{args.groupdir}/results.parquet", statistics=True)

def main():
  # Read experiment configuration data into dataframe and dict.
  configuration_df, expname_map_config = read_experiment_configurations()

  # Read the experiment result data into dataframe.
  with Timer("Reading data lazily"):
    lazy_result_data = read_experiment_result_data(expname_map_config)

  # Read metrics measured during the experiment into dataframe.
  with Timer("Reading metrics", print_header=True):
    metrics_df = read_experiment_metrics(expname_map_config)

  with Timer("Writing experiment group data", print_header=True):
    write_experiment_group_data(configuration_df, lazy_result_data, metrics_df)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
import argparse

from deter_utils import pl_replace
from deter_utils import normalize_using_minimum

import polars as pl

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-m', '--metricsfile', dest='metricsfile',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

# ----------------------------------------

def transform_and_write_metrics():
  """
  Transforms and writes out the pre-processed metric
  data from devices in this experiment.
  """
  df = (
    # Read pre-processed metrics 
    pl.read_csv(args.metricsfile, use_pyarrow=True)

    # Rename server if necessary
    .with_columns([
      pl_replace("device_name", {"server": "originserver"})
    ])
  )

  # Compute the minimum timestamp per trial
  min_timestamp_df = (
    df
    .groupby(["trial", "device_name"])
    .agg([
      pl.col("observation_timestamp").min().alias("min_observation_timestamp")
    ])
  )

  # Join minimum timestamp to the metric data
  time_normalized_df = (
    df.join(min_timestamp_df, on=["trial", "device_name"])
    
    # Normalize time stamps
    .with_columns([
      (pl.col("observation_timestamp") - pl.col("min_observation_timestamp")).alias("observation_timestamp")
    ])
    
    # Drop unnecessary columns
    .drop([
      "min_observation_timestamp"
    ])
  )
  
  # Write the new metrics data out to the original file
  time_normalized_df.write_csv(args.metricsfile)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  transform_and_write_metrics()
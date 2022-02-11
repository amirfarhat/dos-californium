import csv
import sys
import argparse

from pprint import pprint
from collections import namedtuple

metric_datum_columns = ["device_name", "metric_name", "trial", "metric_value", "observation_timestamp"]
MetricDatum = namedtuple("MetricDatum", metric_datum_columns)

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--metricinfiles', dest='metricinfiles',
                      help='', action='store', type=str)
  parser.add_argument('-o', '--metricoutfile', dest='metricoutfile',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

def parse_memory_file(fif, base_record, metric_collection):
  with open(fif, 'r') as f:
    for L in f.readlines():
      # Parse timestamp and memory usage
      memory_parts = L.split(",")
      assert len(memory_parts) == 2
      timestamp = int(memory_parts[0])
      memory_megabytes = int(memory_parts[1])

      # Prepare record
      record = {**base_record}
      record["metric_value"] = memory_megabytes
      record["observation_timestamp"] = timestamp
      metric_collection.append(record)

def parse_cpu_file(fif, base_record, metric_collection):
  with open(fif, 'r') as f:
    # Get header information. Interestingly, it is found in the tail of the file
    lines = f.readlines()
    sampling_interval_sec = int(lines.pop().split()[-1])
    start_timestamp = int(lines.pop().split()[-1])
    
    # Accumulate records into the metric collection
    timestamp = start_timestamp - sampling_interval_sec
    for L in lines:
      if L.startswith("%Cpu(s)"):
        # Parse CPU usage percentage
        idle_part = L.split(",")[3]
        idle_cpu_pct = float(idle_part.split()[0])
        used_cpu_pct = round(100 - idle_cpu_pct, 2)

        # Prepare record
        timestamp += sampling_interval_sec
        record = {**base_record}
        record["metric_value"] = used_cpu_pct
        record["observation_timestamp"] = timestamp
        metric_collection.append(record)
    

def parse_single_full_infile_path(fif):
  """
  >>> # Proxy
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/1/proxy.cpu.metric.out").items())
  [('device_name', 'proxy'), ('metric_name', 'cpu_utilization'), ('trial', 1)]
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/2/proxy.cpu.metric.out").items())
  [('device_name', 'proxy'), ('metric_name', 'cpu_utilization'), ('trial', 2)]
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/3/proxy.memory.metric.out").items())
  [('device_name', 'proxy'), ('metric_name', 'memory_utilization'), ('trial', 3)]

  >>> # Server
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/100/server.cpu.metric.out").items())
  [('device_name', 'server'), ('metric_name', 'cpu_utilization'), ('trial', 100)]
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/9/server.memory.metric.out").items())
  [('device_name', 'server'), ('metric_name', 'memory_utilization'), ('trial', 9)]
  >>> sorted(parse_single_full_infile_path("/home/ubuntu/californium/deter/expdata/real/final/monitor1_quadruple_delay_90conns_1client_0attackers_newreala/3/server.memory.metric.out").items())
  [('device_name', 'server'), ('metric_name', 'memory_utilization'), ('trial', 3)]
  """
  # Parse trial and metric file from infile path
  last_slash_idx = fif.rfind("/")
  penultimate_slash_idx = fif.rfind("/", 0, last_slash_idx)
  trial = int(fif[penultimate_slash_idx + 1 : last_slash_idx])
  base_metric_file = fif[last_slash_idx + 1 : ]

  # Parse device name and metric name
  parts = base_metric_file.split(".")
  assert parts[2] == "metric" and parts[3] == "out" and len(parts) == 4
  device_name = parts[0]
  metric_name = parts[1] + "_utilization"

  return {
    "trial": trial,
    "device_name": device_name,
    "metric_name": metric_name,
  }

def collect_single_full_infile(fif, metric_collection):
  # Get base record from the path
  base_record = parse_single_full_infile_path(fif)

  # Parse the file contents
  if base_record["metric_name"]   == "cpu_utilization":
    parse_cpu_file(fif, base_record, metric_collection)
  elif base_record["metric_name"] == "memory_utilization":
    parse_memory_file(fif, base_record, metric_collection)
  else:
    raise Exception("Unrecognized metric name " + metric_name)

def write_metrics_out(metric_collection):
  with open(args.metricoutfile, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=metric_datum_columns)
    writer.writeheader()
    writer.writerows(metric_collection)

def main():
  print("Processing metrics...")

  # Input files will be separated by ; and may have a trailing ;
  full_infiles = args.metricinfiles.split(";")
  if len(full_infiles) == 0:
    raise Exception(f"Input files to metric processor script are not specified. Got {args.metricinfiles}")
  if full_infiles[-1] == "":
    full_infiles.pop()

  # Parse and collect the metric contents
  metric_collection = list()
  for fif in full_infiles:
    collect_single_full_infile(fif, metric_collection)

  write_metrics_out(metric_collection)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
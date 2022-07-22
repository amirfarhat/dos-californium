import json
import argparse

from deter_utils import Timer
from deter_utils import pl_replace
from deter_utils import wireshark_connections_row_name_map_field_name
from deter_utils import wireshark_connections_row_name_map_pl_type

import polars as pl

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-o', '--outfile', dest='outfile',
                      help='', action='store', type=str)
  parser.add_argument('-c', '--config', dest='config',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

# ----------------------------------------

def _get_device_name_map_file(infile_list):
  """
  Return a mapping from device name to corresponding file.

  >>> out = _get_device_name_map_file(["/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/attacker_dump.pcap.out",\
                                      "/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/client1_dump.pcap.out",\
                                      "/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/proxy_dump.pcap.out",\
                                      "/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/receiver_dump.pcap.out",\
                                      "/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/server_dump.pcap.out"])
  >>> sorted(out.items())
  [('attacker', '/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/attacker_dump.pcap.out'), ('client1', '/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/client1_dump.pcap.out'), ('proxy', '/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/proxy_dump.pcap.out'), ('receiver', '/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/receiver_dump.pcap.out'), ('server', '/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/server_dump.pcap.out')]
  >>> out = _get_device_name_map_file(["/home/ubuntu/dos-californium/deter/expdata/real/final/updated_thesis_group_num_clients_8clients_noattacker_dtls_https/2/client1_dump.pcap.connections.out"])
  >>> sorted(out.items())
  [('client1', '/home/ubuntu/dos-californium/deter/expdata/real/final/updated_thesis_group_num_clients_8clients_noattacker_dtls_https/2/client1_dump.pcap.connections.out')]
  """
  device_name_map_file = dict()
  for infile in infile_list:
    parts = infile.split('/')
    end = parts[-1].index("_dump")
    name = parts[-1][:end]
    device_name_map_file[name] = infile
  return device_name_map_file

def get_non_empty_device_name_map_file(infile_list):
  """
  Return the subset of the mappings in `_get_device_name_map_file`
  which map to non-empty files.
  """
  device_name_map_file = _get_device_name_map_file(infile_list)
  non_empty_device_name_map_file = dict()
  for device_name, infile in device_name_map_file.items():
    with open(infile, "r") as f:
      line_count = 0
      for line in f:
        line_count += 1
        if line_count > 1:
          # Case  : File has data other than header
          # Action: Retain the device-to-input-file mapping
          non_empty_device_name_map_file[device_name] = infile
          break
      else:
        # Case  : If the break never executes, this file is empty
        # Action: Drop the mapping, since read the file will lead to crash
        pass
  return non_empty_device_name_map_file

def get_ip_addr_map_host_name(hosts_config_dict):
  """
  Turn the host configuration into a map from IP addresses to host names.

  >>> get_ip_addr_map_host_name({'attacker': {'hardware': 'microcloud', 'ip': '10.1.3.1', 'operating_system': 'ubuntu1804-std'}})
  {'10.1.3.1': 'attacker'}
  """
  ip_addr_map_host_name = dict()
  for host_name, host_details_dict in hosts_config_dict.items():
    host_ip = host_details_dict["ip"]
    if host_ip in ip_addr_map_host_name:
      raise Exception(f"IP {host_ip} conflict for host {host_name} and {ip_addr_map_host_name[host_ip]}")
    ip_addr_map_host_name[host_ip] = host_name
  return ip_addr_map_host_name

def read_connections_lazily(device_name, infile, ip_addr_map_host_name, config):
  """
  Read the data from `infile` using a `LazyFrame` for good performance
  and return it when done with initial shaping.

  Source: https://pola-rs.github.io/polars/py-polars/html/reference/lazyframe.html
  """
  # Derive experiment metadata.
  exp_id = config["expname"]
  trial = infile[infile.index(exp_id) + len(exp_id) + 1:].split("/")[0]

  # Sometimes the server is named "originserver", and other times
  # it is named "server". Standardize the former here before proceeding.
  if device_name == "server":
    device_name = "originserver"

  # Read in the connection data.
  df = (
    pl
    .scan_csv(
      infile,
      dtypes=wireshark_connections_row_name_map_pl_type,
      sep=";",
      quote_char='"'
    )

    # Add metadata columns.
    .with_columns([
      pl.lit(int(trial)).alias("trial"),
      pl.lit(exp_id).alias("exp_id"),
      pl.lit(device_name).alias("observer_id"),
    ])
    # Rename columns to human readable equivalents.
    .rename(wireshark_connections_row_name_map_field_name)
    
    # Replace IP addresses with host names.
    .with_columns([
      pl_replace("src_ip", ip_addr_map_host_name),
      pl_replace("dst_ip", ip_addr_map_host_name),
    ])
    .sort(by=["exp_id", "trial", "observer_id", "timestamp"])
  )
  
  return df

def transform_and_write_connections(infile_list, ip_addr_map_host_name, config):
  """
  Transforms the connections from files in `infile_list` to a 
  format that is expected for possible later DB insertion.
  """
  with Timer("Lazily reading device connections"):
    # Reading empty input files causes the dataframe to crash.
    # Therefore, we filter to only read non-empty files.
    non_empty_device_name_map_file = get_non_empty_device_name_map_file(infile_list)
    lazy_dfs = [read_connections_lazily(device_name, infile, ip_addr_map_host_name, config) \
                  for device_name, infile in non_empty_device_name_map_file.items()]
  
  with Timer("Coalescing all connection data"):
    df = pl.concat(lazy_dfs).collect()

  # df.write_parquet(f"/home/ubuntu/dbg_transform_connections_{config['expname']}.parquet")

  with Timer("Writing data out"):
    df.write_parquet(args.outfile)

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    config_dict = json.load(f)

  # Map IP addresses to human readable host names
  ip_addr_map_host_name = get_ip_addr_map_host_name(config_dict["hosts"])

  # Separate input files into a list
  infile_list = args.infiles.rstrip(';').split(';')

  transform_and_write_connections(infile_list, ip_addr_map_host_name, config_dict)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
import json
import argparse

from deter_utils import Timer
from deter_utils import pl_replace
from deter_utils import nullify_columns
from deter_utils import normalize_using_minimum
from deter_utils import wireshark_data_row_name_map_pl_type
from deter_utils import wireshark_data_row_name_map_field_name
from deter_utils import cast_to_final_types
from deter_utils import cast_to_pre_final_types
from deter_utils import lowercase_transformed_data
from deter_utils import lowercase_wireshark_data
from deter_utils import ipv4_regex
from deter_utils import max_allowed_message_timestamp
from deter_utils import min_allowed_message_timestamp
from deter_utils import max_allowed_message_size
from deter_utils import min_allowed_message_size
from deter_utils import allowed_protocols
from deter_utils import transformed_field_name_map_pl_type

import polars as pl

# Mapping from all possible coap type values to human readable ones.
# Source: https://datatracker.ietf.org/doc/html/rfc7252#section-12.1.1
coap_type_map_human_readable = {
  0: "con",
  1: "non",
  2: "ack",
  3: "rst",
}

# Mapping from all possible coap code values to human readable ones.
# Source: https://datatracker.ietf.org/doc/html/rfc7252#section-12.1.2
_code_to_string = lambda c, dd : (c << 5) | dd
coap_code_map_human_readable = {
  # Empty Message
  _code_to_string(0, 00) : "empty_message",
  
  # Method Codes
  _code_to_string(0,  1) : "get",
  _code_to_string(0,  2) : "put",
  _code_to_string(0,  3) : "post",
  _code_to_string(0,  4) : "delete",

  # Response Codes
  _code_to_string(2,  1) : "created",
  _code_to_string(2,  2) : "deleted",
  _code_to_string(2,  3) : "valid",
  _code_to_string(2,  4) : "changed",
  _code_to_string(2,  5) : "content",
  _code_to_string(4, 00) : "bad_request",
  _code_to_string(4,  1) : "unauthorized",
  _code_to_string(4,  2) : "bad_option",
  _code_to_string(4,  3) : "forbidden",
  _code_to_string(4,  4) : "not_found",
  _code_to_string(4,  5) : "method_not_allowed",
  _code_to_string(4,  6) : "not_acceptable",
  _code_to_string(4, 12) : "precondition_failed",
  _code_to_string(4, 13) : "request_entity_too_large",
  _code_to_string(4, 15) : "unsupported_media_type",
  _code_to_string(5, 00) : "internal_server_error",
  _code_to_string(5,  1) : "not_implemented",
  _code_to_string(5,  2) : "bad_gateway",
  _code_to_string(5,  3) : "service_unavailable",
  _code_to_string(5,  4) : "gateway_timeout",
  _code_to_string(5,  5) : "proxying_not_supported",

  # Everything else is reserved
}

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-o', '--outfile', dest='outfile',
                      help='', action='store', type=str)
  parser.add_argument('-c', '--config', dest='config',
                      help='', action='store', type=str)
  parser.add_argument('-r', '--httpoutfile', dest='httpoutfile',
                      help='', action='store', type=str)
  parser.add_argument('-a', '--coapoutfile', dest='coapoutfile',
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

def summarize_protocol_statistics(df):
  """
  Count the response code occurrences for coap and http, then
  write these out to the specified files.
  """
  def _summarize_response_counts(df, protocol, column, outfile):
    summary_df = (
      df
      .filter(
        (pl.col("message_protocol") == protocol)
        & (pl.col(column).is_not_null())
      )
      .groupby(column)
      .agg([
        pl.col(column).count().alias("response_code_count")
      ])
    )
    summary_df.write_json(outfile, row_oriented=True)

  with Timer("\tSummarizing and writing out coap statistics", log=False):
    _summarize_response_counts(df, "coap", "coap_type", args.coapoutfile)
  
  with Timer("\tSummarizing and writing out http statistics", log=False):
    _summarize_response_counts(df, "http", "http_response_code", args.httpoutfile)

def validate_final_data(final_df):
  """
  Validates invariants about the data after it has been processed.
  """
  # Expect the script to have fully replaced IP addresses with host names
  cols_expecting_no_ip = ["node_type", "message_source", "message_destination"]
  for col in cols_expecting_no_ip:
    col_has_ip = final_df.get_column(col).str.contains(ipv4_regex).any()
    assert not col_has_ip

  # Enforce upper and lower bound on message timestamps
  min_found_timestamp = final_df.get_column("message_timestamp").min()
  max_found_timestamp = final_df.get_column("message_timestamp").max()
  assert min_found_timestamp >= min_allowed_message_timestamp
  assert max_found_timestamp <= max_allowed_message_timestamp

  # Enforce only allowed protocols, and always some protocol
  found_protocol_set = set(final_df.get_column("message_protocol").unique().to_list())
  assert len(found_protocol_set - allowed_protocols) == 0
  assert 0 < len(found_protocol_set) <= len(allowed_protocols)

  # Enforce upper and lower bound on message sizes
  min_found_size = final_df.get_column("message_size").min()
  max_found_size = final_df.get_column("message_size").max()
  assert min_found_size >= min_allowed_message_size
  assert max_found_size <= max_allowed_message_size

  # Enforce that the final schema matches post-transformation expecation
  assert final_df.schema == transformed_field_name_map_pl_type, final_df.schema

def transform_http_data(df, coap_columns):
  """
  Transform http protocol messages to the correct types,
  column names, and values.
  """
  # Filter for only http messages
  hdf = df.filter(pl.col("message_protocol") == "http")

  # Nullify values in coap columns. As opposed to the case for coap, where
  # it is possible to nullofy and cast in the same step, after the main data
  # transformation, for http it seems necessary to nullify, then transform,
  # then cast. It is unclear why.
  hdf = hdf.with_columns(nullify_columns(coap_columns))

  hdf = hdf.with_columns([
    # Convert http request to a boolean
    pl.col("http_request").is_not_null().alias("http_request"),
    
    # Coalesce the http URI across requests and responses
    pl.format(
        "{}{}",
        pl.col("http_request_full_uri").fill_null(""),
        pl.col("http_response_for_uri").fill_null("")
    )
    # Then assign each message a UID
    .str.extract(r"(\w+_\w+)", 1).alias("uid"),    
  ])

  # Cast the dataframe to the final expected types
  hdf = hdf.with_columns(cast_to_pre_final_types)

  return hdf

def transform_coap_data(df, http_columns):
  """
  Transform coap protocol messages to the correct types,
  column names, and values.
  """
  # Filter for only coap messages
  cdf = df.filter(pl.col("message_protocol") == "coap")

  cdf = cdf.with_columns([
    # Convert coap type and code to human readable string
    pl_replace("coap_type", coap_type_map_human_readable),
    pl_replace("coap_code", coap_code_map_human_readable),

    # Sometimes there is a random : so we need to remove it
    pl.col("coap_token").str.replace(":", "").alias("coap_token"),
    
    # Convert coap retransmitted to a boolean
    pl.col("coap_retransmitted").is_not_null().alias("coap_retransmitted"),
    
    # Assign each message a UID
    pl.format("{}_{}", "coap_message_id", "coap_token").alias("uid")
  ])

  # Nullify values in http columns and cast the dataframe to the final expected types
  cdf = cdf.with_columns(nullify_columns(http_columns) + cast_to_pre_final_types)

  return cdf

def transform_data(df):
  """
  Transform coap and http protocol messages to the correct types,
  column names, and values.
  """
  # Get columns that are involved explcitly in one protocol
  http_columns = df.select("^(http_).*$").collect().columns
  coap_columns = df.select("^(coap_).*$").collect().columns

  with Timer("\tTransforming CoAP data"):
    cdf = transform_coap_data(df, http_columns)

  with Timer("\tTransforming HTTP data"):
    hdf = transform_http_data(df, coap_columns)

  with Timer("\tJoining CoAP and HTTP dataframes"):
    joined_df = (
      pl.concat([cdf, hdf])
      .sort(by="message_timestamp")
    )

  with Timer("\tCreating message markers"):
    message_marker_df = (
      # Get unique UIDs
      joined_df
      .unique(maintain_order=True, subset=["uid"])
      .select("uid")
      
      # Add row counter which will act as message marker
      .with_row_count(name="message_marker", offset=1)
    )

  with Timer("\tJoining final dataframe"):
    final_df = (
      joined_df
      .join(message_marker_df, on="uid")
      .drop("uid")
      .with_columns(cast_to_final_types)
    )

  return final_df

def read_data_lazily(device_name, infile, ip_addr_map_host_name):
  """
  Read the data from `infile` using a `LazyFrame` for good performance
  and return it when done with initial shaping.

  Source: https://pola-rs.github.io/polars/py-polars/html/reference/lazyframe.html
  """
  df = (
    pl
    # Read intermediate Wireshark data in as csv
    .scan_csv(infile,
              dtypes=wireshark_data_row_name_map_pl_type,
              sep=";",
              quote_char='"')

    # Lowercase all the string column values
    .with_columns(lowercase_wireshark_data)
      
    # Rename column names from Wireshark format to database format
    .rename(wireshark_data_row_name_map_field_name)
    .drop("http.response")
  )

  # Sometimes the server is named "originserver", and other times
  # it is named "server". Standardize the former here before proceeding
  if device_name == "server":
    device_name = "originserver"

  return df.with_columns([
    # Replace IP addresses with host names
    pl_replace("message_source", ip_addr_map_host_name),
    pl_replace("message_destination", ip_addr_map_host_name),
      
    # Add node type that generated the input data file
    pl.lit(device_name).alias('node_type'),
  ])

def transform_and_write_data(infile_list, ip_addr_map_host_name):
  """
  Transforms the data from files in `infile_list` to a format
  that is expected for possible later DB insertion.
  """
  with Timer("Lazily reading device data"):
    # Reading empty input files causes the dataframe to crash.
    # Therefore, we filter to only read non-empty files.
    non_empty_device_name_map_file = get_non_empty_device_name_map_file(infile_list)
    lazy_dfs = [read_data_lazily(device_name, infile, ip_addr_map_host_name) \
                  for device_name, infile in non_empty_device_name_map_file.items()]

  with Timer("Coalescing all device data"):
    df = pl.concat(lazy_dfs)

  with Timer("Transforming data"):
    df = transform_data(df)

  with Timer("Materializing data for writing"):
    final_df = (
      df
      .with_columns(
        normalize_using_minimum("message_timestamp")
        + lowercase_transformed_data
      )
      .collect()
    )

  final_df.write_parquet("/home/ubuntu/dbg_transform.parquet")

  with Timer("Validating data before writing out"):
    validate_final_data(final_df)

  with Timer("Summarizing protocol statistics"):
    summarize_protocol_statistics(final_df)

  with Timer("Writing data out"):
    final_df.write_parquet(args.outfile)

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    config_dict = json.load(f)

  # Map IP addresses to human readable host names
  ip_addr_map_host_name = get_ip_addr_map_host_name(config_dict["hosts"])

  # Separate input files into a list
  infile_list = args.infiles.rstrip(';').split(';')

  transform_and_write_data(infile_list, ip_addr_map_host_name)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
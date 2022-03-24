import csv
import json
import argparse

from deter_utils import Timer, pl_replace

import polars as pl

# Expect data rows read in to have these exact types
# when reading data in. These will later be converted
# to more convenient types.
data_row_name_map_pl_type = {
  '_ws.col.Time'           : pl.datatypes.Float64,
  '_ws.col.Source'         : pl.datatypes.Utf8,
  '_ws.col.Destination'    : pl.datatypes.Utf8,
  '_ws.col.Protocol'       : pl.datatypes.Utf8,
  '_ws.col.Length'         : pl.datatypes.Int64,
  'coap.type'              : pl.datatypes.Int64,
  'coap.retransmitted'     : pl.datatypes.Utf8,
  'coap.code'              : pl.datatypes.Int64,
  'coap.mid'               : pl.datatypes.Int64,
  'coap.token'             : pl.datatypes.Utf8,
  'coap.opt.proxy_uri'     : pl.datatypes.Utf8,
  'http.request'           : pl.datatypes.Int64,
  'http.request.method'    : pl.datatypes.Utf8,
  'http.request.full_uri'  : pl.datatypes.Utf8,
  'http.response'          : pl.datatypes.Int64,
  'http.response.code'     : pl.datatypes.Int64,
  'http.response.code.desc': pl.datatypes.Utf8,
  'http.response_for.uri'  : pl.datatypes.Utf8
}

# Specification of how to go from data row names
# to field names written out by the script.
data_row_name_map_field_name = {
  # Native wireshark columns
  "_ws.col.Time"       : "message_timestamp",
  "_ws.col.Source"     : "message_source",
  "_ws.col.Destination": "message_destination",
  "_ws.col.Protocol"   : "message_protocol",
  "_ws.col.Length"     : "message_size",

  # CoAP columns
  "coap.type"         : "coap_type",
  "coap.code"         : "coap_code",
  "coap.mid"          : "coap_message_id",
  "coap.token"        : "coap_token",
  "coap.opt.proxy_uri": "coap_proxy_uri",
  "coap.retransmitted": "coap_retransmitted",

  # HTTP columns
  "http.request"           : "http_request",
  "http.request.method"    : "http_request_method",
  "http.request.full_uri"  : "http_request_full_uri",
  "http.response.code"     : "http_response_code",
  "http.response.code.desc": "http_response_code_desc",
  "http.response_for.uri"  : "http_response_for_uri",
}

assert set(data_row_name_map_field_name.keys()) <= set(data_row_name_map_pl_type.keys())

# This is the final column type mapping which
# the script will use to write out the transformed
# data.
field_name_map_pl_type = {
  'node_type'              : pl.datatypes.Utf8,
  'message_marker'         : pl.datatypes.Int64,
  'message_timestamp'      : pl.datatypes.Float64,
  'message_source'         : pl.datatypes.Utf8,
  'message_destination'    : pl.datatypes.Utf8,
  'message_protocol'       : pl.datatypes.Utf8,
  'message_size'           : pl.datatypes.Int64,
  'coap_type'              : pl.datatypes.Utf8,
  'coap_code'              : pl.datatypes.Utf8,
  'coap_message_id'        : pl.datatypes.Int64,
  'coap_token'             : pl.datatypes.Utf8,
  'coap_proxy_uri'         : pl.datatypes.Utf8,
  'coap_retransmitted'     : pl.datatypes.Boolean,
  'http_request'           : pl.datatypes.Boolean,
  'http_request_method'    : pl.datatypes.Utf8,
  'http_request_full_uri'  : pl.datatypes.Utf8,
  'http_response_code'     : pl.datatypes.Int64,
  'http_response_code_desc': pl.datatypes.Utf8,
  'http_response_for_uri'  : pl.datatypes.Utf8,
}

# Message marker may not be ready during processing, so
# we exclude it during processing.
pre_final_field_name_map_pl_type = {f:t for f, t in field_name_map_pl_type.items() if f not in {"message_marker"}}

field_names = set(field_name_map_pl_type.keys())
assert set(field_name_map_pl_type.keys()) <= field_names
assert set(pre_final_field_name_map_pl_type.keys()) <= field_names

# Mapping from all possible coap type values to human readable ones.
# Source: https://datatracker.ietf.org/doc/html/rfc7252#section-12.1.1
coap_type_map_human_readable = {
  "0": "con",
  "1": "non",
  "2": "ack",
  "3": "rst",
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

def get_device_name_map_file(infile_list):
  """
  Return a mapping from device name to corresponding file.

  >>> out = get_device_name_map_file(["/home/ubuntu/dos-californium/deter/expdata/real/final/client_and_attacker_httpson/1/attacker_dump.pcap.out",\
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

def validate_final_data(df):
  """
  Method that can be used to validate the data that has been prcessed.
  """
  pass

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
  nullify_coap_columns = [pl.lit(None).alias(column_name) \
                            for column_name in coap_columns]
  hdf = hdf.with_columns(nullify_coap_columns)

  hdf = hdf.with_columns([
    # Convert http request to a boolean
    pl.col("http_request").is_not_null().alias("http_request"),
    
    # Lowercase and coalesce the http URI across requests and responses
    pl.format(
        "{}{}",
        pl.col("http_request_full_uri").str.to_lowercase().fill_null(""),
        pl.col("http_response_for_uri").str.to_lowercase().fill_null("")
    )
    # Then assign each message a UID
    .str.extract(r"(\w+_\w+)", 1).alias("uid"),    
  ])

  # Cast the dataframe to the final expected types
  cast_to_final_types = [pl.col(col).cast(col_type).alias(col) for col, col_type in pre_final_field_name_map_pl_type.items()]
  hdf = hdf.with_columns(cast_to_final_types)

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
  nullify_http_columns = [pl.lit(None).alias(col) for col in http_columns]
  cast_to_final_types = [pl.col(col).cast(col_type).alias(col) for col, col_type in pre_final_field_name_map_pl_type.items()]
  cdf = cdf.with_columns(nullify_http_columns + cast_to_final_types)

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
    final_df = joined_df.join(message_marker_df, on="uid")

  with Timer("\tValidating final data"):
    validate_final_data(final_df)

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
              dtypes=data_row_name_map_pl_type,
              sep=";",
              quote_char='"')
      
    # Rename column names from Wireshark format to database format
    .rename(data_row_name_map_field_name)
    .drop("http.response")
  )

  return df.with_columns([
    # Replace IP addresses with host names
    pl_replace("message_source", ip_addr_map_host_name),
    pl_replace("message_destination", ip_addr_map_host_name),
      
    # Add node type that generated the input data file
    pl.lit(device_name).alias('node_type'),
      
    # Lowercase protocol names
    pl.col("message_protocol").str.to_lowercase().alias("message_protocol")
  ])

def transform_and_write_data(infile_list, ip_addr_map_host_name):
  """
  Transforms the data from files in `infile_list` to a format
  that is expected for possible later DB insertion.
  """
  device_name_map_file = get_device_name_map_file(infile_list)

  with Timer("Lazily reading device data"):
    lazy_dfs = [read_data_lazily(device_name, infile, ip_addr_map_host_name) \
                  for device_name, infile in device_name_map_file.items()]

  with Timer("Coalescing all device data"):
    df = pl.concat(lazy_dfs)

  with Timer("Transforming data"):
    df = transform_data(df)

  with Timer("Materializing data for writing"):
    real_df = df.collect()

  with Timer("Summarizing protocol statistics"):
    summarize_protocol_statistics(real_df)

  with Timer("Writing data out"):
    real_df.write_parquet(args.outfile)

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    config_dict = json.load(f)

  # Map IP addresses to human readable host names
  ip_addr_map_host_name = get_ip_addr_map_host_name(config_dict["hosts"])

  # Separate input files into a list
  infile_list = args.infiles.rstrip(';').split(';')

  # Transform the input data and write it out anew
  transform_and_write_data(infile_list, ip_addr_map_host_name)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
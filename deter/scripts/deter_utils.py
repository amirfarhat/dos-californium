import time
import polars as pl

### 
### Timer
### 

class TimerException(Exception):
  """
  Exceptions specific to instances of the `Timer` below
  """
  pass

class Timer:
  """
  Class to aid in timing code
  """
  def __init__(self, start_text, end_text="Time elapsed: {:.4f} seconds", print_header=False, log=True):
    self._start_time_ns = None
    self._start_text = start_text
    self._end_text = end_text
    self.print_header = print_header
    self.log = log

  def start(self):
    if self._start_time_ns is not None:
      raise TimerException(f"Cannot start Timer, because it is already running with start time {self._start_time_ns}.")

    self._start_time_ns = time.perf_counter_ns()
    if self.print_header:
      if self.log:
        print(self._start_text + "...")

  def stop(self):
    if self._start_time_ns is None:
      raise TimerException(f"Cannot stop Timer, because it has not been started.")

    elapsed_time_ns = time.perf_counter_ns() - self._start_time_ns
    self._start_time_ns = None
    return self._start_text + " - " + self._end_text.format(elapsed_time_ns * 1e-9)

  def __enter__(self):
    self.start()
    return self

  def __exit__(self, *args):
    if self.log:
      print(self.stop())

### 
### Data columns and associated types
### 

# Expect data rows read in to have these exact types
# when reading data in. These will later be converted
# to more convenient types.
wireshark_data_row_name_map_pl_type = {
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
wireshark_data_row_name_map_field_name = {
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

assert set(wireshark_data_row_name_map_field_name.keys()) <= set(wireshark_data_row_name_map_pl_type.keys())

# This is the final column type mapping which
# the script will use to write out the transformed
# data.
transformed_field_name_map_pl_type = {
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

# Message marker is not be ready during processing, 
# until the very end. So we exclude it during processing.
pre_final_transformed_field_name_map_pl_type = {f:t for f, t in transformed_field_name_map_pl_type.items() if f not in {"message_marker"}}

field_names = set(transformed_field_name_map_pl_type.keys())
assert set(transformed_field_name_map_pl_type.keys()) <= field_names
assert set(pre_final_transformed_field_name_map_pl_type.keys()) <= field_names

# This is the final column type mapping which
# the script will use to write out the transformed
# data.
database_transformed_field_name_map_pl_type = {
  'node_type'              : pl.datatypes.Int64,
  'message_marker'         : pl.datatypes.Int64,
  'message_timestamp'      : pl.datatypes.Float64,
  'message_source'         : pl.datatypes.Int64,
  'message_destination'    : pl.datatypes.Int64,
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

assert database_transformed_field_name_map_pl_type.keys() == transformed_field_name_map_pl_type.keys()

# These are enumerations of the fields in protocols
# that the database is meant to store. Note that these
# do not contain the database IDs by design.
database_coap_fields            = ["coap_type", "coap_code", "coap_retransmitted"]
database_http_fields            = ["http_request", "http_request_method", "http_response_code"]
database_message_pattern_fields = ["message_size", "message_source", "message_destination"]
database_experiment_field_map_pl_type = {
  "exp_id"                     : pl.datatypes.Utf8,
  "attacker_rate"              : pl.datatypes.Utf8,
  "server_connections"         : pl.datatypes.Int64,
  "max_keep_alive_requests"    : pl.datatypes.Int64,
  "num_clients"                : pl.datatypes.Int64,
  "num_trials"                 : pl.datatypes.Int64,
  "origin_server_duration"     : pl.datatypes.Int64,
  "attacker_duration"          : pl.datatypes.Int64,
  "receiver_duration"          : pl.datatypes.Int64,
  "proxy_duration"             : pl.datatypes.Int64,
  "client_duration"            : pl.datatypes.Int64,
  "attacker_start_lag_duration": pl.datatypes.Int64,
  "topology_name"              : pl.datatypes.Utf8,
  "num_proxy_connections"      : pl.datatypes.Int64,
  "request_timeout"            : pl.datatypes.Utf8,
  "max_retries"                : pl.datatypes.Int64,
  "keep_alive_duration"        : pl.datatypes.Utf8,
  "request_retry_interval"     : pl.datatypes.Utf8,
  "reuse_connections"          : pl.datatypes.Boolean,
  "run_proxy_with_dtls"        : pl.datatypes.Boolean,
  "run_proxy_with_https"       : pl.datatypes.Boolean,
  "run_attacker"               : pl.datatypes.Boolean,
}
database_experiment_fields = list(database_experiment_field_map_pl_type.keys())
### 
### Polars condition value replacement
### 

def pl_replace_predicates_to_values(column, predicates, values):
  """
  Produces an expression for polars to replace a sequence of `predicates` 
  to corresponding `values` and name the series a specific `column`. Importantly,
  if the predicates don't match, the column value is kept unchanged.
  """
  branch = pl.when(predicates[0]).then(values[0])
  for p, v in zip(predicates[1:], values[1:]):
    branch = branch.when(p).then(v)
  return branch.otherwise(pl.col(column)).alias(column)

def pl_replace_from_to(column, from_, to_):
  """
  Produces an expression for polars to replace a `from` values
  to `to` values inside a specified column.
  """
  branch = pl.when(pl.col(column) == from_[0]).then(to_[0])
  for (from_value, to_value) in zip(from_, to_):
    branch = branch.when(pl.col(column) == from_value).then(to_value)
  return branch.otherwise(pl.col(column)).alias(column)

def pl_replace(column, mapping):
  from_ = [k for k, _ in sorted(mapping.items())]
  to_   = [v for _, v in sorted(mapping.items())]
  return pl_replace_from_to(column, from_, to_)

### 
### Database helpers
### 

def batch_sql_function_calls(select_sql, num_calls):
  """
  Combine multiple SQL function calls into the same
  command sent to the DB.

  >>> batch_sql_function_calls("SELECT * FROM insert_into_coap(%s, %s, %s)", 1)
  'SELECT * FROM insert_into_coap(%s, %s, %s)'

  >>> batch_sql_function_calls("SELECT * FROM insert_into_node(%s, %s, %s)", 2)
  'SELECT * FROM insert_into_node(%s, %s, %s) UNION ALL SELECT * FROM insert_into_node(%s, %s, %s)'

  >>> batch_sql_function_calls("SELECT * FROM insert_into_deployed_node(%s, %s)", 4)
  'SELECT * FROM insert_into_deployed_node(%s, %s) UNION ALL SELECT * FROM insert_into_deployed_node(%s, %s) UNION ALL SELECT * FROM insert_into_deployed_node(%s, %s) UNION ALL SELECT * FROM insert_into_deployed_node(%s, %s)'
  """
  # Here, we need to use ALL after the UNION so that postgres
  # will not reorder the outputs of the batch query. "The 
  # Postgres implementation for UNION ALL returns  values 
  # in the sequence as appended".
  # Source: https://stackoverflow.com/questions/31975969/is-order-preserved-after-union-in-postgresql
  unioned_select_sql = """UNION ALL """ + select_sql

  sql_parts = [None for _ in range(num_calls)]
  sql_parts[0] = select_sql
  for i in range(1, num_calls):
    sql_parts[i] = unioned_select_sql
  return " ".join(sql_parts)

### 
### Polars column manipulation
### 

def _cast_cols_from_type_map(type_map):
  """
  Query to cast all columns specified in the `type_map`
  to their specified type, without creating extra columns.
  """
  return [pl.col(col).cast(col_t).alias(col) for col, col_t in type_map.items()]

def _lowercase_string_columns(type_map):
  """
  Query to lowercase all the values in string columns.
  """
  return [pl.col(col).str.to_lowercase().alias(col) \
            for col, col_t in type_map.items() \
              if col_t == pl.datatypes.Utf8]

def normalize_using_minimum(col):
  """
  Expression which subtracts the minimum column value from every
  value in the input column `col`. Overrwites the "unnormalized"
  column with the normalized column.
  """
  return [(pl.col(col) - pl.col(col).min()).alias(col)]

def nullify_columns(columns):
  """
  Query to nullify all values in the input `columns`.
  """
  return [pl.lit(None).alias(col) for col in columns]

def _zero_out_response_code_for_http_request():
  """
  Return a query which will set the http response code
  column value to -1 for http requests.
  """
  return (
    pl.when(pl.col("http_request") == True)
      .then(pl.lit(-1).alias("http_response_code"))
      .otherwise(pl.col("http_response_code").alias("http_response_code"))
  )

def _zero_out_request_method_for_http_response():
  """
  Return a query which will set the http request method
  column value to "" for http responses.
  """
  return (
    pl.when(pl.col("http_request") == False)
      .then(pl.lit("").alias("http_request_method"))
      .otherwise(pl.col("http_request_method").alias("http_request_method"))
  )

cast_to_database_types     = _cast_cols_from_type_map(database_transformed_field_name_map_pl_type)
cast_to_pre_final_types    = _cast_cols_from_type_map(pre_final_transformed_field_name_map_pl_type)
cast_to_final_types        = _cast_cols_from_type_map(transformed_field_name_map_pl_type)
cast_configuration_fields  = _cast_cols_from_type_map(database_experiment_field_map_pl_type)
lowercase_wireshark_data   = _lowercase_string_columns(wireshark_data_row_name_map_pl_type)
lowercase_transformed_data = _lowercase_string_columns(transformed_field_name_map_pl_type)
zero_out_response_code_for_http_request   = _zero_out_response_code_for_http_request()
zero_out_request_method_for_http_response = _zero_out_request_method_for_http_response()

### 
### Constants and Regexes
###
allowed_protocols             = {"http", "coap"}
min_allowed_message_size      = 0 # bytes
max_allowed_message_size      = 2000 # bytes
min_allowed_message_timestamp = 0 # 0 seconds
max_allowed_message_timestamp = 10 * 60 # 10 minutes to seconds
ipv4_regex                    = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"

import doctest
doctest.testmod()
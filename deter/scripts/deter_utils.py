
import time
import polars as pl

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

# Message marker may not be ready during processing, so
# we exclude it during processing.
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
import csv
import sys
import json
import argparse

import numpy as np

from pprint import pprint

http_response_code_map_freq = dict()
coap_response_code_map_freq = dict()

fieldnames = ['node_type',
                'message_marker',
                'message_timestamp', 
                'message_source',
                'message_destination',
                'message_protocol',
                'message_size',
                'coap_type',
                'coap_code',
                'coap_message_id',
                'coap_token',
                'coap_proxy_uri',
                'coap_retransmitted',
                'http_request',
                'http_request_method',
                'http_request_full_uri',
                'http_response_code',
                'http_response_code_desc',
                'http_response_for_uri']

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

class CoapUnspportedValueException(Exception): pass

def coap_type_convert(coap_type: str) -> str:
  """
  Convert integer `coap_type` to human-readable

  >>> coap_type_convert("0")
  'con'

  >>> coap_type_convert("1")
  'non'

  >>> coap_type_convert("2")
  'ack'
  
  >>> coap_type_convert("3")
  'rst'
  """
  type_map_text = {
    "0": "con",
    "1": "non",
    "2": "ack",
    "3": "rst",
  }
  if coap_type not in type_map_text:
    raise CoapUnspportedValueException(f"CoAP type {coap_type} must be one of {sorted(type_map_text.keys())}")
  return type_map_text[coap_type]

def coap_code_convert(coap_code: str) -> str:
  """
  Convert integer `coap_code` to human-readable "c.dd" format
  where `c` is the class and `dd` is the detail

  >>> set([coap_code_convert(x) for x in ["0", "00", "000"]])
  {'empty_message'}

  >>> set([coap_code_convert(x) for x in ["1", "1.0"]])
  {'get'}

  >>> set([coap_code_convert(x) for x in ["67", "67.0"]])
  {'valid'}
  >>> set([coap_code_convert(x) for x in ["69", "69.0"]])
  {'content'}

  >>> set([coap_code_convert(x) for x in ["128", "128.0"]])
  {'bad_request'}
  >>> set([coap_code_convert(x) for x in ["132", "132.0"]])
  {'not_found'}

  >>> set([coap_code_convert(x) for x in ["160", "160.0"]])
  {'internal_server_error'}
  >>> set([coap_code_convert(x) for x in ["163", "163.0"]])
  {'service_unavailable'}
  >>> set([coap_code_convert(x) for x in ["164", "164.0"]])
  {'gateway_timeout'}
  >>> set([coap_code_convert(x) for x in ["165", "165.0"]])
  {'proxying_not_supported'}
  """
  # Convert into c.dd format
  x = int(float(coap_code))
  c, dd = (x >> 5, x & 0b11111)
  coap_code = (c, dd)

  code_map_text = {
    # Empty Message
    (0, 00) : "empty_message",
    
    # Method Codes
    (0,  1) : "get",
    (0,  2) : "put",
    (0,  3) : "post",
    (0,  4) : "delete",

    # Response Codes
    (2,  1) : "created",
    (2,  2) : "deleted",
    (2,  3) : "valid",
    (2,  4) : "changed",
    (2,  5) : "content",
    (4, 00) : "bad_request",
    (4,  1) : "unauthorized",
    (4,  2) : "bad_option",
    (4,  3) : "forbidden",
    (4,  4) : "not_found",
    (4,  5) : "method_not_allowed",
    (4,  6) : "not_acceptable",
    (4, 12) : "precondition_failed",
    (4, 13) : "request_entity_too_large",
    (4, 15) : "unsupported_content_format",
    (5, 00) : "internal_server_error",
    (5,  1) : "not_implemented",
    (5,  2) : "bad_gateway",
    (5,  3) : "service_unavailable",
    (5,  4) : "gateway_timeout",
    (5,  5) : "proxying_not_supported",

    # Everything else is reserved
  }
  if coap_code not in code_map_text:
    raise CoapUnspportedValueException(f"CoAP code {coap_code} must be one of {sorted(code_map_text.keys())}")
  return code_map_text[coap_code]


def ip_to_name(ip, config_dict):
  hosts = config_dict['hosts']
  for h in hosts:
    if hosts[h]['ip'] == ip:
      return h
  print(hosts)
  raise Exception(f"Could not find name for IP {ip}")
  

# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================

def parse_protocol_information(fieldmap, row, uid_map_number):
  protocol = fieldmap['message_protocol']
  uid = None

  if protocol == "coap":
    # CoAP Type
    fieldmap["coap_type"] = coap_type_convert(row["coap.type"])

    # CoAP Code
    fieldmap["coap_code"] = coap_code_convert(row["coap.code"])

    # CoAP MID
    fieldmap["coap_message_id"] = row["coap.mid"]

    # Machine sometimes inserts : so we need to remove it
    coap_token = row["coap.token"].replace(":", "")
    fieldmap["coap_token"] = coap_token

    # CoAP Options
    fieldmap["coap_proxy_uri"] = row["coap.opt.proxy_uri"]

    # CoAp Retransmission
    fieldmap["coap_retransmitted"] = 1 if row["coap.retransmitted"] else 0

    # UID is made from the CoAP message ID and token
    coap_message_id = fieldmap["coap_message_id"]
    coap_token = fieldmap["coap_token"]
    uid = f"{coap_message_id}_{coap_token}".lower()
    if ":" in uid or ":" in coap_token:
      raise Exception()

    # Record coap response codes
    global coap_response_code_map_freq
    resp_code = fieldmap["coap_code"]
    coap_response_code_map_freq[resp_code] = coap_response_code_map_freq.setdefault(resp_code, 0) + 1
    

  elif protocol == "http":
    # Is HTTP request?
    fieldmap["http_request"] = 1 if row["http.request"] else 0
    fieldmap["http_request_method"] = row["http.request.method"].lower()
    fieldmap["http_request_full_uri"] = row["http.request.full_uri"]

    # Is HTTP response?
    fieldmap["http_response_code"] = row["http.response.code"]
    fieldmap["http_response_code_desc"] = row["http.response.code.desc"]
    fieldmap["http_response_for_uri"] = row["http.response_for.uri"]

    # Get whichever URI is first and not empty string
    uri = fieldmap["http_request_full_uri"] or fieldmap["http_response_for_uri"]

    # UID (from CoAP message ID and token), is the requested resource
    uid = uri.split("/")[-1].lower()

    # Record http response codes
    global http_response_code_map_freq
    resp_code = fieldmap["http_response_code"]
    http_response_code_map_freq[resp_code] = http_response_code_map_freq.setdefault(resp_code, 0) + 1

  else:
    raise ValueError(f"Uncrecognized protocol {protocol}")

  # Add to uid map
  uid_map_number.setdefault(uid, 1 + len(uid_map_number))
  fieldmap["message_marker"] = uid_map_number[uid]

def do_process_row(row, writer, fieldmap, config_dict, uid_map_number):
  # Timestamp
  message_timestamp = row["_ws.col.Time"]
  if float(message_timestamp) <= 0:
    raise ValueError(f"Expected positive timestamp, got {message_timestamp}")
  fieldmap["message_timestamp"] = message_timestamp

  # Source
  message_source = row["_ws.col.Source"]
  fieldmap["message_source"] = ip_to_name(message_source, config_dict)

  # Destination
  message_destination = row["_ws.col.Destination"]
  fieldmap["message_destination"] = ip_to_name(message_destination, config_dict)

  # Protocol
  message_protocol = row["_ws.col.Protocol"].lower()
  if message_protocol not in { "coap", "http" }:
    raise ValueError(f"Unrecognized protol {message_protocol}")
  fieldmap["message_protocol"] = message_protocol

  # Message size
  message_size = row["_ws.col.Length"]
  if int(message_size) <= 0:
    raise ValueError(f"Expected positive message size, got {message_size}")
  fieldmap["message_size"] = message_size

  # Enagage protocol-specific parsing
  parse_protocol_information(fieldmap, row, uid_map_number)

def process_row(row, writer, fieldmap, config_dict, row_batch, uid_map_number):
  do_process_row(row, writer, fieldmap, config_dict, uid_map_number)
  
  # Write empty string as null
  for k, v in fieldmap.items():
    fieldmap[k] = 'NULL' if v == '' else v

  row_batch.append(fieldmap)

# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================
# ====================================================================

class NamedReader:
  def __init__(self, reader, name):
    self.reader = reader
    self.name = name
    self.row = None
    self.is_open = False
  
  def load_next(self):
    if not self.is_open:
      raise Exception("Named reader is not open")
    try:
      self.row = next(self.reader)
    except StopIteration:
      self.row = None
      self.is_open = False
    return self.row

  def start(self):
    if self.is_open:
      raise Exception("Named reader is already open")
    self.is_open = True

def run_through_named_readers(writer, named_readers, config_dict, uid_map_number):
  # Start all named readers
  for nr in named_readers:
    nr.start()
    nr.load_next()

  # Incrementally iterate over the readers, min row first by timestamp
  open_nrs = list(filter(lambda nr: nr.is_open, named_readers))
  while len(open_nrs) > 0:
    # Get the named reader whose current row has the earliest timestamp
    i, min_row_reader = min(enumerate(open_nrs), key=lambda t: t[1].row["_ws.col.Time"])
    min_row = min_row_reader.row
    assert min_row is not None

    # Process that reader's row
    fieldmap = { f : "" for f in fieldnames }
    fieldmap['node_type'] = "originserver" if open_nrs[i].name == "server" else open_nrs[i].name
    fieldmap['message_marker'] = -1
    do_process_row(min_row, writer, fieldmap, config_dict, uid_map_number)
    writer.writerow(fieldmap)

    # Advance the next row for that reader
    open_nrs[i].load_next()

    # Recompute the open named readers
    open_nrs = list(filter(lambda nr: nr.is_open, named_readers))

  # All readers should now be closed
  assert all(not nr.is_open for nr in named_readers)

def ingest_tcpdumps(writer, fieldnames, infile_list, config_dict):
  # Parse node type from filename
  nodes = dict()
  name_to_file = dict()
  for infile in infile_list:
    parts = infile.split('/')
    end = parts[-1].index("_dump")
    n = parts[-1][:end]

    nodes[infile] = n
    name_to_file[n] = infile

  # Partition the infile list into groups that must be used for naming
  # messages using a marker (marker_group) and the remaining ones (remaining_group)
  marker_group = set()
  remaining_group = set()
  for name in name_to_file.keys():
    # The physical source of messages is where we 
    # employing naming / marking of messages
    if name == "attacker" or name.startswith("client"):
      marker_group.add(name)
    else:
      remaining_group.add(name)

  mk_reader = lambda f : csv.DictReader(f, delimiter=";", quotechar='"')

  # Now process the marker group considering earliest timestamp first per
  # row in order to assign message numbers
  uid_map_number = dict()
  if len(marker_group) > 0:
    group = sorted(marker_group)
    print(f"Reading {group}...")
    open_files = [open(name_to_file[name], 'r') for name in group]
    named_readers = [NamedReader(reader=mk_reader(open_files[i]), 
                                  name=group[i]) for i, _ in enumerate(group)]
    run_through_named_readers(writer, named_readers, config_dict, uid_map_number)

  # Open each file sequentially
  for node in remaining_group:
    infile = name_to_file[node]
    with open(infile, 'r') as inf:
      print(f"Reading {node}...")
      reader = mk_reader(inf)
      
      BATCH_SIZE = 10_000
      row_batch = list()

      try:
        row = next(reader)
      except StopIteration:
        row = None
      while row:
        try:
          # Process this row
          fieldmap = { f : "" for f in fieldnames }
          fieldmap['node_type'] = "originserver" if node == "server" else node
          process_row(row, writer, fieldmap, config_dict, row_batch, uid_map_number)

          # Write processed rows in batches
          if len(row_batch) >= BATCH_SIZE:
            writer.writerows(row_batch)
            row_batch = list()

          # Move to next row
          row = next(reader)

        except StopIteration:
          # No more new rows ==> handle potentially 
          # lingering batch of rows to write
          if len(row_batch) > 0:
            writer.writerows(row_batch)
          
          # No more rows so loop should exit
          row = None

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    config_dict = json.load(f)

  # Strip mismatched right ; then split
  infile_list = args.infiles.rstrip(';').split(';')

  with open(args.outfile, 'w') as outf:
    # Write fields of the header
    writer = csv.DictWriter(outf, fieldnames=fieldnames)
    writer.writeheader()
  
    # Process the input files
    ingest_tcpdumps(writer, fieldnames, infile_list, config_dict)

  # Log and dump http response code stats
  global http_response_code_map_freq, coap_response_code_map_freq
  maps_and_files = [(http_response_code_map_freq, args.httpoutfile), (coap_response_code_map_freq, args.coapoutfile)]
  for m, f in maps_and_files:
    try:
      del m[""]
    except KeyError:
      pass
    with open(f, 'w') as handle:
      json.dump(m, handle)

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
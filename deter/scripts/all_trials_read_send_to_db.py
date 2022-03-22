import io
import os
import sys
import json
import time
import argparse

import psycopg2
import psycopg2.extras

import numpy as np
import pandas as pd

from pprint import pprint
from multiprocessing.pool import ThreadPool

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infile-csvs', dest='infile_csvs',
                      help='', action='store', type=str)
  parser.add_argument('-e', '--expname', dest='expname',
                      help='', action='store', type=str)
  parser.add_argument('-t', '--trial-number', dest='trial',
                      help='', action='store', type=str)
  parser.add_argument('-c', '--config', dest='config',
                      help='', action='store', type=str)
  parser.add_argument('-d', '--dbname', dest='dbname',
                      help='', action='store', type=str)
  parser.add_argument('-m', '--metrics-file', dest='metrics_file',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

con = psycopg2.connect(user="postgres", password="coap", dbname=args.dbname)
cur = con.cursor()

# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# --------------------------------------------------------------------

class TimerException(Exception):
  """
  Exceptions specific to instances of the `Timer` below
  """
  pass

class Timer:
  """
  Class to aid in timing code
  """
  def __init__(self, start_text, end_text="Time elapsed: {:.4f} seconds", print_header=False):
    self._start_time_ns = None
    self._start_text = start_text
    self._end_text = end_text
    self.print_header = print_header

  def start(self):
    if self._start_time_ns is not None:
      raise TimerException(f"Cannot start Timer, because it is already running with start time {self._start_time_ns}.")

    self._start_time_ns = time.perf_counter_ns()
    if self.print_header:
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
    print(self.stop())


def read_data(node_name_map_ids):
  # Split ID maps
  nname_map_node_id = {nname: str(node_name_map_ids[nname]["node_id"]) for nname in node_name_map_ids}
  nname_map_dnid = {nname: str(node_name_map_ids[nname]["dnid"]) for nname in node_name_map_ids}

  # Typed parsing of the packet data
  float_t = np.float64
  str_t = pd.StringDtype()
  uint16_t = pd.UInt16Dtype()
  uint32_t = pd.UInt32Dtype()
  bool_t = pd.BooleanDtype()
  dtype = {
    'node_type': str_t,
    'message_marker': uint32_t,
    'message_timestamp': float_t, 
    'message_source': str_t,
    'message_destination': str_t,
    'message_protocol': str_t,
    'message_size': uint16_t,
    'coap_type': str_t,
    'coap_code': str_t,
    'coap_retransmitted': bool_t,
    'http_request': bool_t,
    'http_request_method': str_t,
    'http_response_code': uint32_t,
  }

  # Get each trial's csv summary
  infiles = args.infile_csvs.rstrip(";").split(";")
  num_trials = len(infiles)

  def read_trial_df(trial_dfs, i):
    tdf = pd.read_csv(infiles[i], dtype=dtype, usecols=dtype.keys(), engine="c")
    
    # Add IDs and metadata
    tdf['cmci'] = -1
    tdf['hmci'] = -1
    tdf['message_id'] = -1
    tdf['trial'] = i + 1

    trial_dfs[i] = tdf

  # Read each trial's data in a separate thread
  trial_dfs = [None] * num_trials
  with ThreadPool(num_trials) as pool:
    for trial_idx in range(num_trials):
      pool.apply_async(read_trial_df, (trial_dfs, trial_idx))
    pool.close()
    pool.join()
  
  # Combine the trial dataframes into one
  df = pd.concat(trial_dfs)

  # node_type should get dnid
  df.node_type.replace(nname_map_dnid, inplace=True)

  # message_source and message_destination should get node_id
  df.message_source.replace(nname_map_node_id, inplace=True)
  df.message_destination.replace(nname_map_node_id, inplace=True)

  # Add row counter
  df = df.reset_index()
  df['message_index'] = np.arange(len(df))
  df.set_index('message_index')

  return df

def insert_experiment_table(cfg):
  sql = """
  SELECT insert_into_experiment(
    %s, %s,
    %s, %s, %s, 
    %s,
    %s, %s, %s, %s, %s, %s,
    %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s
  );
  """
  sql_args = (
    args.expname, cfg["attack_rate"], 
    cfg["server_connections"], cfg["max_keep_alive_requests"], cfg["num_clients"], 
    cfg["num_trials"],
    cfg["origin_server_duration"], cfg["attacker_duration"], cfg["receiver_duration"], cfg["proxy_duration"], cfg["client_duration"], cfg["attacker_start_lag_duration"],
    cfg["topology_name"],
    cfg["num_proxy_connections"], cfg["request_timeout"], cfg["max_retries"], cfg["keep_alive_duration"], cfg["request_retry_interval"], cfg["reuse_connections"],
    cfg["run_proxy_with_dtls"], cfg["run_proxy_with_https"]
  )
  cur.execute(sql, sql_args)
  con.commit()

def insert_node_table(cfg, node_name_map_ids):
  sql = """
  SELECT insert_into_node(
    %s, %s, %s
  );
  """
  for nname, hdict in cfg["hosts"].items():
    sql_args = (
      nname, hdict['hardware'], hdict['operating_system']
    )
    cur.execute(sql, sql_args)
    node_id = cur.fetchone()[0]
    
    # Note this node's node_id
    node_name_map_ids.setdefault(nname, dict())
    node_name_map_ids[nname]["node_id"] = node_id
  
  con.commit()

def insert_deployed_node_table(cfg, node_name_map_ids):
  # Insert nodes into deployed nodes associated with the exp
  sql = """
  SELECT insert_into_deployed_node(
    %s, %s
  );
  """
  for nname, nids in sorted(node_name_map_ids.items()):
    sql_args = (args.expname, nids["node_id"])
    cur.execute(sql, sql_args)
    dnid = cur.fetchone()[0]
    node_name_map_ids[nname]["dnid"] = dnid
  
  con.commit()

def insert_metadata(cfg, node_name_map_ids):
  insert_experiment_table(cfg)
  insert_node_table(cfg, node_name_map_ids)
  insert_deployed_node_table(cfg, node_name_map_ids)

def insert_coap(df):
  """
  Insert uniquely valued coap messages into DB. Note 
  the new cmci for each one and reflect the update
  to the dataframe
  """
  with Timer("\tFiltering dataframe for coap"):
    coap_df = df[df["message_protocol"] == "coap"]
    coap_message_df = coap_df[["coap_type", "coap_code", "coap_retransmitted"]]
    
  with Timer("\tFiltering for uniquely valued coap groups"):
    # Count the rows with unique coap values
    groups_df = coap_message_df.value_counts().reset_index(name="count")[["coap_type", "coap_code", "coap_retransmitted"]]
    groups = tuple(groups_df.to_records(index=False).tolist())
    group_sequence = sum(groups, ()) # Convert unique rows to a flattened tuple
  
  if len(groups) <= 0:
    raise Exception("No coap groups found")

  # Batch the insertions and IDs fetches in a single SQL statement
  base_select_sql  = """SELECT * FROM insert_into_coap(%s, %s, %s)"""
  union_select_sql = """UNION SELECT * FROM insert_into_coap(%s, %s, %s)"""
  sql_parts = [None for _ in range(len(groups))]
  sql_parts[0] = base_select_sql
  for i in range(1, len(groups)):
    sql_parts[i] = union_select_sql
  sql = " ".join(sql_parts)

  with Timer("\tSending coap groups to DB"):
    with con.cursor() as c:
      c.execute(sql, group_sequence)
      cmcis = c.fetchall()
      con.commit()
    cmcis = sum(cmcis, ())

  with Timer("\tUpdating coap message IDs"):
    # Associate each uniquely valued coap tuple in the dataframe with the coap ID from the DB 
    for g, cmci in zip(groups, cmcis):
      df.loc[(df["coap_type"] == g[0])
             & (df["coap_code"] == g[1])
             & (df["coap_retransmitted"] == g[2]), 'cmci'] = cmci

  print(f"\t==> Added {len(groups)} unique coap groups {groups} with cmci {cmcis}")

def insert_message_coap(df):
  """
  Insert uniquely valued coap messages into DB. Note
  the new message_id for each one and reflect the update
  to the dataframe
  """
  with Timer("\tFiltering dataframe for message-coap"):
    message_cols = ["message_size", "message_source", "message_destination", "cmci"]
    message_df = df[message_cols][(df["message_protocol"] == "coap") & (df['cmci'] > 0)]

  with Timer("\tFiltering for uniquely valued message-coap groups"):
    # Count the rows with unique coap values
    groups_df = message_df.value_counts().reset_index(name="count")[message_cols]
    groups = tuple(groups_df.to_records(index=False).tolist())
    group_sequence = sum(groups, ()) # Convert unique rows to a flattened tuple

  # Batch the insertions and IDs fetches in a single SQL statement
  base_select_sql  = """SELECT * FROM insert_into_message_coap(%s, %s, %s, %s)"""
  union_select_sql = """UNION SELECT * FROM insert_into_message_coap(%s, %s, %s, %s)"""
  sql_parts = [None for _ in range(len(groups))]
  sql_parts[0] = base_select_sql
  for i in range(1, len(groups)):
    sql_parts[i] = union_select_sql
  sql = " ".join(sql_parts)

  with Timer("\tSending message-coap groups to DB"):
    with con.cursor() as c:
      c.execute(sql, group_sequence)
      message_ids = c.fetchall()
      con.commit()
    message_ids = sum(message_ids, ())

  with Timer("\tUpdating message-coap IDs"):
    # Associate each uniquely valued message-coap tuple in the dataframe with the message ID from the DB 
    for g, message_id in zip(groups, message_ids):
      df.loc[(df["message_size"] == g[0])
             & (df["message_source"] == g[1])
             & (df["message_destination"] == g[2])
             & (df["cmci"] == g[3]), 'message_id'] = message_id

  print(f"\t==> Added {len(groups)} unique message-coap groups")

def insert_http(df, cfg, node_name_map_ids):
  # Get http messages
  http_df = df[df["message_protocol"] == "http"]

  http_req_df = http_df[http_df["http_request"]]
  http_res_df = http_df[~http_df["http_request"]]

  requests_gb = http_req_df.groupby(by=["http_request", "http_request_method"])
  responses_gb = http_res_df.groupby(by=["http_request", "http_response_code"])

  sql = """
    SELECT insert_into_http(%s, %s, %s);
  """

  # Insert uniquely valued http requests into DB, note 
  # the new hmci for each one
  with con.cursor() as c:
    for dhqg, idxs in requests_gb.groups.items():
      c.execute(sql, [bool(dhqg[0]), dhqg[1], -1])
      hmci = c.fetchone()[0]
      df.loc[df["message_index"].isin(set(idxs)), 'hmci'] = hmci
    con.commit()

  # Insert uniquely valued http responses into DB, note 
  # the new hmci for each one
  with con.cursor() as c:
    for dhsg, idxs in responses_gb.groups.items():
      c.execute(sql, [bool(dhsg[0]), '', dhsg[1]])
      hmci = c.fetchone()[0]
      df.loc[df["message_index"].isin(set(idxs)), 'hmci'] = hmci
    con.commit()

  http_df = df[df["message_protocol"] == "http"]
  message_df = http_df[["message_size", "message_source", "message_destination", "hmci"]]

  # Insert uniquely valued messages into DB, note 
  # the new message_id for each one
  sql = """
    SELECT insert_into_message_http(%s, %s, %s, %s);
  """
  message_df_gb = message_df.groupby(by=["message_size", "message_source", "message_destination", "hmci"])
  with con.cursor() as c:
    for dmg, idxs in message_df_gb.groups.items():
      c.execute(sql, dmg)
      message_id = c.fetchone()[0]
      df.loc[df["message_index"].isin(idxs), 'message_id'] = message_id
    con.commit()

def insert_event(df, cfg, node_name_map_ids):
  # Construct event
  event_df = df[["node_type", "message_id", "message_timestamp", "trial", "message_marker"]]
  event_df = event_df.rename(columns={
    "node_type": "observer_id",
    "message_timestamp": "observe_timestamp",
  })

  with con.cursor() as c:
    c.execute("""BEGIN;""")
    c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_observer_id_fkey;""")
    c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_message_id_fkey;""")

    # And send a csv copy via stdin
    buf = io.StringIO()
    event_df.to_csv(buf, header=None, index=None)
    buf.seek(0)
    c.copy_from(buf, "event", columns=event_df.columns, sep=",")

    c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_message_id_fkey FOREIGN KEY ("message_id") REFERENCES "message" ("message_id");""")
    c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_observer_id_fkey FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");""")
    c.execute("""COMMIT;""")
    con.commit()

def insert_metrics(node_name_map_ids):
  # Alias server to origin server
  node_name_map_ids["server"] = {**node_name_map_ids["originserver"]}

  # Read and massage dataframe of the metrics
  metrics_df = pd.read_csv(args.metrics_file, engine="c")
  metrics_df = metrics_df.rename(columns={
    "device_name": "observer_id",
    "metric_name": "metric_type",
  })
  metrics_df = metrics_df[["observer_id", "trial", "observation_timestamp", "metric_type", "metric_value"]]

  # Replace english names of devices (like proxy or server) with their dnids
  for node_name, ids in node_name_map_ids.items():
    metrics_df.loc[metrics_df["observer_id"] == node_name, 'observer_id'] = ids["dnid"]

  # Copy metrics to the node metric table
  with con.cursor() as c:
    buf = io.StringIO()
    metrics_df.to_csv(buf, header=None, index=None)
    buf.seek(0)
    c.copy_from(buf, "node_metric", columns=metrics_df.columns, sep=",")
    con.commit()

def insert_packets(df, cfg, node_name_map_ids):
  with Timer("Inserting coap", print_header=True):
    insert_coap(df)

  with Timer("Inserting message-coap", print_header=True):
    insert_message_coap(df)

  with Timer("Inserting http"):
    insert_http(df, cfg, node_name_map_ids)
  
  # Then bulk load the events
  with Timer("Inserting event"):
    insert_event(df, cfg, node_name_map_ids)

def run_analyze():
  with con.cursor() as c:
    c.execute("ANALYZE")
    con.commit()

def check_experiment_not_inserted(cfg):
  with con.cursor() as c:
    c.execute(f"""SELECT COUNT(*) FROM experiment WHERE exp_id = '{cfg["expname"]}'""")
    con.commit()
    if c.fetchone()[0] > 0:
      raise Exception(f"""Experiment {cfg["expname"]} is already in the database {args.dbname}""")

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    cfg = json.load(f)

  # Check that the experiment is not already in the database
  # check_experiment_not_inserted(cfg)

  # Insert metadata & populate information about 
  # each node's IDs in tables
  node_name_map_ids = dict()
  with Timer("Inserting metadata"):
    insert_metadata(cfg, node_name_map_ids)

  # Insert metrics recorded during the experiment
  with Timer("Inserting metrics"):
    insert_metrics(node_name_map_ids)

  # Read the actual experiment data into a typed dataframe
  with Timer("Reading data", print_header=True):
    df = read_data(node_name_map_ids)

  # Start with coap messages, split into chunks
  insert_packets(df, cfg, node_name_map_ids)

  # Run ANALYZE for better read performance later
  with Timer("Running analyze"):
    run_analyze()

  con.close()

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  try:
    main()
  except Exception as e:
    con.close()
    raise e
import io
import sys
import json
import time
import argparse

import psycopg2

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

def read_data(node_name_map_ids):
  # Split ID maps
  nname_map_node_id = {nname: node_name_map_ids[nname]["node_id"] for nname in node_name_map_ids}
  nname_map_dnid = {nname: node_name_map_ids[nname]["dnid"] for nname in node_name_map_ids}

  # Typed parsing of the packet data
  float_t = np.float
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
  print("Reading dataframes...")
  trial_dfs = [None] * num_trials
  with ThreadPool(num_trials) as pool:
    for trial_idx in range(num_trials):
      pool.apply_async(read_trial_df, (trial_dfs, trial_idx))
    pool.close()
    pool.join()
  
  # Combine the trial dataframes into one
  print("Combining dataframes...")
  df = pd.concat(trial_dfs)

  print("Done!")

  print("Massaging dataframe...")
  # node_type should get dnid
  df.node_type.replace(nname_map_dnid, inplace=True)

  # message_source and message_destination should get node_id
  df.message_source.replace(nname_map_node_id, inplace=True)
  df.message_destination.replace(nname_map_node_id, inplace=True)

  # Add row counter
  df = df.reset_index()
  df['message_index'] = np.arange(len(df))
  df.set_index('message_index')
  print("Done!")

  return df

def insert_experiment_table(cfg):
  sql = """
  SELECT insert_into_experiment(
    %s, %s,
    %s, %s, %s, 
    %s,
    %s, %s, %s, %s, %s, %s,
    %s,
    %s, %s, %s, %s, %s, %s
  );
  """
  sql_args = (
    args.expname, cfg["attack_rate"], 
    cfg["server_connections"], cfg["max_keep_alive_requests"], cfg["num_clients"], 
    cfg["num_trials"],
    cfg["origin_server_duration"], cfg["attacker_duration"], cfg["receiver_duration"], cfg["proxy_duration"], cfg["client_duration"], cfg["attacker_start_lag_duration"],
    cfg["topology_name"],
    cfg["num_proxy_connections"], cfg["request_timeout"], cfg["max_retries"], cfg["keep_alive_duration"], cfg["request_retry_interval"], cfg["reuse_connections"]
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
  # Experiment
  insert_experiment_table(cfg)

  # Node & Deployed Node
  insert_node_table(cfg, node_name_map_ids)
  insert_deployed_node_table(cfg, node_name_map_ids)

def insert_coap(df, cfg, node_name_map_ids):
  # Get coap and necessary subset
  coap_df = df[df["message_protocol"] == "coap"]
  cdf = coap_df[["coap_type", "coap_code", "coap_retransmitted",
             "message_size", "message_source", "message_destination",
             "node_type", "message_timestamp"]]
  
  coap_message_df = cdf[["coap_type", "coap_code", "coap_retransmitted"]]
  coap_message_gb = coap_message_df.groupby(by=["coap_type", "coap_code", "coap_retransmitted"])

  # Insert uniquely valued coap messages into DB, note 
  # the new cmci for each one
  print("Inserting coap...")
  sql = """
    SELECT insert_into_coap(%s, %s, %s);
  """
  with con.cursor() as c:
    for dcg, idxs in coap_message_gb.groups.items():
      c.execute(sql, [dcg[0], dcg[1], bool(dcg[2])])
      cmci = c.fetchone()[0]
      df.loc[df["message_index"].isin(idxs), 'cmci'] = cmci
    con.commit()

  # Message and necessary subset
  coap_df = df[df["message_protocol"] == "coap"]
  message_df = coap_df[["message_size", "message_source", "message_destination", "cmci"]]
  message_df = message_df[message_df['cmci'] > 0]

  # Insert uniquely valued messages into DB, note 
  # the new message_id for each one
  print("Inserting coap message...")
  sql = """
    SELECT insert_into_message_coap(%s, %s, %s, %s);
  """
  message_df_gb = message_df.groupby(by=["message_size", "message_source", "message_destination", "cmci"])
  with con.cursor() as c:
    for dmg, idxs in message_df_gb.groups.items():
      c.execute(sql, dmg)
      message_id = c.fetchone()[0]
      df.loc[df["message_index"].isin(idxs), 'message_id'] = message_id
    con.commit()

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
  print("Inserting http requests...")
  with con.cursor() as c:
    for dhqg, idxs in requests_gb.groups.items():
      c.execute(sql, [bool(dhqg[0]), dhqg[1], -1])
      hmci = c.fetchone()[0]
      df.loc[df["message_index"].isin(set(idxs)), 'hmci'] = hmci
    con.commit()

  # Insert uniquely valued http responses into DB, note 
  # the new hmci for each one
  print("Inserting http responses...")
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
  print("Inserting http message...")
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

  print("Copying event...")
  start = time.time()
  with con.cursor() as c:
    print("Dropping constraints table...")
    c.execute("""BEGIN;""")
    c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_observer_id_fkey;""")
    c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_message_id_fkey;""")
    print("Done")

    # And send a csv copy via stdin
    buf = io.StringIO()
    event_df.to_csv(buf, header=None, index=None)
    buf.seek(0)
    print("Copying...")
    c.copy_from(buf, "event", columns=event_df.columns, sep=",")
    print("Done")

    print("Reinstating constraints...")
    c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_message_id_fkey FOREIGN KEY ("message_id") REFERENCES "message" ("message_id");""")
    c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_observer_id_fkey FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");""")
    c.execute("""COMMIT;""")
    con.commit()
    print("Done")
  
  end = time.time()
  print(f"DONE {end - start}")

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
    print("Copying metrics...")
    buf = io.StringIO()
    metrics_df.to_csv(buf, header=None, index=None)
    buf.seek(0)
    print("Copying...")
    c.copy_from(buf, "node_metric", columns=metrics_df.columns, sep=",")
    con.commit()
    print("Done")


def insert_packets(df, cfg, node_name_map_ids):
  # Insert coap & http
  insert_coap(df, cfg, node_name_map_ids)
  insert_http(df, cfg, node_name_map_ids)
  
  # Then bulk load the events
  insert_event(df, cfg, node_name_map_ids)

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    cfg = json.load(f)

  # Insert metadata & populate information about 
  # each node's IDs in tables
  node_name_map_ids = dict()
  insert_metadata(cfg, node_name_map_ids)

  # Insert metrics recorded during the experiment
  insert_metrics(node_name_map_ids)

  # Read the actual experiment data into a typed dataframe
  df = read_data(node_name_map_ids)

  # Start with coap messages, split into chunks
  insert_packets(df, cfg, node_name_map_ids)

  con.close()

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
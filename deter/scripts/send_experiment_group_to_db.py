import io
import sys
import json
import argparse

import psycopg2
import psycopg2.extras

import polars as pl

from deter_utils import Timer
from deter_utils import pl_replace
from deter_utils import pl_replace_predicates_to_values
from deter_utils import batch_sql_function_calls
from deter_utils import zero_out_response_code_for_http_request
from deter_utils import zero_out_request_method_for_http_response
from deter_utils import cast_to_database_types
from deter_utils import database_message_pattern_fields
from deter_utils import database_coap_fields
from deter_utils import database_http_fields

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-d', '--dbname', dest='dbname',
                      help='', action='store', type=str)
  parser.add_argument('-a', '--analyze', dest='analyze',
                      help='', action='store', type=int)

  args = parser.parse_args()
  args.analyze = bool(args.analyze)
  return args

args = parse_args()

con = psycopg2.connect(user="postgres", password="coap", dbname=args.dbname, application_name="send_experiment_group_to_db")
cur = con.cursor()

# ----------------------------------------

def read_data(expname_map_config):
  """
  Read data in from all specified input files and return
  the result of concatenating the data together with some
  initial processing.
  """
  def read_exp_trial_dfs(expname):
    """
    This producedure loads experiment expname's data
    from all trials lazily into the trial_dfs list.
    """
    cfg = expname_map_config[expname]
    num_trials = int(cfg["num_trials"])
    base_dir_path = cfg["base_dir_path"]
    for t in range(1, num_trials + 1):
      trial_dir_path = f"{base_dir_path}/{t}"
      trial_data_path = f"{trial_dir_path}/{expname}.parquet"
      df = (
        # For each trial, read the trial data into memory.
        pl
        .scan_parquet(trial_data_path)
        .with_columns([
          # Add columns for database IDs, trial, and experiment.
          pl.lit(-1).alias("cmci"),
          pl.lit(-1).alias("hmci"),
          pl.lit(-1).alias("message_id"),
          pl.lit(t).alias("trial"),
          pl.lit(expname).alias("exp_id"),
          
          # Replace string node names with database IDs.
          pl_replace("node_type", cfg["node_name_map_dnid"]),
          pl_replace("message_source", cfg["node_name_map_node_id"]),
          pl_replace("message_destination", cfg["node_name_map_node_id"]), 
          
          # Change the values of HTTP request and response to 
          # database type-friendly values.
          zero_out_response_code_for_http_request,
          zero_out_request_method_for_http_response,
        ])
        # Cast column types to expected DB types.
        .with_columns(cast_to_database_types)
      )
      trial_dfs.append(df)

  # Collect all experiment trial data lazily into memory.
  trial_dfs = list()
  for expname in expname_map_config:
    read_exp_trial_dfs(expname)
  df = pl.concat(trial_dfs)

  # Assert that we read as many trials as we expect to.
  expected_num_trial_dfs = sum(int(cfg["num_trials"]) for _, cfg in expname_map_config.items())
  assert len(trial_dfs) == expected_num_trial_dfs

  return df

def insert_experiment_table(expname_map_config):
  """
  Insert experiment configuration values into the DB.
  """
  sql = """
    SELECT insert_into_experiment(
      %(expname)s, 
      %(attack_rate)s,
      %(server_connections)s,
      %(max_keep_alive_requests)s,
      %(num_clients)s, 
      %(num_trials)s,
      %(origin_server_duration)s,
      %(attacker_duration)s,
      %(receiver_duration)s,
      %(proxy_duration)s,
      %(client_duration)s,
      %(attacker_start_lag_duration)s,
      %(topology_name)s,
      %(num_proxy_connections)s,
      %(request_timeout)s,
      %(max_retries)s,
      %(keep_alive_duration)s,
      %(request_retry_interval)s,
      %(reuse_connections)s,
      %(run_proxy_with_dtls)s,
      %(run_proxy_with_https)s,
      %(run_attacker)s
    );
  """
  for _, cfg in expname_map_config.items():
    cur.execute(sql, cfg)
  con.commit()

def insert_node_table(expname_map_config):
  """
  
  Insert experiment node templates into the node table in the DB.
  """
  expname_map_node_name_map_ids = dict()
  
  for expname, cfg in expname_map_config.items():
    # Stream each node, its hardware, and operating system as arguments to the SQL query
    node_name_and_details = sorted(cfg["hosts"].items())
    sql_args = [(name, details["hardware"], details["operating_system"]) \
                  for name, details in node_name_and_details]
    sql_arg_stream = sum(sql_args, ())      

    # Batch the insertions and node ID fetches in a single SQL statement
    select_sql = """SELECT * FROM insert_into_node(%s, %s, %s)"""
    sql = batch_sql_function_calls(select_sql, len(node_name_and_details))
    cur.execute(sql, sql_arg_stream)
    node_ids = cur.fetchall()
    con.commit()

    node_name_map_ids = dict()
    for (node_name, _), (node_id,) in zip(node_name_and_details, node_ids):
      # Record this node's node_id
      node_name_map_ids.setdefault(node_name, dict())
      node_name_map_ids[node_name]["node_id"] = node_id

    # Update the temporary expname map with the new node IDs
    expname_map_node_name_map_ids[expname] = node_name_map_ids

  for expname, node_name_map_ids in expname_map_node_name_map_ids.items():
    expname_map_config[expname]["node_name_map_ids"] = node_name_map_ids

def insert_deployed_node_table(expname_map_config):
  """
  Insert this experiment deployed nodes into the deployed node table in the DB.
  """
  for expname, cfg in expname_map_config.items():
    # Stream each experiment name and node id to the SQL query
    node_name_map_ids = cfg["node_name_map_ids"]
    node_name_and_ids = sorted(node_name_map_ids.items())
    sql_args = [(cfg["expname"], ids["node_id"]) \
                  for _, ids in node_name_and_ids]
    sql_args = sum(sql_args, ())
    
    # Batch the insertions and node ID fetches in a single SQL statement
    select_sql = """SELECT insert_into_deployed_node(%s, %s)"""
    sql = batch_sql_function_calls(select_sql, len(node_name_map_ids))
    cur.execute(sql, sql_args)
    deployed_node_ids = cur.fetchall()
    con.commit()

    for (node_name, _), (dnid,) in zip(node_name_and_ids, deployed_node_ids):
      # Record this node's dnid
      node_name_map_ids[node_name]["dnid"] = dnid

    # Add node_id and dnid mappings into the config
    node_name_map_ids["server"] = node_name_map_ids["originserver"]
    cfg["node_name_map_node_id"] = {node_name: node_name_map_ids[node_name]["node_id"] for node_name in node_name_map_ids}
    cfg["node_name_map_dnid"] = {node_name: node_name_map_ids[node_name]["dnid"] for node_name in node_name_map_ids}

def insert_metadata(expname_map_config):
  """
  Insert metadata of this experiment to the database. Metadata includes
  configuration values and nodes which participated in the experiment.
  """
  insert_experiment_table(expname_map_config)
  insert_node_table(expname_map_config)
  insert_deployed_node_table(expname_map_config)

def insert_coap(message_patterns_df, unique_coap_df, log=False):
  """
  Insert uniquely valued coap messages into DB. Note 
  the new cmci for each one and reflect the update
  to the dataframe.
  """
  with Timer("\tFiltering dataframe for uniquely valued coap groups", log=log):
    groups = tuple(unique_coap_df.to_pandas().to_records(index=False).tolist())
    group_sequence = sum(groups, ()) # Convert unique rows to a flattened tuple
  
  if len(groups) <= 0:
    raise Exception("No coap groups found")

  # Batch the insertions and IDs fetches in a single SQL statement
  sql = batch_sql_function_calls("""SELECT * FROM insert_into_coap(%s, %s, %s)""", len(groups))

  with Timer("\tSending coap groups to DB", log=log):
    with con.cursor() as c:
      c.execute(sql, group_sequence)
      cmcis = c.fetchall()
      con.commit()
    cmcis = sum(cmcis, ())

  with Timer("\tUpdating coap message IDs", log=log):
    # Associate each uniquely valued coap tuple in the dataframe with the coap ID from the DB 
    filter_predicates = [(
      (pl.col("coap_type") == g[0])
      & (pl.col("coap_code") == g[1])
      & (pl.col("coap_retransmitted") == g[2])
      ) for g in groups
    ]
    message_patterns_df = message_patterns_df.with_columns([
      pl_replace_predicates_to_values("cmci", filter_predicates, cmcis)
    ])
  
  if log:
    print(f"\t==> Added {len(groups)} unique coap groups {groups} with cmci {cmcis}")
  
  return message_patterns_df

def insert_http(message_patterns_df, unique_http_df, log=False):
  """
  Insert uniquely valued http requests and responses into DB. 
  Note the new hmci ID for each one and reflect the update
  to the dataframe.
  """
  with Timer("\tFiltering dataframe for uniquely valued http groups", log=log):
    groups = tuple(unique_http_df.to_pandas().to_records(index=False).tolist())
    group_sequence = sum(groups, ()) # Convert unique rows to a flattened tuple
  
  if len(groups) <= 0:
    raise Exception("No http groups found")

  # Batch the insertions and IDs fetches in a single SQL statement
  select_sql = """SELECT * FROM insert_into_http(%s, %s, %s)"""
  sql = batch_sql_function_calls(select_sql, len(groups))

  # Execute the insertions and fetch the returned IDs
  with Timer(f"\tSending http groups to DB", log=log):
    with con.cursor() as c:
      c.execute(sql, group_sequence)
      hmcis = c.fetchall()
      con.commit()
      hmcis = sum(hmcis, ())

  # Update the hmcis for columns with matching values
  with Timer(f"\tUpdating http message IDs", log=log):
    # Here, we need to update http requests and the responses
    # separately. This is because the fields which requests and
    # responses care about for equality in the hmci update below
    # are different. Normally this is not an issue, but the
    # "irrelevant" field (e.g., response code in a request)
    # could have a different value, so we effectively ignore it
    # by having a predicate for requests and a predicate for 
    # responses.
    hmci_update_request_predicates = [
      (pl.col("message_protocol") == "http")
        & (pl.col("http_request") == True)
        & (pl.col("http_request_method") == g[1])
        & (pl.col("hmci") < 0)
      for g in groups
    ]
    hmci_update_response_predicates = [
      (pl.col("message_protocol") == "http")
        & (pl.col("http_request") == False)
        & (pl.col("http_response_code") == g[2])
        & (pl.col("hmci") < 0)
      for g in groups
    ]
    # These replacement statements for the hmci need to be 
    # executed separately so they don't interfere with each
    # other. Do not place them in the same with_columns.
    message_patterns_df = (
      message_patterns_df
        .with_columns([
          pl_replace_predicates_to_values("hmci", hmci_update_request_predicates, hmcis),
        ])
        .with_columns([
          pl_replace_predicates_to_values("hmci", hmci_update_response_predicates, hmcis),
        ])
    )

  if log:
    print(f"\t==> Added {len(groups)} unique https groups {groups} with hmci {hmcis}")

  return message_patterns_df

def _insert_message_for_protocol(message_patterns_df, protocol, log=False):
  """
  Insert uniquely valued `protocol` messages into DB. Note
  the new message_id for each one and reflect the update
  to the dataframe. Protocol can be either http or coap.
  """
  supported_protocols = {"coap", "http"}
  if protocol not in supported_protocols:
    raise Exception(f"Got unsupported protocol {protocol}. Supported protocols are {supported_protocols}")

  # Set attributes of the database based on the input protocol
  insertion_function_name = f"insert_into_message_{protocol}"
  protocol_message_id_name = f"{protocol[0]}mci"

  assert insertion_function_name in {"insert_into_message_coap", "insert_into_message_http"}
  assert protocol_message_id_name in {"cmci", "hmci"}

  with Timer(f"\tFiltering dataframe for uniquely valued message-{protocol} groups", log=log):
    message_df = (
      message_patterns_df
      .filter(
        (pl.col("message_protocol") == protocol)
        & (pl.col(protocol_message_id_name) > 0)
      )
      .select(database_message_pattern_fields + [protocol_message_id_name])
      .unique()
    )
    groups = tuple(message_df.to_pandas().to_records(index=False).tolist())
    group_sequence = sum(groups, ()) # Convert unique rows to a flattened tuple

  if len(groups) <= 0:
    raise Exception(f"No message-{protocol} groups found")

  # Batch the insertions and IDs fetches in a single SQL statement
  select_sql = f"""SELECT * FROM {insertion_function_name}(%s, %s, %s, %s)"""
  sql = batch_sql_function_calls(select_sql, len(groups))

  with Timer(f"\tSending message-{protocol} groups to DB", log=log):
    with con.cursor() as c:
      c.execute(sql, group_sequence)
      message_ids = c.fetchall()
      con.commit()
    message_ids = sum(message_ids, ())

  with Timer(f"\tUpdating message-{protocol} IDs", log=log):
    # Associate each uniquely valued message tuple in the dataframe with the message ID from the DB
    filter_predicates = [(
      (pl.col("message_size") == g[0])
      & (pl.col("message_source") == g[1])
      & (pl.col("message_destination") == g[2])
      & (pl.col(protocol_message_id_name) == g[3])
      ) for g in groups
    ]
    message_patterns_df = message_patterns_df.with_columns([
      pl_replace_predicates_to_values("message_id", filter_predicates, message_ids)
    ])

  if log:
    # The below commented print statement will clutter the 
    # stdout, so only use it when debugging.
    # print(f"\t==> Added {len(groups)} unique message-{protocol} groups {groups} with message_id {message_ids}")
    print(f"\t==> Added {len(groups)} unique message-{protocol} groups")

  return message_patterns_df

def insert_event(message_patterns_df, real_df, log=False):
  """
  Bulk insert the contents of the expriments into the event table.
  """
  # Shape event dataframe to look like event table in DB
  with Timer("\tReading and shaping dataframe for bulk insertion to event", log=log):
    event_df = (
      # Join data from disk on all the columns which differentiate
      # packet data from each other, without considering observers,
      # timestamps, and trials. The goal is to copy over the message_id
      # from message_patterns_df into real_df.
      real_df
        .join(
          message_patterns_df,
          how="left",
          on=['message_protocol', 'message_size', 'message_source', 'message_destination', 
              'coap_type', 'coap_code', 'coap_retransmitted', 'http_request', 'http_request_method', 
              'http_response_code']
        )
        # Replace the old IDs with the new IDs post-join.
        .with_columns([
          pl.col("cmci_right").alias("cmci"),
          pl.col("hmci_right").alias("hmci"),
          pl.col("message_id_right").alias("message_id"),
        ])
        .drop(["cmci_right", "hmci_right", "message_id_right"])

        # Keep only the columns that will be used for bulk-loading
        # the event table data into the database.
        .select(["node_type", "message_id", "message_timestamp", "trial", "message_marker"])
        .rename({
          "node_type": "observer_id",
          "message_timestamp": "observe_timestamp",
        })
    )

  with con.cursor() as c:
    with Timer("\tDropping constraints", log=log):
      c.execute("""BEGIN;""")
      c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_observer_id_fkey;""")
      c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_message_id_fkey;""")

    with Timer("\tChanging event table to unlogged", log=log):
      c.execute("""ALTER TABLE event SET UNLOGGED;""")

    # And send a csv copy via stdin
    with Timer("\tBuffering to stdin", log=log, print_header=log):
        buf = io.BytesIO()
        event_df.write_csv(buf, has_header=False)
        buf.seek(0)
    with Timer("\tCopying", log=log, print_header=log):
      c.copy_from(buf, "event", columns=event_df.columns, sep=",")

    with Timer("\tChanging event table back to logged", log=log):
      c.execute("""ALTER TABLE event SET LOGGED;""")
    
    with Timer("\tReinstating constraints", log=log):
      c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_message_id_fkey FOREIGN KEY ("message_id") REFERENCES "message" ("message_id");""")
      c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_observer_id_fkey FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");""")
      c.execute("""COMMIT;""")
    con.commit()

def insert_metrics(expname_map_config):
  """
  Insert experiment metrics into the DB.
  """
  def read_exp_metric_dfs(expname):
    """
    This procedure adds a lazy dataframe to the metrics_df
    list corresponding to the metrics of experimenet expname.
    """
    cfg = expname_map_config[expname]
    base_dir_path = cfg["base_dir_path"]
    metrics_data_path = f"{base_dir_path}/{expname}.metrics.csv"
    df = (
      pl
      .scan_csv(metrics_data_path)
      
      # Rename columns and re-order to match DB schema of the metric table
      .rename({
        "device_name": "observer_id",
        "metric_name": "metric_type",
      })
      .select(["observer_id", "trial", "observation_timestamp", "metric_type", "metric_value"])

      # Replace observer id with deployed node IDs from the DB
      .with_columns([
        pl_replace("observer_id", cfg["node_name_map_dnid"])
      ])
    )
    metrics_dfs.append(df)

  # Collect all metrics from experiments into memory.
  metrics_dfs = list()
  for expname in expname_map_config:
    read_exp_metric_dfs(expname)
  metrics_df = pl.concat(metrics_dfs).collect()

  # Copy metrics to the node metric table
  with con.cursor() as c:
    buf = io.BytesIO()
    metrics_df.write_csv(buf, has_header=False)
    buf.seek(0)
    c.copy_from(buf, "node_metric", columns=metrics_df.columns, sep=",")
    con.commit()

def get_unique_protocol_values_df(lazy_df, log=False):
  """
  Reads experiment data from disk, does some in memory filtering, and
  returns the resulting dataframes to the caller. This function is 
  written with special attention to performance since experiment data
  can be voluminous.
  """
  # This step is expected to be slow because it reads
  # the experiment data from disk.
  with Timer("\tReading data from disk", log=log):
    real_df = lazy_df.collect()

  # This step is expected to be somewhat slow because it 
  # does heavy computations on lots of data in memory.
  with Timer("\tReading unique message patterns from data in memory", log=log):
    message_patterns_df = (
      real_df
        .select(
          ["message_protocol"]
          + database_message_pattern_fields
          + database_coap_fields
          + database_http_fields
        )
        .unique()
        .with_columns([
          # These are database IDs which we will populate
          # later in the data analysis, but we allocate here.
          pl.lit(-1).alias("cmci"),
          pl.lit(-1).alias("hmci"),
          pl.lit(-1).alias("message_id"),
        ])
    )

  # The steps below are expected to be fast because
  # they read a small amount of data from memory.

  unique_coap_df = (
    message_patterns_df
      .filter(pl.col("message_protocol") == "coap")
      .select(database_coap_fields)
      .unique()
  )

  unique_http_df = (
    message_patterns_df
      .filter(pl.col("message_protocol") == "http")
      .select(database_http_fields)
      .unique()
      .with_columns([
        zero_out_response_code_for_http_request,
        zero_out_request_method_for_http_response
      ])
  )

  return real_df, message_patterns_df, unique_coap_df, unique_http_df

def insert_packets(lazy_df, log=False):
  with Timer("Filtering for unique protocol values", log=True, print_header=True):
    real_df, message_patterns_df, unique_coap_df, unique_http_df = get_unique_protocol_values_df(lazy_df, log=True)

  with Timer("Inserting coap"):
    message_patterns_df = insert_coap(message_patterns_df, unique_coap_df, log=log)

  with Timer("Inserting http"):
    message_patterns_df = insert_http(message_patterns_df, unique_http_df, log=log)

  with Timer("Inserting message-coap"):
    message_patterns_df = _insert_message_for_protocol(message_patterns_df, "coap", log=True)

  with Timer("Inserting message-http"):
    message_patterns_df = _insert_message_for_protocol(message_patterns_df, "http", log=True)

  # At this point, all message IDs should be set.
  assert len(message_patterns_df.filter(pl.col("message_id") < 0)) == 0

  with Timer("Inserting event", print_header=True):
    insert_event(message_patterns_df, real_df, log=True)

def run_analyze():
  with con:
    with con.cursor() as c:
      c.execute("ANALYZE")

def main():
  if args.infiles[-1] == ";":
    args.infiles = args.infiles[:-1]

  # Read experiment configurations
  expname_map_config = dict()
  for i in args.infiles.split(";"):
    expname = i.split("/")[-1]
    with open(f"{i}/metadata/config.json", "r") as f:
      cfg = json.load(f)
      expname_map_config[expname] = cfg
      expname_map_config[expname]["base_dir_path"] = i

  # Insert metadata & populate information about 
  # each node's IDs in tables
  with Timer("Inserting metadata"):
    insert_metadata(expname_map_config)

  # Insert metrics recorded during the experiment
  with Timer("Inserting metrics"):
    insert_metrics(expname_map_config)

  # Read the actual experiment data into dataframe
  with Timer("Reading data lazily"):
    lazy_df = read_data(expname_map_config)

  with open("/home/ubuntu/expname_map_config.json", "w") as f:
    json.dump(expname_map_config, f)

  # Insert all the packets captured in the experiments
  insert_packets(lazy_df)

  # Run ANALYZE for better read performance later
  if args.analyze:
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
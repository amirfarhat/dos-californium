import io
import json
import argparse

import psycopg2
import psycopg2.extras

import polars as pl

from deter_utils import Timer
from deter_utils import pl_replace
from deter_utils import pl_replace_predicates_to_values
from deter_utils import cast_to_database_types

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-e', '--expname', dest='expname',
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

# ----------------------------------------

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
  # will not reorder the outputs of the batch query. See:
  # "The Postgres implementation for UNION ALL returns 
  # values in the sequence as appended".
  # Source: https://stackoverflow.com/questions/31975969/is-order-preserved-after-union-in-postgresql
  unioned_select_sql = """UNION ALL """ + select_sql

  sql_parts = [None for _ in range(num_calls)]
  sql_parts[0] = select_sql
  for i in range(1, num_calls):
    sql_parts[i] = unioned_select_sql
  return " ".join(sql_parts)

def read_data(node_name_map_node_id, node_name_map_dnid):
  # *Lazily* read each trial's data into a separate dataframe
  infiles = args.infiles.rstrip(";").split(";")
  num_trials = len(infiles)
  trial_dfs = [None for _ in range(num_trials)]
  assert len(infiles) == num_trials == len(trial_dfs)
  for i, infile in enumerate(infiles):
    df = pl.scan_parquet(infile)
    df = df.with_columns([
      pl.lit(-1).alias("cmci"),
      pl.lit(-1).alias("hmci"),
      pl.lit(-1).alias("message_id"),
      pl.lit(i + 1).alias("trial"),
    ])
    trial_dfs[i] = df

  df = (
    # Concatenate each trial's dataframe into one
    pl
    .concat(trial_dfs)

    # Replace string node names with database IDs
    .with_columns([
      pl_replace("node_type", node_name_map_dnid),
      pl_replace("message_source", node_name_map_node_id),
      pl_replace("message_destination", node_name_map_node_id),
    ])

    # Cast column types to expected db types
    .with_columns(cast_to_database_types)
  )

  return df

def insert_experiment_table(cfg):
  """
  Insert this experiment's configuration values into the DB.
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
      %(run_proxy_with_https)s
    );
  """
  cur.execute(sql, cfg)
  con.commit()

def insert_node_table(cfg, node_name_map_ids):
  """
  Insert this experiment's node templates into the node table in the DB.
  """
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

  for (node_name, _), (node_id,) in zip(node_name_and_details, node_ids):
    # Record this node's node_id
    node_name_map_ids.setdefault(node_name, dict())
    node_name_map_ids[node_name]["node_id"] = node_id

def insert_deployed_node_table(cfg, node_name_map_ids):
  """
  Insert this experiment's deployed nodes into the deployed node table in the DB.
  """
  # Stream each experiment name and node id to the SQL query
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

def insert_metadata(cfg):
  """
  Insert metadata of this experiment to the database. Metadata includes
  configuration values and nodes which participated in the experiment.
  """
  node_name_map_ids = dict()
  insert_experiment_table(cfg)
  insert_node_table(cfg, node_name_map_ids)
  insert_deployed_node_table(cfg, node_name_map_ids)
  return node_name_map_ids

def insert_coap(df, log=False):
  """
  Insert uniquely valued coap messages into DB. Note 
  the new cmci for each one and reflect the update
  to the dataframe.
  """
  with Timer("\tFiltering dataframe for uniquely valued coap groups", log=log):
    coap_df = (
        df
        .filter(pl.col("message_protocol") == "coap")
        .select(["coap_type", "coap_code", "coap_retransmitted"])
        .unique()
    )
    groups = tuple(coap_df.collect().to_pandas().to_records(index=False).tolist())
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
    df = df.with_columns([
      pl_replace_predicates_to_values("cmci", filter_predicates, cmcis)
    ])
  
  if log:
    print(f"\t==> Added {len(groups)} unique coap groups {groups} with cmci {cmcis}")
  
  return df

def get_http_partition_groups(df):
  """
  Partition `df` into uniquely values HTTP requests and responses,
  returning the groupings of these values as tuples.
  """
  http_df = df.filter(
    pl.col("message_protocol") == "http"
  )

  http_request_df = (
    http_df
    # Only keep HTTP requests
    .filter(
      pl.col("http_request") == True
    )
    # Add placeholder http_response_code for DB schema
    .with_column(
      pl.lit(-1).alias("http_response_code")
    )
    # Keep only DB schema columns
    .select(["http_request", "http_request_method", "http_response_code"])

    # Keep distinct values
    .unique()
  )
  request_groups = tuple(http_request_df.collect().to_pandas().to_records(index=False).tolist())
  request_group_sequence = sum(request_groups, ()) # Convert unique rows to a flattened tuple
  if len(request_groups) <= 0:
    raise Exception("No http request groups found")

  http_response_df = (
    http_df
    # Only keep HTTP responses
    .filter(
      pl.col("http_request") == False
    )
    # Add placeholder http_request_method for DB schema
    .with_column(
      pl.lit("").alias("http_request_method")
    )
    # Keep only DB schema columns
    .select(["http_request", "http_request_method", "http_response_code"])

    # Keep distinct values
    .unique()
  )
  response_groups = tuple(http_response_df.collect().to_pandas().to_records(index=False).tolist())
  response_group_sequence = sum(response_groups, ()) # Convert unique rows to a flattened tuple
  if len(response_groups) <= 0:
    raise Exception("No http response groups found")

  return request_groups, request_group_sequence, response_groups, response_group_sequence

def _insert_http_partition(df, partition, groups, group_sequence, cursor, log=False):
  """
  Insert a HTTP `partition`, defined as either a request or response, to the DB
  using the DB `cursor` and group values `groups`, `group_sequence`. Finally return
  `df` with the update hcmis.
  """
  supported_partitions = {'request', 'response'}
  if partition not in supported_partitions:
    raise Exception(f"Got unsupported HTTP partition {partition}. Supported partitions are {supported_partitions}")

  # Decide about which column matters depending on whether
  # this partition of HTTP is a request or a response
  if partition == "request":
    partition_aware_column = "http_request_method"
    group_index            = 1
    is_http_request        = True
  elif partition == "response":
    partition_aware_column = "http_response_code"
    group_index            = 2
    is_http_request        = False
  else:
    raise Exception("Unreachable")

  # Batch the insertions and IDs fetches in a single SQL statement
  select_sql = """SELECT * FROM insert_into_http(%s, %s, %s)"""
  sql = batch_sql_function_calls(select_sql, len(groups))

  # Execute the insertions and fetch the returned IDs
  with Timer(f"\tSending http {partition} groups to DB", log=log):
    cursor.execute(sql, group_sequence)
    hmcis = cursor.fetchall()
    con.commit()
    hmcis = sum(hmcis, ())

  # Update the hmcis for columns with matching values
  with Timer(f"\tUpdating http {partition} message IDs", log=log):
    hmci_update_predicates = [
      (pl.col("message_protocol") == "http")
        & (pl.col("http_request") == is_http_request)
        & (pl.col(partition_aware_column) == g[group_index])
        & (pl.col("hmci") < 0)
      for g in groups
    ]
    df = df.with_columns([
      pl_replace_predicates_to_values("hmci", hmci_update_predicates, hmcis)
    ])

  if log:
    print(f"\t==> Added {len(groups)} unique http {partition} groups {groups} with hmci {hmcis}")

  return df

def _insert_message_for_protocol(df, protocol, log=False):
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

  with Timer(f"\tFiltering dataframe for uniquely valued message-{protocol} groups", log=log):
    message_df = (
      df
      .filter(
        (pl.col("message_protocol") == protocol)
        & (pl.col(protocol_message_id_name) > 0)
      )
      .select(["message_size", "message_source", "message_destination", protocol_message_id_name])
      .unique()
    )
    groups = tuple(message_df.collect().to_pandas().to_records(index=False).tolist())
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
    df = df.with_columns([
      pl_replace_predicates_to_values("message_id", filter_predicates, message_ids)
    ])

  if log:
    print(f"\t==> Added {len(groups)} unique message-{protocol} groups {groups} with message_id {message_ids}")

  return df

def insert_http(df, log=False):
  """
  Insert uniquely valued http requests and responses into DB. 
  Note the new hmci ID for each one and reflect the update
  to the dataframe.
  """
  with Timer("\tFiltering dataframe for uniquely valued http groups", log=log):
    request_groups, request_group_sequence, \
      response_groups, response_group_sequence = get_http_partition_groups(df)

  with con.cursor() as c:
    df = _insert_http_partition(df, "request", request_groups, request_group_sequence, c, log=log)
    df = _insert_http_partition(df, "response", response_groups, response_group_sequence, c, log=log)

  return df

def insert_event(df, log=False):
  """
  Bulk insert the contents of the dataframe into the event table.
  """
  # Shape event dataframe to look like event table in DB
  with Timer("\tShaping dataframe for bulk insertion to event", log=log):
    event_df = (
      df
      .select(["node_type", "message_id", "message_timestamp", "trial", "message_marker"])
      .rename({
        "node_type": "observer_id",
        "message_timestamp": "observe_timestamp",
      })
      .collect()
    )

  with con.cursor() as c:
    with Timer("\tDropping constraints", log=log):
      c.execute("""BEGIN;""")
      c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_observer_id_fkey;""")
      c.execute("""ALTER TABLE "event" DROP CONSTRAINT event_message_id_fkey;""")

    # And send a csv copy via stdin
    with Timer("\tCopying", log=log):
      buf = io.BytesIO()
      event_df.write_csv(buf, has_header=False)
      buf.seek(0)
      c.copy_from(buf, "event", columns=event_df.columns, sep=",")

    with Timer("\tReinstating constraints", log=log):
      c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_message_id_fkey FOREIGN KEY ("message_id") REFERENCES "message" ("message_id");""")
      c.execute("""ALTER TABLE "event" ADD CONSTRAINT event_observer_id_fkey FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");""")
      c.execute("""COMMIT;""")
    con.commit()

def insert_metrics(node_name_map_dnid):
  # Alias server to origin server
  node_name_map_dnid["server"] = node_name_map_dnid["originserver"]

  metrics_df = (
    pl
    .scan_csv(args.metrics_file)
    
    # Rename columns and re-order to match DB schema of the metric table
    .rename({
      "device_name": "observer_id",
      "metric_name": "metric_type",
    })
    .select(["observer_id", "trial", "observation_timestamp", "metric_type", "metric_value"])

    # Replace observer id with deployed node IDs from the DB
    .with_columns([
      pl_replace("observer_id", node_name_map_dnid)
    ])
    
    .collect()
  )

  # Copy metrics to the node metric table
  with con.cursor() as c:
    buf = io.BytesIO()
    metrics_df.write_csv(buf, has_header=False)
    buf.seek(0)
    c.copy_from(buf, "node_metric", columns=metrics_df.columns, sep=",")
    con.commit()

def insert_packets(df):
  with Timer("Inserting coap"):
    df = insert_coap(df)

  with Timer("Inserting message-coap"):
    df = _insert_message_for_protocol(df, "coap")

  with Timer("Inserting http"):
    df = insert_http(df)

  with Timer("Inserting message-http"):
    df = _insert_message_for_protocol(df, "http")
  
  with Timer("Inserting event", print_header=True):
    df = insert_event(df, log=True)

  return df

def run_analyze():
  with con.cursor() as c:
    c.execute("ANALYZE")
    con.commit()

def check_experiment_not_inserted(cfg):
  with con.cursor() as c:
    c.execute(f"""SELECT COUNT(*) FROM experiment WHERE exp_id = '{cfg["expname"]}'""")
    con.commit()
    if c.fetchone()[0] > 0:
      raise Exception(f"Experiment {cfg['expname']} is already in the database")

def main():
  # Read config into dict
  with open(args.config, 'r') as f:
    cfg = json.load(f)

  # # Check that the experiment is not already in the database
  # check_experiment_not_inserted(cfg)

  # Insert metadata & populate information about 
  # each node's IDs in tables
  with Timer("Inserting metadata"):
    node_name_map_ids = insert_metadata(cfg)
    node_name_map_node_id = {node_name: node_name_map_ids[node_name]["node_id"] for node_name in node_name_map_ids}
    node_name_map_dnid = {node_name: node_name_map_ids[node_name]["dnid"] for node_name in node_name_map_ids}

  # Insert metrics recorded during the experiment
  with Timer("Inserting metrics"):
    insert_metrics(node_name_map_dnid)

  # Read the actual experiment data into a typed dataframe
  with Timer("Reading data"):
    df = read_data(node_name_map_node_id, node_name_map_dnid)

  # Start with coap messages, split into chunks
  insert_packets(df)

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
import sys
import json
import argparse

from clickhouse_driver import Client

import polars as pl

from pprint import pprint

from deter_utils import Timer
from deter_utils import pl_replace
from deter_utils import pl_replace_predicates_to_values
from deter_utils import zero_out_response_code_for_http_request
from deter_utils import cast_to_database_types
from deter_utils import zero_out_request_method_for_http_response
from deter_utils import database_message_pattern_fields
from deter_utils import database_coap_fields
from deter_utils import database_http_fields

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infiles', dest='infiles',
                      help='', action='store', type=str)
  parser.add_argument('-d', '--dbname', dest='dbname',
                      help='', action='store', type=str)

  args = parser.parse_args()
  return args

args = parse_args()

client = Client('localhost', database=args.dbname)

# ----------------------------------------

def generate_next_unique_id(collection):
  """
  Generates IDs in autoincrementing fashion based on `collection`.

  >>> generate_next_unique_id(list())
  1
  >>> generate_next_unique_id(set())
  1
  >>> generate_next_unique_id({1})
  2
  >>> generate_next_unique_id({10})
  11
  """
  if len(collection) == 0:
    return 1
  return max(collection) + 1

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

def format_cfg(cfg):
  """
  TODO doctest
  """
  cfg["exp_id"] = cfg["expname"]
  cfg["attacker_rate"] = cfg["attack_rate"]
  cfg["server_connections"] = int(cfg["server_connections"])
  cfg["max_keep_alive_requests"] = int(cfg["max_keep_alive_requests"])
  cfg["num_clients"] = int(cfg["num_clients"])
  cfg["num_trials"] = int(cfg["num_trials"])
  cfg["origin_server_duration"] = int(cfg["origin_server_duration"])
  cfg["attacker_duration"] = int(cfg["attacker_duration"])
  cfg["receiver_duration"] = int(cfg["receiver_duration"])
  cfg["proxy_duration"] = int(cfg["proxy_duration"])
  cfg["client_duration"] = int(cfg["client_duration"])
  cfg["attacker_start_lag_duration"] = int(cfg["attacker_start_lag_duration"])
  cfg["num_proxy_connections"] = int(cfg["num_proxy_connections"])
  cfg["max_retries"] = int(cfg["max_retries"])
  cfg["reuse_connections"] = bool(cfg["reuse_connections"])
  cfg["run_proxy_with_dtls"] = bool(int(cfg["run_proxy_with_dtls"]))
  cfg["run_proxy_with_https"] = bool(int(cfg["run_proxy_with_https"]))
  cfg["run_attacker"] = bool(int(cfg["run_attacker"]))

def insert_experiment_table(expname_map_config):
  """
  Insert experiment configuration values into the DB.
  """
  sql = """
    INSERT INTO {dbname}.experiment VALUES 
  """.format(dbname=args.dbname)

  # TODO dedup

  for _, cfg in expname_map_config.items():
    format_cfg(cfg)
    client.execute(sql, [cfg], types_check=True)

def insert_node_table(expname_map_config):
  """
  Insert experiment node templates into the node table in the DB.
  """
  select_sql = """SELECT * FROM {dbname}.node""".format(dbname=args.dbname)
  insert_sql = """
    INSERT INTO {dbname}.node (node_id, node_name, hardware_type, operating_system) VALUES
  """.format(dbname=args.dbname)
  found_nodes = client.execute(select_sql)
  node_row_map_node_id = { tuple(n[1:]) : n[0] for n in found_nodes }
  
  expname_map_node_name_map_ids = dict()
  
  for expname, cfg in expname_map_config.items():
    node_name_and_details = sorted(cfg["hosts"].items())
    for name, details in node_name_and_details:
      row = (name, details["hardware"], details["operating_system"])
      if row not in node_row_map_node_id:
        node_id = generate_next_unique_id(set(node_row_map_node_id.values()))
        node_row_map_node_id[row] = node_id
        client.execute(
          insert_sql, 
          [{
            "node_id": node_id,
            "node_name": name,
            "hardware_type": details["hardware"],
            "operating_system": details["operating_system"],
          }]
        , types_check=True)
    
    # Update the temporary expname map with the new node IDs
    node_name_map_ids = { row[0] : {"node_id":node_id} for row, node_id in node_row_map_node_id.items() }
    expname_map_node_name_map_ids[expname] = node_name_map_ids

  for expname, node_name_map_ids in expname_map_node_name_map_ids.items():
    expname_map_config[expname]["node_name_map_ids"] = node_name_map_ids

def insert_deployed_node_table(expname_map_config):
  """
  Insert this experiment deployed nodes into the deployed node table in the DB.
  """
  select_sql = """SELECT * FROM {dbname}.deployed_node""".format(dbname=args.dbname)
  insert_sql = """
    INSERT INTO {dbname}.deployed_node (dnid, exp_id, node_id) VALUES
  """.format(dbname=args.dbname)
  found_deployed_nodes = client.execute(select_sql)
  deployed_node_row_map_deployed_node_id = { tuple(n[1:]) : n[0] for n in found_deployed_nodes }

  for expname, cfg in expname_map_config.items():
    node_name_map_ids = cfg["node_name_map_ids"]
    node_name_and_ids = sorted(node_name_map_ids.items())
    for node_name, ids in node_name_and_ids:
      row = (expname, ids["node_id"])
      if row not in deployed_node_row_map_deployed_node_id:
        deployed_node_id = generate_next_unique_id(set(deployed_node_row_map_deployed_node_id.values()))
        deployed_node_row_map_deployed_node_id[row] = deployed_node_id
        client.execute(
          insert_sql, 
          [{
            "dnid": deployed_node_id,
            "exp_id": expname,
            "node_id": ids["node_id"],
          }]
        )
      node_name_map_ids[node_name]["dnid"] = deployed_node_row_map_deployed_node_id[row]

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
  select_sql = """SELECT * FROM {dbname}.coap_message""".format(dbname=args.dbname)
  insert_sql = """
    INSERT INTO {dbname}.coap_message (cmci, coap_type, coap_code, coap_retransmitted) VALUES
  """.format(dbname=args.dbname)
  found_coaps = client.execute(select_sql)
  row_map_cmci = { tuple(n[1:]) : n[0] for n in found_coaps }
  
  with Timer("\tSending coap groups to DB", log=log):
    named_rows = unique_coap_df.to_dicts()
    # TODO: add check that named rows is not empty, also in other places
    for nr in named_rows:
      row = tuple(nr.values())
      if row not in row_map_cmci:
        cmci = generate_next_unique_id(set(row_map_cmci.values()))
        row_map_cmci[row] = cmci
        client.execute(insert_sql, [{**nr, **{"cmci": cmci}}])

  with Timer("\tUpdating coap message IDs", log=log):
    rows = list(row_map_cmci.keys())
    cmcis = list(row_map_cmci.values())

    # Associate each uniquely valued coap tuple in the dataframe with the coap ID from the DB 
    filter_predicates = [(
      (pl.col("coap_type") == r[0])
      & (pl.col("coap_code") == r[1])
      & (pl.col("coap_retransmitted") == r[2])
      ) for r in rows
    ]
    message_patterns_df = message_patterns_df.with_columns([
      pl_replace_predicates_to_values("cmci", filter_predicates, cmcis)
    ])
  
  if log:
    print(f"\t==> Added {len(rows)} unique coap groups {rows} with cmci {cmcis}")
  
  return message_patterns_df

def insert_http(message_patterns_df, unique_http_df, log=False):
  """
  Insert uniquely valued http requests and responses into DB. 
  Note the new hmci ID for each one and reflect the update
  to the dataframe.
  """
  select_sql = """SELECT * FROM {dbname}.http_message""".format(dbname=args.dbname)
  insert_sql = """
    INSERT INTO {dbname}.http_message (hmci, http_request, http_request_method, http_response_code) VALUES
  """.format(dbname=args.dbname)
  found_https = client.execute(select_sql)
  row_map_hmci = { tuple(n[1:]) : n[0] for n in found_https }

  with Timer(f"\tSending http groups to DB", log=log):
    named_rows = unique_http_df.to_dicts()
    for nr in named_rows:
      row = tuple(nr.values())
      if row not in row_map_hmci:
        hmci = generate_next_unique_id(set(row_map_hmci.values()))
        row_map_hmci[row] = hmci
        client.execute(insert_sql, [{**nr, **{"hmci": hmci}}])

  # Update the hmcis for columns with matching values
  with Timer(f"\tUpdating http message IDs", log=log):
    rows = list(row_map_hmci.keys())
    hmcis = list(row_map_hmci.values())

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
        & (pl.col("http_request_method") == r[1])
        & (pl.col("hmci") == -1) # Only change unset hmci.
      for r in rows
    ]
    hmci_update_response_predicates = [
      (pl.col("message_protocol") == "http")
        & (pl.col("http_request") == False)
        & (pl.col("http_response_code") == r[2])
        & (pl.col("hmci") == -1) # Only change unset hmci.
      for r in rows
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
    print(f"\t==> Added {len(rows)} unique https groups {rows} with hmci {hmcis}")

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
  protocol_message_id_name = f"{protocol[0]}mci"
  protocol_message = f"{protocol}_message"
  select_sql = """
    SELECT * FROM {dbname}.message
  """.format(dbname=args.dbname)
  insert_sql = """
    INSERT INTO {dbname}.message (message_id, size_bytes, src_id, dst_id, {protocol_message}) VALUES
  """.format(dbname=args.dbname, protocol_message=protocol_message)

  assert protocol_message_id_name in {"cmci", "hmci"}
  assert protocol_message in {"coap_message", "http_message"}

  found_messages = client.execute(select_sql)
  row_map_message_id = dict()
  for n in found_messages:
    message_id, size_bytes, src_id, dst_id, http_message, coap_message = n
    if protocol == "coap":
      row = (size_bytes, src_id, dst_id, coap_message)
    else:
      row = (size_bytes, src_id, dst_id, http_message)
    row_map_message_id[row] = message_id

  # row_map_message_id = { tuple(n[1:]) : n[0] for n in found_messages }

  with Timer(f"\tFiltering dataframe for uniquely valued message-{protocol} groups", log=log):
    message_df = (
      message_patterns_df
      .filter(
        (pl.col("message_protocol") == protocol)
        & (pl.col(protocol_message_id_name) != -1)
      )
      .select(database_message_pattern_fields + [protocol_message_id_name])
      .unique()
    )
    named_rows = message_df.to_dicts()

  with Timer(f"\tSending message-{protocol} groups to DB", log=log):
    for nr in named_rows:
      row = tuple(nr.values())
      if row not in row_map_message_id:
        message_id = generate_next_unique_id(set(row_map_message_id.values()))
        row_map_message_id[row] = message_id
        # Here, we need to add new keys which match the column
        # names expected in the SQL queries. In cases elsewhere,
        # the names match exactly. Here, they don't.
        v = {**nr, **{"message_id": message_id}}
        v["size_bytes"] = v["message_size"]
        v["src_id"] = v["message_source"]
        v["dst_id"] = v["message_destination"]
        v[protocol_message] = v[protocol_message_id_name]
        client.execute(insert_sql, [v])

  with Timer(f"\tUpdating message-{protocol} IDs", log=log):
    rows = list(row_map_message_id.keys())
    message_ids = list(row_map_message_id.values())

    # Associate each uniquely valued message tuple in the dataframe with the message ID from the DB
    filter_predicates = [(
      (pl.col("message_size") == r[0])
      & (pl.col("message_source") == r[1])
      & (pl.col("message_destination") == r[2])
      & (pl.col(protocol_message_id_name) == r[3])
      ) for r in rows
    ]

    message_patterns_df = message_patterns_df.with_columns([
      pl_replace_predicates_to_values("message_id", filter_predicates, message_ids)
    ])

  if log:
    # The below commented print statement will clutter the 
    # stdout, so only use it when debugging.
    # print(f"\t==> Added {len(rows)} unique message-{protocol} groups {rows} with message_id {message_ids}")
    print(f"\t==> Added {len(rows)} unique message-{protocol} groups")

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
        .to_pandas()
    )

  with Timer("\tCopying to event", log=log):
    sql = """INSERT INTO {dbname}.event VALUES""".format(dbname=args.dbname)
    client.insert_dataframe(sql, event_df, settings={ "max_block_size": 100_000, "use_numpy": True, "columnar": True })

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
  metrics_df = pl.concat(metrics_dfs).collect().to_pandas()

  sql = """INSERT INTO {dbname}.node_metric VALUES""".format(dbname=args.dbname)
  client.insert_dataframe(sql, metrics_df, settings={ "use_numpy": True, "columnar": True })

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
  with Timer("Filtering for unique protocol values", log=log, print_header=log):
    real_df, message_patterns_df, unique_coap_df, unique_http_df = get_unique_protocol_values_df(lazy_df, log=log)

  with Timer("Inserting coap"):
    message_patterns_df = insert_coap(message_patterns_df, unique_coap_df, log=log)

  with Timer("Inserting http"):
    message_patterns_df = insert_http(message_patterns_df, unique_http_df, log=log)

  with Timer("Inserting message-coap"):
    message_patterns_df = _insert_message_for_protocol(message_patterns_df, "coap", log=log)

  with Timer("Inserting message-http"):
    message_patterns_df = _insert_message_for_protocol(message_patterns_df, "http", log=log)

  # At this point, all message IDs should be set.
  assert len(message_patterns_df.filter(pl.col("message_id") == -1)) == 0

  with Timer("Inserting event", log=log, print_header=log):
    insert_event(message_patterns_df, real_df, log=log)

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

  # Insert all the packets captured in the experiments
  with Timer("Inserting messages", print_header=True):
    insert_packets(lazy_df, log=True)

if __name__ == "__main__":
  import doctest
  doctest.testmod()

  try:
    main()
  except Exception as e:
    client.disconnect()
    raise e
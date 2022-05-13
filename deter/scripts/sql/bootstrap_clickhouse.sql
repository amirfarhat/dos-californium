CREATE DATABASE IF NOT EXISTS {dbname} ENGINE = Atomic;

CREATE TABLE IF NOT EXISTS {dbname}.experiment (
  exp_id String NOT NULL,
  attacker_rate String NOT NULL,
  server_connections Int64 NOT NULL,
  max_keep_alive_requests Int64 NOT NULL,
  num_clients Int64 NOT NULL,
  num_trials Int64 NOT NULL,
  origin_server_duration Int64 NOT NULL,
  attacker_duration Int64 NOT NULL,
  receiver_duration Int64 NOT NULL,
  proxy_duration Int64 NOT NULL,
  client_duration Int64 NOT NULL,
  attacker_start_lag_duration Int64 NOT NULL,
  topology_name String NOT NULL,
  num_proxy_connections Int64 NOT NULL,
  request_timeout String NOT NULL,
  max_retries Int64 NOT NULL,
  keep_alive_duration String NOT NULL,
  request_retry_interval String NOT NULL,
  reuse_connections Boolean NOT NULL,
  run_proxy_with_dtls Boolean NOT NULL,
  run_proxy_with_https Boolean NOT NULL,
  run_attacker Boolean NOT NULL,
  PRIMARY KEY(exp_id)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.node (
  node_id Int64 NOT NULL,
  node_name String NOT NULL,
  hardware_type String NOT NULL,
  operating_system String NOT NULL,
  PRIMARY KEY(node_id)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.deployed_node (
  dnid Int64 NOT NULL,
  exp_id String NOT NULL,
  node_id Int64 NOT NULL,
  PRIMARY KEY(dnid)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.message (
  message_id Int64 NOT NULL,
  size_bytes Int64 NOT NULL,
  src_id Int64 NOT NULL,
  dst_id Int64 NOT NULL,
  http_message Nullable(Int64),
  coap_message Nullable(Int64),
  PRIMARY KEY(message_id)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.event (
  observer_id Int64 NOT NULL,
  message_id Int64 NOT NULL,
  observe_timestamp Float64 NOT NULL,
  trial Int64 NOT NULL,
  message_marker Int64 NOT NULL
) ENGINE = MergeTree() ORDER BY (observer_id, message_marker);


CREATE TABLE IF NOT EXISTS {dbname}.coap_message (
  cmci Int64 NOT NULL,
  coap_type String NOT NULL,
  coap_code String NOT NULL,
  coap_retransmitted Boolean NOT NULL,
  PRIMARY KEY(cmci)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.http_message (
  hmci Int64 NOT NULL,
  http_request Boolean NOT NULL,
  http_request_method String NOT NULL,
  http_response_code Int64 NOT NULL,
  PRIMARY KEY(hmci)
) ENGINE = MergeTree();

CREATE TABLE IF NOT EXISTS {dbname}.node_metric (
  observer_id Int64 NOT NULL,
  trial Int64 NOT NULL,
  observation_timestamp Float64 NOT NULL,
  metric_type String NOT NULL,
  metric_value Float64 NOT NULL
) ENGINE = MergeTree() ORDER BY (observer_id, trial);
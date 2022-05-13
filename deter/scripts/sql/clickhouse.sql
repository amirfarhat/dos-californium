SHOW DATABASES;

CREATE DATABASE do_test_db ENGINE = Atomic;

CREATE TABLE IF NOT EXISTS do_test_db.event_csv (
  observer_id UInt32,
  message_id UInt32,
  observe_timestamp Float32,
  trial UInt32,
  message_marker UInt32
) ENGINE = MergeTree()
ORDER BY (observer_id, message_marker)

-- Insert 24M thin event rows in CSV
-- time clickhouse-client --input_format_with_names_use_header=0 --query="INSERT INTO do_test_db.event_csv FORMAT CSV" < event_headerless.csv
-- Time: 6 seconds

CREATE TABLE IF NOT EXISTS do_test_db.results_csv (
  message_timestamp Float64,
  message_source String,
  message_destination String,
  message_protocol String,
  message_size Int64,
  coap_type Nullable(String),
  coap_retransmitted Nullable(Boolean),
  coap_code Nullable(String),
  coap_message_id Nullable(Int64),
  coap_token Nullable(String),
  coap_proxy_uri Nullable(String),
  http_request Nullable(Boolean),
  http_request_method Nullable(String),
  http_request_full_uri Nullable(String),
  http_response_code Nullable(Int64),
  http_response_code_desc Nullable(String),
  http_response_for_uri Nullable(String),
  node_type String,
  message_marker Int64,
  trial Int64,
  exp_id String
) ENGINE = MergeTree()
ORDER BY (exp_id, message_marker)

-- Insert 28M wide result rows in CSV
-- time clickhouse-client --query="INSERT INTO do_test_db.results_csv FORMAT CSV" < large_event.csv
-- Time: 36 seconds

DROP DATABASE IF EXISTS tst;
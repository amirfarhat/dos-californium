import io
import json
import time
import argparse

import psycopg2

import numpy as np
import pandas as pd

from pprint import pprint

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-d', '--dbname', dest='dbname',
                      help='', action='store', type=str)
  parser.add_argument('-p', '--procedurespath', dest='procedurespath',
                      help='', action='store', type=str)

  return parser.parse_args()

def sql_create_tables():
  return """
    CREATE TABLE IF NOT EXISTS "experiment" (
      "exp_id" text PRIMARY KEY NOT NULL,
      "attacker_rate" text NOT NULL,
      "server_connections" int NOT NULL,
      "max_keep_alive_requests" int NOT NULL,
      "num_clients" int NOT NULL,
      "num_trials" int NOT NULL,
      "origin_server_duration" int NOT NULL,
      "attacker_duration" int NOT NULL,
      "receiver_duration" int NOT NULL,
      "proxy_duration" int NOT NULL,
      "client_duration" int NOT NULL,
      "attacker_start_lag_duration" int NOT NULL,
      "topology_name" text NOT NULL,
      "num_proxy_connections" int NOT NULL,
      "request_timeout" text NOT NULL,
      "max_retries" int NOT NULL,
      "keep_alive_duration" text NOT NULL,
      "request_retry_interval" text NOT NULL,
      "reuse_connections" boolean NOT NULL,
      "run_proxy_with_dtls" boolean NOT NULL,
      "run_proxy_with_https" boolean NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "node" (
      "node_id" SERIAL PRIMARY KEY NOT NULL,
      "node_name" text NOT NULL,
      "hardware_type" text NOT NULL,
      "operating_system" text NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "deployed_node" (
      "dnid" SERIAL PRIMARY KEY NOT NULL,
      "exp_id" text NOT NULL,
      "node_id" int NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "message" (
      "message_id" SERIAL PRIMARY KEY NOT NULL,
      "size_bytes" int NOT NULL,
      "src_id" int NOT NULL,
      "dst_id" int NOT NULL,
      "http_message" int,
      "coap_message" int
    );

    CREATE TABLE IF NOT EXISTS "event" (
      "observer_id" int NOT NULL,
      "message_id" int NOT NULL,
      "observe_timestamp" float NOT NULL,
      "trial" int NOT NULL,
      "message_marker" int NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "coap_message" (
      "cmci" SERIAL PRIMARY KEY NOT NULL,
      "coap_type" text NOT NULL,
      "coap_code" text NOT NULL,
      "coap_retransmitted" boolean NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "http_message" (
      "hmci" SERIAL PRIMARY KEY NOT NULL,
      "http_request" boolean NOT NULL,
      "http_request_method" text NOT NULL,
      "http_response_code" int NOT NULL
    );

    CREATE TABLE IF NOT EXISTS "node_metric" (
      "observer_id" int NOT NULL,
      "trial" int NOT NULL,
      "observation_timestamp" int NOT NULL,
      "metric_type" text NOT NULL,
      "metric_value" float NOT NULL
    );
  """

def sql_inject_foreign_keys():
  return """
    ALTER TABLE "deployed_node" ADD FOREIGN KEY ("exp_id") REFERENCES "experiment" ("exp_id");
    ALTER TABLE "deployed_node" ADD FOREIGN KEY ("node_id") REFERENCES "node" ("node_id");
    ALTER TABLE "message" ADD FOREIGN KEY ("src_id") REFERENCES "node" ("node_id");
    ALTER TABLE "message" ADD FOREIGN KEY ("dst_id") REFERENCES "node" ("node_id");
    ALTER TABLE "message" ADD FOREIGN KEY ("http_message") REFERENCES "http_message" ("hmci");
    ALTER TABLE "message" ADD FOREIGN KEY ("coap_message") REFERENCES "coap_message" ("cmci");
    ALTER TABLE "node_metric" ADD FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");
  """

def sql_inject_named_constraints():
  return """
    DO $$
      BEGIN
        IF NOT EXISTS (SELECT conname FROM pg_constraint WHERE conname = 'event_observer_id_fkey') THEN
          ALTER TABLE "event" ADD CONSTRAINT event_observer_id_fkey FOREIGN KEY ("observer_id") REFERENCES "deployed_node" ("dnid");
        END IF;

        IF NOT EXISTS (SELECT conname FROM pg_constraint WHERE conname = 'event_message_id_fkey') THEN
          ALTER TABLE "event" ADD CONSTRAINT event_message_id_fkey FOREIGN KEY ("message_id") REFERENCES "message" ("message_id");
        END IF;
      END;
    $$    
  """

def create_tables_commands():
  return [
    sql_create_tables(),
    sql_inject_foreign_keys(),
    sql_inject_named_constraints(),
  ]

args = parse_args()

def main():
  # Create tables and utilities on the database for insertion

  # Set up connection and cursor
  con = psycopg2.connect(user="postgres", password="coap", dbname=args.dbname)
  cur = con.cursor()

  # Create tables
  for c in create_tables_commands():
    cur.execute(c)
  con.commit()

  # Read functions and procedures then send to DB
  cur.execute(open(args.procedurespath, "r").read())
  con.commit()

  # Close connection to database
  print("Created tables, functions, and stored procedures")
  con.close()

if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
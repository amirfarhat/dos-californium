import argparse
from clickhouse_driver import Client

from deter_utils import Timer

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-d', '--dbname', dest='dbname',
                      help='', action='store', type=str)
  parser.add_argument('-s', '--sqlfile', dest='sqlfile',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

def main():
  client = Client(host='localhost')

  # Read and format bootstrapping SQL statements.
  with open(args.sqlfile, "r") as f:
    bootstrap_sql_statements = (
      f.read()
      .format(dbname=args.dbname)
      .split(";")
    )
    if bootstrap_sql_statements[-1] == "":
      bootstrap_sql_statements.pop()
  
  # Execute SQL statements on ClickHouse server.
  for sql in bootstrap_sql_statements:
    client.execute(sql)
  
  client.disconnect()
  
if __name__ == "__main__":
  import doctest
  doctest.testmod()
  main()
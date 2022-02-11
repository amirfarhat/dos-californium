import argparse

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-s', '--src', dest='src',
                      help='', action='store', type=str)
  parser.add_argument('-d', '--dst', dest='dst',
                      help='', action='store', type=str)
  parser.add_argument('-i', '--ipsfile', dest='ipsfile',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

# Print the corresponding ip address for `dst`
with open(args.ipsfile, "r") as f:
  for line in f:
    if line.startswith(args.dst):
      parts = line.split()
      _, dst_ip = parts
      print(dst_ip)
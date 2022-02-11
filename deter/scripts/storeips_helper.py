import argparse

def parse_args():
  parser = argparse.ArgumentParser(description = '')

  parser.add_argument('-i', '--infile', dest='infile',
                      help='', action='store', type=str)
  parser.add_argument('-o', '--outfile', dest='outfile',
                      help='', action='store', type=str)

  return parser.parse_args()

args = parse_args()

NS_IP_PREFIX = "tb-set-ip $"

# Read ip lines that look like "HOSTNAME INTERNAL_IP"
ip_lines = []
with open(args.infile, "r") as f:
  for L in f:
    if L.startswith(NS_IP_PREFIX):
      dollar_host, ip = L.split()[1:]
      host = dollar_host.lstrip("$")
      ipl = host + " " + ip
      ip_lines.append(ipl)

# Write IP lines out, one per line
with open(args.outfile, "w") as f:
  f.writelines("\n".join(ip_lines))
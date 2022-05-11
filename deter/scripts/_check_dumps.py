import json
from pprint import pprint

# File looks smth like this:
# process_cloud_proxy_and_500mbpsattacker_withattacker.log:server_dump.pcap
# process_cloud_proxy_and_500mbpsattacker_withattacker.log-real   2m15.496s
# process_cloud_proxy_and_500mbpsattacker_withattacker.log:attacker_dump.pcap
# process_cloud_proxy_and_500mbpsattacker_withattacker.log-real   3m0.424s

d = dict()
with open("/home/ubuntu/dump_times.txt", "r") as f:
  cur_exp = None
  dump = None
  for L in f:
    L = L.strip()
    if ":" in L:
      parts = L.split(":")
      exp = parts[0]
      exp = exp.rstrip(".log")
      dump = parts[1]
      if exp not in d:
        d[exp] = dict()
      if dump not in d[exp]:
        d[exp][dump] = list()
    else:
      parts = L.split("-real")
      exp = parts[0]
      exp = exp.rstrip(".log")
      s = parts[1]
      mins = int(s[:s.index("m")])
      secs = float(s[s.index("m") + 1 : s.index("s")])
      time = mins*60 + secs
      assert time > 0
      d[exp][dump].append(time)

o = dict()
for exp, dd in d.items():
  o[exp] = dict()
  for dump, times in dd.items():
    if len(times) > 0:
      avg_time = sum(times) / len(times)
      o[exp][dump] = round(avg_time)
 
assert len(d) == len(o) == 12

pprint(o)

with open("/home/ubuntu/dump_times.json", "w") as f:
  json.dump(o, f)
import json
import glob

for f in glob.glob("../accounts/*.json"):
    account = json.load(open(f))
    if not account.get("notes"):
        account["notes"] = []
    with open(f, 'w') as nf:
        nf.write(json.dumps(account, sort_keys=True, indent=4, separators=(',', ': ')))

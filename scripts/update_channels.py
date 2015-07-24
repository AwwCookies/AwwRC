import json
import glob

for f in glob.glob("../channels/*.json"):
    account = json.load(open(f))
    if not account.get("public_notes"):
        account["public_notes"] = []
    with open(f, 'w') as nf:
        nf.write(json.dumps(account, sort_keys=True, indent=4, separators=(',', ': ')))

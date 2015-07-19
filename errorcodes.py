codes = {
    "nick already registered": "001",
    "invalid nick password": "002",
    "invalid channel/nick": "003",
    "invalid account name": "004",
    "nick in use": "005",
    "nick excecced limt": "006",
    "not an oper": "007",
    "not in channel": "008",
}

def get(name):
    if name.lower() in codes:
        return codes[name.lower()]

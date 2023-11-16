import json

with open('botinfo.json', 'r') as f:
    botinfo_dict = json.loads(f.read())

version = botinfo_dict["version"]
maintainer = botinfo_dict["maintainer"]

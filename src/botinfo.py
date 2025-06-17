import json

from src.utils.dir_utils import DirUtils

dir_utils = DirUtils()

with open(dir_utils.main_dir.joinpath("botinfo.json"), 'r') as f:
    botinfo_dict = json.loads(f.read())

version = botinfo_dict["version"]
maintainer = botinfo_dict["maintainer"]

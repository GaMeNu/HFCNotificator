import json

from utils.dir_utils import DirUtils

dir_utils = DirUtils()

BOTINFO_PATH = dir_utils.project_dir.joinpath("botinfo.json")


def get_botinfo_data():
    with open(BOTINFO_PATH, 'r') as f:
        return json.load(f)


class _Botinfo:
    def __init__(self):
        self.version: str = ""
        self.maintainer: str = ""

        self.reload()

    def reload(self):
        with open(BOTINFO_PATH, 'r') as f:
            botinfo_dict = json.loads(f.read())

        self.version = botinfo_dict["version"]
        self.maintainer = botinfo_dict["maintainer"]


botinfo = _Botinfo()

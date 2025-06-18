import json

from src.utils.dir_utils import DirUtils

dir_utils = DirUtils()


class _Botinfo:
    def __init__(self):
        self.version: str = ""
        self.maintainer: str = ""

        self.reload()

    def reload(self):
        with open(dir_utils.project_dir.joinpath("botinfo.json"), 'r') as f:
            botinfo_dict = json.loads(f.read())

        self.version = botinfo_dict["version"]
        self.maintainer = botinfo_dict["maintainer"]


botinfo = _Botinfo()

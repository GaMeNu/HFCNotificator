import os
from pathlib import Path

_project_root = Path(__file__).joinpath("../../..").resolve()


class DirUtils:

    @staticmethod
    def ensure_working_directory():
        os.chdir(_project_root)

    @property
    def main_dir(self):
        return _project_root

    @property
    def botdata_dir(self):
        path = _project_root.joinpath("botdata")
        if not path.is_dir():
            path.mkdir()
        return path

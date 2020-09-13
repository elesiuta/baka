# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# https://github.com/elesiuta/baka

import argparse
import json
import os
import subprocess
import sys

from binaryornot.check import is_binary


def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Baka Admin Kludge Assistant",
                                     usage="%(prog)s [--dry-run] <argument>")
    maingrp = parser.add_mutually_exclusive_group()
    maingrp.add_argument("--init", dest="init", action="store_true",
                         help="init git repo in system root")
    maingrp.add_argument("--add", dest="add", action="store_true",
                         help="scan for files and add to repo")
    maingrp.add_argument("--commit", dest="commit", action="store_true",
                         help="add and commit your changes to tracked files")
    maingrp.add_argument("--git", dest="git", action="store", metavar="args", nargs=argparse.REMAINDER,
                         help="wrapper to run git command with args (TODO)")
    maingrp.add_argument("--upgrade", dest="upgrade", action="store_true",
                         help="upgrade packages on system and commit changes")
    maingrp.add_argument("--verify", dest="verify", action="store_true",
                         help="verify all packages on system")
    maingrp.add_argument("--apply", dest="apply", action="store_true",
                         help="apply patches to system (TODO)")
    maingrp.add_argument("--export", dest="export", action="store_true",
                         help="export patches of diffs against base system (TODO)")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true",
                        help="print system commands instead of executing them")
    return parser


def is_possible_config(file_path: str) -> bool:
    # https://stackoverflow.com/questions/898669/how-can-i-detect-if-a-file-is-binary-non-text-in-python
    # https://docs.python.org/3.6/library/mimetypes.html
    # https://github.com/ahupp/python-magic
    # https://pypi.org/project/binaryornot/
    return not is_binary(file_path)


def baka_init(dry_run: bool) -> int:
    cmd = ["git", "init"]
    if dry_run:
        print(" ".join(cmd))
        return 0
    else:
        return subprocess.run(cmd).returncode


def baka_add(dry_run: bool, config: "Config"):
    # init cmd runner
    if dry_run:
        run = lambda cmd: print(" ".join(cmd))
    else:
        run = lambda cmd: subprocess.run(cmd)
    # check every file on system that is not ignored
    for dir_path, subdir_list, file_list in os.walk("/", followlinks=False):
        # ignore paths and folders
        if dir_path in config.ignored_paths:
            subdir_list.clear()
            continue
        for subdir in subdir_list:
            if subdir in config.ignored_folders:
                subdir_list.remove(subdir)
        # check if file is possible config and add to git
        for file_name in file_list:
            file_path = os.path.join(dir_path, file_name)
            if is_possible_config(file_path):
                run(["git", "add", file_path])
    # commit changes
    run(["git", "commit", "-m", "baka add"])


def baka_commit(dry_run: bool):
    cmds = [
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka commit admin changes"]
    ]
    for cmd in cmds:
        if dry_run:
            print(" ".join(cmd))
        else:
            subprocess.run(cmd).returncode


def baka_git():
    # TODO
    # unnecessary until logging is implimented, even then?
    pass


def baka_upgrade(dry_run: bool, config: "Config"):
    cmds = [
        config.cmd_upgrade,
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka upgrade"]
    ]
    for cmd in cmds:
        if dry_run:
            print(" ".join(cmd))
        else:
            subprocess.run(cmd).returncode


def baka_verify(dry_run: bool, config: "Config"):
    cmd = config.cmd_verify_packages
    if dry_run:
        print(" ".join(cmd))
    else:
        subprocess.run(cmd).returncode


def baka_apply():
    # TODO
    # either take path as argument or use .baka/patches or something
    pass


def baka_export():
    # TODO
    # either take path as argument or use .baka/patches or something
    pass


class Config:
    def __init__(self):
        # read config file
        config_path = os.path.join(os.path.expanduser("~"), ".baka", "config.json")
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8", errors="surrogateescape") as json_file:
                config = json.load(json_file)
        # default config
        self.cmd_upgrade = ["apt", "update", "&&", "apt", "upgrade"]
        self.cmd_verify_packages = ["debsums", "-ac"]
        self.ignored_folders = [
            ".git"
        ]
        self.ignored_paths = [
            "/proc",
            "/media",
            "/var/log",
            "/var/tmp",
            "/tmp"
        ]
        # load config
        for key in config:
            if config[key] is not None and hasattr(self, key):
                self.__setattr__(key, config[key])
        # normalize paths
        for i in range(len(self.ignored_paths)):
            self.ignored_paths[i] = os.path.normpath(self.ignored_paths[i])
        # write config file if does not exist
        if not os.path.exists(config_path):
            if not os.path.isdir(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path))
            try:
                with open(config_path, "w", encoding="utf-8", errors="surrogateescape") as json_file:
                    json.dump(vars(self), json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
            except Exception:
                print("Error: Could not write config file to " + config_path)


class Log:
    def __init__(self):
        # TODO
        pass


def main() -> int:
    # parse arguments
    parser = init_parser()
    args = parser.parse_args()
    # check for root
    if not sys.platform.startswith("linux") or os.getuid() != 0:
        raise Exception("Error: This programs needs to be run as root, exiting")
    # init config
    config = Config()
    # change cwd to /
    os.chdir("/")
    # execute function
    if args.init:
        return baka_init(args.dry_run)
    elif args.add:
        baka_add(args.dry_run, config)
    elif args.commit:
        baka_commit(args.dry_run)
    elif args.git:
        baka_git()
    elif args.upgrade:
        baka_upgrade(args.dry_run, config)
    elif args.verify:
        baka_verify(args.dry_run, config)
    elif args.apply:
        baka_apply()
    elif args.export:
        baka_export()
    return 0


if __name__ == "__main__":
    sys.exit(main())

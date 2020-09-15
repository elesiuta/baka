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
import shlex
import subprocess
import sys


def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Baka Admin's Kludge Assistant",
                                     usage="%(prog)s [--dry-run] <argument>")
    maingrp = parser.add_mutually_exclusive_group()
    maingrp.add_argument("--init", dest="init", action="store_true",
                         help="init git repo in system root")
    maingrp.add_argument("--add", dest="add", action="store_true",
                         help="scan for new files to add to repo and commit")
    maingrp.add_argument("--commit", dest="commit", type=str, metavar="msg",
                         help="git add -u and commit your changes to tracked files")
    maingrp.add_argument("--git", dest="git", nargs=argparse.REMAINDER,
                         help="wrapper to run git command with args")
    maingrp.add_argument("--install", dest="install", nargs=argparse.REMAINDER,
                         help="install package(s) and commit changes")
    maingrp.add_argument("--remove", dest="remove", nargs=argparse.REMAINDER, type=list, default=None,
                         help="remove package(s) and commit changes")
    maingrp.add_argument("--upgrade", dest="upgrade", action="store_true",
                         help="upgrade packages on system and commit changes")
    maingrp.add_argument("--verify", dest="verify", action="store_true",
                         help="verify all packages on system")
    maingrp.add_argument("--diff", dest="diff", action="store_true",
                         help="show git diff --stat")
    maingrp.add_argument("--log", dest="log", action="store_true",
                         help="show pretty git log")
    maingrp.add_argument("--apply", dest="apply", action="store_true",
                         help="apply patches to system (TODO)")
    maingrp.add_argument("--export", dest="export", action="store_true",
                         help="export patches of diffs against base system (TODO)")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true",
                        help="print system commands instead of executing them")
    return parser


def baka_init(dry_run: bool) -> int:
    cmd = [
        "git", "init", "&&",
        "git", "config", "core.worktree", "/", "&&",
        "git", "config", "user.name", "baka admin", "&&",
        "git", "config", "user.email", "baka@" + os.uname().nodename
    ]
    if dry_run:
        print(shlex.join(["bash", "-c", " ".join(cmd)]))
        return 0
    else:
        return subprocess.run(["bash", "-c", " ".join(cmd)]).returncode


def baka_add(dry_run: bool, config: "Config"):
    cmds = [["git", "add", "--ignore-errors", path] for path in config.tracked_paths] + [["git", "commit", "-m", "baka add"]]
    for cmd in cmds:
        if dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)


def baka_commit(dry_run: bool, msg: str):
    cmds = [
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka commit " + msg]
    ]
    for cmd in cmds:
        if dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)


def baka_git(dry_run: bool, args: list):
    cmd = ["git"] + args
    if dry_run:
        print(shlex.join(cmd))
        return 0
    else:
        return subprocess.run(cmd).returncode


def baka_install(dry_run: bool, config: "Config", packages: list):
    cmds = [
        config.cmd_install + packages,
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka install"]
    ]
    for cmd in cmds:
        if dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)


def baka_remove(dry_run: bool, config: "Config", packages: list):
    cmds = [
        config.cmd_remove + packages,
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka remove"]
    ]
    for cmd in cmds:
        if dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)


def baka_upgrade(dry_run: bool, config: "Config"):
    cmds = [
        config.cmd_upgrade,
        ["git", "add", "-u"],
        ["git", "commit", "-m", "baka upgrade"]
    ]
    for cmd in cmds:
        if dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)


def baka_verify(dry_run: bool, config: "Config"):
    cmd = config.cmd_verify_packages
    if dry_run:
        print(shlex.join(cmd))
    else:
        subprocess.run(cmd)


def baka_diff(dry_run: bool):
    cmd = ["git", "diff", "--stat"]
    if dry_run:
        print(shlex.join(cmd))
    else:
        subprocess.run(cmd)


def baka_log(dry_run: bool):
    cmd = [
        "git", "log", "--abbrev-commit", "--all", "--decorate", "--graph", "--stat",
        "--format=format:%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(bold yellow)%d%C(reset)%n%C(bold white)%s%C(reset)%C(dim white) - %an%C(reset)"
    ]
    if dry_run:
        print(shlex.join(cmd))
    else:
        subprocess.run(cmd)


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
        config_path = os.path.expanduser("~/.baka/config.json")
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8", errors="surrogateescape") as json_file:
                config = json.load(json_file)
        # default config
        self.cmd_install = ["sudo", "apt", "install"]
        self.cmd_remove = ["sudo", "apt", "autoremove", "--purge"]
        self.cmd_upgrade = ["bash", "-c", "sudo apt update && sudo apt upgrade"]
        self.cmd_verify_packages = ["sudo", "debsums", "-ac"]
        self.tracked_paths = [
            "/etc/.",
            os.path.expanduser("~/.config/."),
            os.path.expanduser("~/.local/share/.")
        ]
        # load config
        for key in config:
            if config[key] is not None and hasattr(self, key):
                self.__setattr__(key, config[key])
        # write config file if does not exist
        if not os.path.exists(config_path):
            if not os.path.isdir(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path))
            try:
                with open(config_path, "w", encoding="utf-8", errors="surrogateescape") as json_file:
                    json.dump(vars(self), json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
            except Exception:
                print("Error: Could not write config file to " + config_path)


def main() -> int:
    # parse arguments
    parser = init_parser()
    args = parser.parse_args()
    # init config
    config = Config()
    # change cwd to repo folder
    os.chdir(os.path.expanduser("~/.baka"))
    # execute function
    if args.init:
        return baka_init(args.dry_run)
    elif args.add:
        baka_add(args.dry_run, config)
    elif args.commit:
        baka_commit(args.dry_run, args.commit)
    elif args.git:
        baka_git(args.dry_run, args.git)
    elif args.install:
        baka_install(args.dry_run, config, args.install)
    elif args.remove is not None:
        baka_remove(args.dry_run, config, args.remove)
    elif args.upgrade:
        baka_upgrade(args.dry_run, config)
    elif args.verify:
        baka_verify(args.dry_run, config)
    elif args.diff:
        baka_diff(args.dry_run)
    elif args.log:
        baka_log(args.dry_run)
    elif args.apply:
        baka_apply()
    elif args.export:
        baka_export()
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
                         help="open config, init git repo, add files then commit")
    maingrp.add_argument("--commit", dest="commit", type=str, metavar="msg",
                         help="git add -u and commit your changes to tracked files")
    maingrp.add_argument("--install", dest="install", nargs=argparse.REMAINDER,
                         help="install package(s) and commit changes")
    maingrp.add_argument("--remove", dest="remove", nargs=argparse.REMAINDER, default=None,
                         help="remove package(s) and commit changes")
    maingrp.add_argument("--upgrade", dest="upgrade", action="store_true",
                         help="upgrade packages on system and commit changes")
    maingrp.add_argument("--verify", dest="verify", action="store_true",
                         help="verify all packages on system")
    maingrp.add_argument("--diff", dest="diff", action="store_true",
                         help="show git diff --stat")
    maingrp.add_argument("--log", dest="log", action="store_true",
                         help="show pretty git log")
    maingrp.add_argument("--git", dest="git", nargs=argparse.REMAINDER,
                         help="wrapper to run git command with args")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true",
                        help="print system commands instead of executing them")
    return parser


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
    # select commands
    if args.init:
        # option to edit then reload config
        _ = input("Press enter to open your config file with nano")
        if args.dry_run:
            print(shlex.join(["nano", os.path.expanduser("~/.baka/config.json")]))
        else:
            subprocess.run(["nano", os.path.expanduser("~/.baka/config.json")])
        config = Config()
        # git commands
        cmds = [
            ["git", "init"],
            ["git", "config", "core.worktree", "/"],
            ["git", "config", "user.name", "baka admin"],
            ["git", "config", "user.email", "baka@" + os.uname().nodename],
            ["bash", "-c", "echo '*~\n*.dpkg-new\n*.dpkg-old\n' | cat > .gitignore"],
            ["bash", "-c", "read -p 'Press enter to add files to repository'"]
        ]
        cmds += [["git", "add", "--ignore-errors", path] for path in config.tracked_paths]
        cmds += [["git", "commit", "-m", "baka initial commit"]]
    elif args.commit:
        cmds = [
            ["git", "add", "-u"],
            ["git", "commit", "-m", "baka commit " + args.commit]
        ]
    elif args.install:
        cmds = [["git", "add", "--ignore-errors", path] for path in config.tracked_paths]
        cmds += [["git", "commit", "-m", "baka pre-install"]]
        cmds += [config.cmd_install + args.install]
        cmds += [["git", "add", "--ignore-errors", path] for path in config.tracked_paths]
        cmds += [["git", "commit", "-m", "baka install " + " ".join(args.install)]]
    elif args.remove is not None:
        cmds = [
            ["git", "add", "-u"],
            ["git", "commit", "-m", "baka pre-remove"],
            config.cmd_remove + args.remove,
            ["git", "add", "-u"],
            ["git", "commit", "-m", "baka remove"]
        ]
    elif args.upgrade:
        cmds = [
            ["git", "add", "-u"],
            ["git", "commit", "-m", "baka pre-upgrade"],
            config.cmd_upgrade,
            ["git", "add", "-u"],
            ["git", "commit", "-m", "baka upgrade"]
        ]
    elif args.verify:
        cmds = [config.cmd_verify_packages]
    elif args.diff:
        cmds = [["git", "diff", "--stat"]]
    elif args.log:
        cmds = [[
            "git", "log", "--abbrev-commit", "--all", "--decorate", "--graph", "--stat",
            "--format=format:%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(bold yellow)%d%C(reset)%n%C(bold white)%s%C(reset)%C(dim white) - %an%C(reset)"
        ]]
    elif args.git:
        cmds = [["git"] + args.git]
    # execute commands
    for cmd in cmds:
        if args.dry_run:
            print(shlex.join(cmd))
        else:
            subprocess.run(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3

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
import datetime
import email
import email.mime.text
import hashlib
import json
import os
import shlex
import shutil
import smtplib
import socket
import subprocess
import sys
import time
import typing

__version__: typing.Final[str] = "0.8.7"
BASE_PATH: typing.Final[str] = os.path.expanduser("~/.baka")


def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="the stupid configuration tracker using the stupid content tracker",
                                     usage="%(prog)s [--dry-run] <argument>")
    parser.add_argument("--version", action="version", version=__version__)
    maingrp = parser.add_mutually_exclusive_group()
    maingrp.add_argument("--_hash_and_copy_files", dest="hash_and_copy_files", action="store_true",
                         help=argparse.SUPPRESS)
    maingrp.add_argument("--init", dest="init", action="store_true",
                         help="open config, init git repo, add files then commit")
    maingrp.add_argument("--commit", dest="commit", type=str, metavar="msg",
                         help="git add and commit your changes to tracked files")
    maingrp.add_argument("--push", dest="push", action="store_true",
                         help="git push (caution, ensure remote is private)")
    maingrp.add_argument("--pull", dest="pull", action="store_true",
                         help="git pull (does not restore files over system)")
    maingrp.add_argument("--untrack", dest="untrack", nargs=argparse.REMAINDER,
                         help="untrack path(s) from git")
    maingrp.add_argument("--install", dest="install", nargs=argparse.REMAINDER,
                         help="install package(s) and commit changes")
    maingrp.add_argument("--remove", dest="remove", nargs=argparse.REMAINDER, default=None,
                         help="remove package(s) and commit changes")
    maingrp.add_argument("--upgrade", dest="upgrade", action="store_true",
                         help="upgrade packages on system and commit changes")
    maingrp.add_argument("--docker", dest="docker", nargs=argparse.REMAINDER,
                         help="usage: --docker <up|down|pull> <all|names...>")
    maingrp.add_argument("--podman", dest="podman", nargs=argparse.REMAINDER,
                         help="usage: --podman <up|down|pull> <all|names...>")
    maingrp.add_argument("--file", dest="file", nargs=argparse.REMAINDER,
                         help="usage: --file <save|restore> <all|names...>")
    maingrp.add_argument("--job", dest="job", type=str, metavar="name",
                         help="run commands for job with name (modifiers: -i, -e, -y)")
    maingrp.add_argument("--list", dest="list", action="store_true",
                         help="show list of jobs")
    maingrp.add_argument("--sysck", dest="system_checks", action="store_true",
                         help="run commands for system checks and commits output")
    maingrp.add_argument("--scan", dest="system_scans", action="store_true",
                         help="run commands for scanning system, prints and commits output")
    maingrp.add_argument("--diff", dest="diff", action="store_true",
                         help="show git diff --color-words")
    maingrp.add_argument("--log", dest="log", action="store_true",
                         help="show pretty git log")
    maingrp.add_argument("--show", dest="show", action="store_true",
                         help="show most recent commit")
    parser.add_argument("-i", dest="interactive", action="store_true",
                        help="force job to run in interactive mode")
    parser.add_argument("-e", dest="error_interactive", action="store_true",
                        help="job interactive mode after error (non zero exit code)")
    parser.add_argument("-y", dest="yes", action="store_true",
                        help="supplies 'y' to job commands, similar to yes | job")
    parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true",
                        help="print commands instead of executing them")
    return parser


class Config:
    def __init__(self):
        # default config
        self.cmd_install = ["sudo", "apt", "install"]
        self.cmd_remove = ["sudo", "apt", "autoremove", "--purge"]
        self.cmd_upgrade = ["bash", "-c", "sudo apt update && sudo apt dist-upgrade"]
        self.email = {
            "cc": None,
            "from": "myemail@domain.com",
            "html": True,
            "smtp_server": "smtp.domain.com",
            "smtp_port": 587,
            "smtp_username": "username",
            "smtp_password": "password"
        }
        self.files = {
            "example_file_a": {
                "src": "path/to/file",
            },
            "example_file_b": {
                "cmd": ["echo", "command to generate file"],
            }
        }
        self.jobs = {
            "example_job_name": {
                "commands": [
                    ["echo", "hello world"],
                    ["echo", "task completed"]
                ],
                "email": {
                    "to": "email@domain.com or null",
                    "subject": "example subject"
                },
                "exit_non_zero": False,
                "interactive": False,
                "shlex_split": False,
                "verbosity": "one of: debug (default if null), info, error, silent",
                "write": "./jobs/example job %Y-%m-%d %H:%M.log (supports strftime format codes) or null"
            }
        }
        self.system_checks = {
            "ip_rules_v4": "sudo cat /etc/iptables/rules.v4",
            "ip_rules_v6": "sudo cat /etc/iptables/rules.v6",
            "packages": "sudo apt list --installed",
            "pip": "pip3 list --user",
            "SMART-sda": "sudo smartctl -a /dev/sda",
            "SMART-sdb": "sudo smartctl -a /dev/sdb",
            "ss": "sudo ss -lntu | awk 'NR<2{print $0;next}{print $0| \"sort -k5\"}'",
            "ufw": "sudo ufw status verbose",
        }
        self.system_scans = {
            "aide": "sudo aide.wrapper --update",
            "chkrootkit": "sudo chkrootkit",
            "debsums": "sudo debsums -ac",
            "lynis": "sudo lynis audit system",
            "rkhunter": "sudo rkhunter --check --skip-keypress",
        }
        self.tracked_paths = {k: v for k, v in {
            "/etc": {"max_size": 128000},
            os.path.expanduser("~"): {"max_depth": 2, "max_size": 128000, "path_starts_with": ".", "exclude": [".ssh"]},
            os.path.expanduser("~/.config"): {"max_depth": 2, "max_size": 128000, "exclude": ["log", "Local State", "TransportSecurity"]},
            os.path.expanduser("~/.kde/share"): {"max_depth": 3, "max_size": 128000},
            os.path.expanduser("~/.local/share"): {"max_depth": 3, "max_size": 128000, "exclude": ["application_state"]},
        }.items() if os.path.exists(k)}
        # read config file and set values, or write if it does not exist
        config_path = os.path.join(BASE_PATH, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8", errors="surrogateescape") as json_file:
                # remove comments from json file
                raw_text = json_file.readlines()
                for i in reversed(range(len(raw_text))):
                    if raw_text[i].lstrip().startswith("#"):
                        _ = raw_text.pop(i)
                config = json.loads("".join(raw_text))
            for key in config:
                if config[key] is not None and hasattr(self, key):
                    self.__setattr__(key, config[key])
            for tracked_path in self.tracked_paths:
                assert os.path.isabs(tracked_path)
        else:
            if not os.path.isdir(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path))
            with open(config_path, "w", encoding="utf-8", errors="surrogateescape") as json_file:
                json.dump(vars(self), json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
        # get the system hostname, usually /etc/hostname but can override with .baka/hostname (not in config.json or committed)
        if os.path.exists(os.path.join(BASE_PATH, "hostname")):
            with open(os.path.join(BASE_PATH, "hostname"), "r") as f:
                self.hostname = f.read().strip()
        else:
            self.hostname = socket.gethostname()


def os_stat_tracked_files(config: "Config") -> None:
    stat = {}
    for tracked_path in list(config.tracked_paths):
        if os.path.isdir(tracked_path):
            for root, dirs, files in os.walk(BASE_PATH + tracked_path, followlinks=False):
                for file_or_folder in files + dirs:
                    file_path = "/" + os.path.relpath(os.path.join(root, file_or_folder), BASE_PATH)
                    if os.path.exists(file_path):
                        file_stat = os.stat(file_path)
                        stat[file_path] = {"mode": oct(file_stat.st_mode), "uid": file_stat.st_uid, "gid": file_stat.st_gid}
        elif os.path.isfile(tracked_path):
            file_path = tracked_path
            if os.path.exists(BASE_PATH + file_path):
                file_stat = os.stat(file_path)
                stat[file_path] = {"mode": oct(file_stat.st_mode), "uid": file_stat.st_uid, "gid": file_stat.st_gid}
    with open(os.path.join(BASE_PATH, "stat.json"), "w", encoding="utf-8", errors="surrogateescape") as json_file:
        json.dump(stat, json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)


def hash_and_copy_files(config: "Config") -> None:
    # also keep track of hashes, need to read the files anyways and can save on writes
    new_hashes = {}
    old_hashes = {}
    omitted = {}
    if os.path.exists(os.path.join(BASE_PATH, "sha256.json")):
        with open(os.path.join(BASE_PATH, "sha256.json"), "r", encoding="utf-8", errors="surrogateescape") as json_file:
            old_hashes = json.load(json_file)
    for tracked_path in config.tracked_paths:
        # set default values (no conditions) and load conditions for which files to track/copy
        conditions = {"exclude": [], "include": [], "file_starts_with": "", "path_starts_with": "", "max_depth": None, "max_size": None, "test_utf_readable": True}
        for condition in config.tracked_paths[tracked_path]:
            conditions[condition] = config.tracked_paths[tracked_path][condition]
        for root, dirs, files in os.walk(tracked_path, followlinks=False):
            # check conditions
            relpath = os.path.relpath(root, tracked_path)
            # ~/.baka is a subfolder of the path to track
            if root.startswith(BASE_PATH):
                del dirs
                continue
            if conditions["path_starts_with"] and not relpath.startswith(conditions["path_starts_with"]):
                omitted[root] = "path_starts_with"
                del dirs
                continue
            if conditions["max_depth"] and relpath.count("/") > conditions["max_depth"]:
                omitted[root] = "max_depth"
                del dirs
                continue
            for file in files:
                file_path = os.path.join(root, file)
                file_relpath = os.path.relpath(file_path, tracked_path)
                if conditions["exclude"] and any(e in file_relpath for e in conditions["exclude"]):
                    omitted[file_path] = "exclude"
                    continue
                if conditions["include"] and not any(i in file_relpath for i in conditions["include"]):
                    omitted[file_path] = "include"
                    continue
                if conditions["file_starts_with"] and not file.startswith(conditions["file_starts_with"]):
                    omitted[file_path] = "file_starts_with"
                    continue
                if conditions["path_starts_with"] and not file_relpath.startswith(conditions["path_starts_with"]):
                    omitted[file_path] = "path_starts_with"
                    continue
                try:
                    if os.path.islink(file_path):
                        omitted[file_path] = f"islink: {os.path.realpath(file_path)}"
                    if conditions["max_size"] and os.stat(file_path).st_size > conditions["max_size"]:
                        omitted[file_path] = "max_size"
                        continue
                    if conditions["test_utf_readable"]:
                        with open(file_path, "r", encoding="utf-8") as f:
                            _ = f.read(1)
                    # all conditions met, hash and copy file if changed
                    copy_path = BASE_PATH + file_path
                    with open(file_path, "rb") as f:
                        file_contents = f.read()
                        new_hash = hashlib.sha256(file_contents).hexdigest()
                        new_hashes[file_path] = new_hash
                    if new_hash == old_hashes.get(file_path, ""):
                        continue
                    # dest might be readonly since permissions are copied, temporarily make it writable
                    if os.path.exists(copy_path) and not os.path.islink(copy_path):
                        os.chmod(copy_path, 0o200)
                    elif not os.path.isdir(os.path.dirname(copy_path)):
                        os.makedirs(os.path.dirname(copy_path))
                    with open(copy_path, "wb") as f:
                        f.write(file_contents)
                    shutil.copystat(file_path, copy_path)
                    del file_contents
                except Exception as e:
                    omitted[file_path] = type(e).__name__
        # remove copies of tracked files that no longer exist on system
        for root, dirs, files in os.walk(BASE_PATH + tracked_path, followlinks=False):
            for file in files:
                if not os.path.exists("/" + os.path.relpath(os.path.join(root, file), BASE_PATH)):
                    if not os.path.islink(os.path.join(root, file)):
                        os.chmod(os.path.join(root, file), 0o200)
                    os.remove(os.path.join(root, file))
    # write new hashes and omitted files with reasons
    with open(os.path.join(BASE_PATH, "sha256.json"), "w", encoding="utf-8", errors="surrogateescape") as json_file:
        json.dump(new_hashes, json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
    with open(os.path.join(BASE_PATH, "omitted.json"), "w", encoding="utf-8", errors="surrogateescape") as json_file:
        json.dump(omitted, json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)


def copy_and_git_add_all() -> list[list[str]]:
    cmds = [
        [sys.executable, os.path.abspath(__file__), "--_hash_and_copy_files"],
        ["git", "add", "--ignore-errors", "--all"]
    ]
    return cmds


def send_email(config_email: dict, job_email: dict, body: str) -> int:
    message = email.message.EmailMessage()
    message["From"] = config_email["from"]
    message["To"] = job_email["to"]
    if config_email["cc"]:
        message["Cc"] = config_email["cc"]
    message["Subject"] = job_email["subject"]
    if config_email["html"]:
        body = email.mime.text.MIMEText("<pre>" + body + "</pre>", "html")
    message.set_content(body)
    with smtplib.SMTP(config_email["smtp_server"], int(config_email["smtp_port"])) as smtp_server_instance:
        smtp_server_instance.ehlo()
        smtp_server_instance.starttls()
        smtp_server_instance.login(config_email["smtp_username"], config_email["smtp_password"])
        smtp_server_instance.send_message(message)
    return 0


def main() -> int:
    # There are three main steps to baka:
    # 1. Generate commands to be executed based on argument
    # 2. Execute (or print if dry-run) commands
    # 3. Append time and arguments to history.log, also log command output if job
    if sys.flags.optimize > 0:
        print("Warning: baka does not function properly with the -O (optimize) flag", file=sys.stderr)
    # parse arguments
    parser = init_parser()
    args = parser.parse_args()
    # init config
    config = Config()
    # change cwd to repo folder
    original_cwd = os.getcwd()
    os.chdir(BASE_PATH)
    # 1. Generate commands to be executed based on argument
    # all arguments are mutually exclusive, except for dry-run or the job modifiers
    # no commands are ever executed and nothing is ever written outside of ~/.baka if --dry-run
    if args.hash_and_copy_files:
        # meant for internal use only
        hash_and_copy_files(config)
        return 0
    elif args.init:
        assert not (os.path.exists(os.path.join(BASE_PATH, ".gitignore")) or os.path.exists(os.path.join(BASE_PATH, ".git")))
        # option to edit then reload config
        _ = input("Press enter to open your config file with nano")
        if args.dry_run:
            print(shlex.join(["nano", os.path.join(BASE_PATH, "config.json")]))
        else:
            subprocess.run(["nano", os.path.join(BASE_PATH, "config.json")])
        config = Config()
        # git commands
        cmds = [
            ["git", "init"],
            ["git", "config", "user.name", "baka admin"],
            ["git", "config", "user.email", "baka@" + config.hostname],
            ["touch", "error.log"],
            ["bash", "-c", "echo '"
                "history.log\n"
                "hostname\n"
                "docker/**\n"
                "ignore/**\n"
                "!**/config.php\n"
                "!**/*.ini\n"
                "!**/*.json\n"
                "!**/*.toml\n"
                "!**/*.xml\n"
                "!**/*.yaml\n"
                "!**/*.yml\n"
                "*~\n"
                "*-old\n"
                "*.cache\n"
                "*.dpkg-bak\n"
                "*.dpkg-dist\n"
                "*.dpkg-new\n"
                "*.dpkg-old\n"
                "**/fish_history\n"
                "**/xonsh-*.json\n"
            "' > .gitignore"],
            ["bash", "-c", "read -p 'Press enter to open .gitignore with nano'"],
            ["nano", os.path.join(BASE_PATH, ".gitignore")],
            ["bash", "-c", "read -p 'Press enter to add files to repository'"],
            *copy_and_git_add_all(),
            ["mkdir", "-p", "docker"],
            ["mkdir", "-p", "ignore"],
            ["mkdir", "-p", "scripts"],
            ["mkdir", "-p", "syscks"],
            ["mkdir", "-p", "scans"],
            ["git", "commit", "-m", "baka initial commit"]
        ]
    elif args.commit:
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka commit " + args.commit]
        ]
    elif args.push:
        cmds = [
            ["git", "push"]
        ]
    elif args.pull:
        cmds = [
            ["git", "pull"]
        ]
    elif args.untrack:
        paths = []
        for path in sorted(args.untrack):
            if os.path.isabs(path):
                paths.append(os.path.normpath(os.path.relpath(path)))
            else:
                paths.append(os.path.normpath(os.path.relpath(os.path.join(original_cwd, path))))
            assert os.path.exists(paths[-1])
        cmds = [
            ["git", "commit", "-m", "baka pre-untrack"],
            ["git", "rm", "-r", "--cached", *paths],
            ["bash", "-c", "echo \"\n# baka untrack\n%s\" >> .gitignore" % "\n".join(paths)],
            ["git", "add", ".gitignore"],
            ["git", "commit", "-m", "baka untrack %s" % " ".join(paths)]
        ]
    elif args.install:
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka pre-install"],
            config.cmd_install + args.install,
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka install " + " ".join(args.install)]
        ]
    elif args.remove is not None:
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka pre-remove"],
            config.cmd_remove + args.remove,
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka remove " + " ".join(args.remove)]
        ]
    elif args.upgrade:
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka pre-upgrade"],
            config.cmd_upgrade,
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka upgrade"]
        ]
    elif args.docker or args.podman:
        compose: str = "sudo docker-compose" if args.docker else "podman-compose"
        args.docker = args.docker if args.docker else args.podman
        assert args.docker[0] in ["up", "down", "pull"] and len(args.docker) >= 2
        assert args.docker[1] != "all" or (args.docker[1] == "all" and len(args.docker) == 2)
        compose_arg = "up -d" if args.docker[0] == "up" else args.docker[0]
        cmds = []
        if args.docker[1] == "all":
            for folder in sorted(os.listdir("docker")):
                if not os.path.exists(os.path.join("docker", folder, ".dockerignore")):
                    cmds.append(["bash", "-c", f"cd docker/{folder} && {compose} {compose_arg}"])
        else:
            for folder in args.docker[1:]:
                cmds.append(["bash", "-c", f"cd docker/{folder} && {compose} {compose_arg}"])
    elif args.file:
        assert args.file[0] in ["save", "restore", "s", "r"] and len(args.file) >= 2
        assert args.file[1] != "all" or (args.file[1] == "all" and len(args.file) == 2)
        file_list = config.files.keys() if args.file[1] == "all" else args.file[1:]
        cmds = [
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", f"baka pre-file {config.hostname}"]
        ]
        current_os = "windows" if os.name == "nt" else "linux"
        not_current_os_abbrev = "l" if current_os == "windows" else "w"
        copy_command = ["cp", "-f"] if current_os == "linux" else ["copy", "/Y"]
        os.path.makedirs(os.path.join(BASE_PATH, config.hostname), exist_ok=True)
        for file in file_list:
            assert len(config.files[file]) == 1
            file_key = list(config.files[file].keys())[0]
            if not_current_os_abbrev in file_key.split("_"):
                continue
            if args.file[0] in ["save", "s"]:
                if "src" in file_key.split("_"):
                    cmds.append([*copy_command, config.files[file][file_key], os.path.join(BASE_PATH, config.hostname, file)])
                elif "cmd" in config.files[file]:
                    cmds.append(["BAKA_DEST", os.path.join(BASE_PATH, config.hostname, file), *config.files[file]["cmd"]])
            elif args.file[0] in ["restore", "r"]:
                if "src" in file_key.split("_"):
                    cmds.append([*copy_command, os.path.join(BASE_PATH, config.hostname, file), config.files[file][file_key]])
        cmds.append(["git", "add", "--ignore-errors", "--all"])
        cmds.append(["git", "commit", "-m", f"baka file {config.hostname}"])
    elif args.job:
        if args.interactive:
            config.jobs[args.job]["interactive"] = True
        cmds = config.jobs[args.job]["commands"]
    elif args.list:
        cmds = [
            ["echo", "Prompt\tExit!0\tJob Name\n========================"],
            *[["echo", "%s\t%s\t%s" % ("interactive" in config.jobs[job] and config.jobs[job]["interactive"],
                                       "exit_non_zero" in config.jobs[job] and config.jobs[job]["exit_non_zero"],
                                       job)] for job in config.jobs]
        ]
    elif args.system_checks:
        assert ("history" not in config.system_checks)
        assert all([key not in config.system_scans for key in config.system_checks])
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka pre-sysck"],
            *[["bash", "-c", "%s > syscks/%s.log" % (config.system_checks[key], key)] for key in config.system_checks],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka sysck"]
        ]
    elif args.system_scans:
        assert ("history" not in config.system_scans)
        assert all([key not in config.system_checks for key in config.system_scans])
        cmds = [
            *copy_and_git_add_all(),
            ["git", "commit", "-m", "baka pre-scan"],
            *[["bash", "-c", "%s | tee scans/%s.log" % (config.system_scans[key], key)] for key in config.system_scans],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka scan"]
        ]
    elif args.diff:
        cmds = [
            *copy_and_git_add_all(),
            ["git", "status", "-sb"],
            ["git", "diff", "--color-words", "--cached", "--minimal"]
        ]
    elif args.log:
        cmds = [[
            "git", "log", "--abbrev-commit", "--all", "--decorate", "--graph", "--stat",
            "--format=format:%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(bold yellow)%d%C(reset)%n%C(bold white)%s%C(reset)%C(dim white) - %an%C(reset)"
        ]]
    elif args.show:
        cmds = [["git", "show", "--color-words"]]
    else:
        parser.print_usage()
        return 2
    # 2. Execute (or print if dry-run) commands
    command_output = []
    error_message = ""
    pending_stat = False
    return_code = 0
    try:
        for cmd in cmds:
            if args.job and config.jobs[args.job].get("shlex_split", False):
                if type(cmd) == list and len(cmd) == 1:
                    cmd = cmd[0]
                cmd = shlex.split(cmd)
            if args.dry_run:
                print(shlex.join(cmd))
                command_output.append("dry-run")
                command_output.append(">>> " + shlex.join(cmd))
                continue
            # execute command if not dry-run
            if args.job:
                # run command as part of job, otherwise run command normally
                capture_output = bool(
                    ("write" in config.jobs[args.job] and config.jobs[args.job]["write"]) or
                    ("email" in config.jobs[args.job] and config.jobs[args.job]["email"] and config.jobs[args.job]["email"]["to"])
                )
                verbosity = config.jobs[args.job].get("verbosity", "debug")
                verbosity = verbosity if verbosity else "debug"
                verbosity = verbosity.lower()
                assert verbosity in ["debug", "info", "error", "silent"]
                if verbosity in ["debug"]:
                    print("\033[94m%s\033[0m" % shlex.join(cmd))
                if config.jobs[args.job].get("interactive", False):
                    response = input("\033[92mContinue (yes/no/skip)?\033[0m ")
                    if response.strip().lower().startswith("y"):
                        pass
                    elif response.strip().lower().startswith("n"):
                        break
                    elif response.strip().lower().startswith("s"):
                        continue
                    else:
                        print("\033[91mInvalid response, exiting\033[0m")
                        break
                proc_input = b"y\n" if args.yes else None
                proc_out = subprocess.PIPE
                proc_err = subprocess.PIPE
                if not capture_output:
                    if verbosity in ["debug", "info"]:
                        proc_out = sys.stdout
                    if verbosity in ["debug", "info", "error"]:
                        proc_err = sys.stderr
                proc = subprocess.run(cmd, stdout=proc_out, stderr=proc_err, input=proc_input)
                if proc.returncode != 0:
                    if args.error_interactive:
                        return_code += 1
                        print(f"Error: exit {proc.returncode} for `{shlex.join(cmd)}`, continuing in interactive mode")
                        config.jobs[args.job]["interactive"] = True
                    elif config.jobs[args.job].get("exit_non_zero", False):
                        return_code = proc.returncode
                        error_message = "Error: baka job encountered a non-zero exit code for `%s`, exiting" % shlex.join(cmd)
                        command_output.append(error_message)
                        print(error_message, file=sys.stderr)
                        break
                    else:
                        return_code += 1
                if capture_output:
                    if verbosity in ["debug", "info"]:
                        sys.stdout.buffer.write(proc.stdout)
                    if verbosity in ["debug", "info", "error"]:
                        sys.stderr.buffer.write(proc.stderr)
                        print("\n")
                    command_output.append(">>> " + shlex.join(cmd))
                    command_output.append(proc.stdout.decode().strip())
                    command_output.append(proc.stderr.decode().strip())
                    command_output.append("\n")
                elif verbosity in ["debug", "info", "error"]:
                    print("")
            elif args.file:
                # save outputs of non-copy commands as files, otherwise run command normally
                if cmd[0] == "BAKA_DEST":
                    dest = cmd[1]
                    with open(dest, "w", encoding="utf-8", errors="surrogateescape") as f:
                        proc = subprocess.run(cmd[2:], capture_output=True, text=True)
                        f.write(proc.stdout)
                else:
                    proc = subprocess.run(cmd)
                if proc.returncode != 0 and not (cmd[0] == "git" and cmd[1] == "commit"):
                    return_code += 1
            else:
                # run command normally
                if cmd == [sys.executable, os.path.abspath(__file__), "--_hash_and_copy_files"]:
                    pending_stat = True
                elif pending_stat:
                    os_stat_tracked_files(config)
                    pending_stat = False
                proc = subprocess.run(cmd)
                if proc.returncode != 0 and not (cmd[0] == "git" and cmd[1] == "commit"):
                    return_code += 1
    except Exception as e:
        error_message = "Error baka line: %s For: %s %s %s" % (sys.exc_info()[2].tb_lineno, shlex.join(cmd), type(e).__name__, e.args)
        command_output.append(error_message)
        print(error_message, file=sys.stderr)
    # 3. Append time and arguments to history.log, also log command output if job
    # append to history.log
    if not (args.dry_run or args.diff or args.log or args.show):
        log_entry = time.ctime()
        for key in vars(args):
            if vars(args)[key] or (key == "remove" and args.remove is not None):
                log_entry += " " + key + " " + str(vars(args)[key])
        if error_message:
            log_entry += " " + error_message
        with open(os.path.join(BASE_PATH, "history.log"), "a", encoding="utf-8", errors="surrogateescape") as log_file:
            log_file.write(log_entry + "\n")
    # email or write command output
    if args.job:
        command_output = "\n".join(command_output)
        if "email" in config.jobs[args.job] and config.jobs[args.job]["email"] and config.jobs[args.job]["email"]["to"]:
            try:
                send_email(config.email, config.jobs[args.job]["email"], command_output)
            except Exception as e:
                error_email = "--- %s ---\nEmail Error: %s %s\nMessage:\n%s" % (time.ctime(), type(e).__name__, e.args, command_output)
                with open(os.path.join(BASE_PATH, "error.log"), "a", encoding="utf-8", errors="surrogateescape") as log_file:
                    log_file.write(error_email + "\n")
        if "write" in config.jobs[args.job] and config.jobs[args.job]["write"]:
            file_path = os.path.abspath(datetime.datetime.now().strftime(config.jobs[args.job]["write"]))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8", errors="backslashreplace") as f:
                f.write(command_output)
    return return_code


if __name__ == "__main__":
    sys.exit(main())

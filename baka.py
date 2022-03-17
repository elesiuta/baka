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
import json
import os
import shlex
import shutil
import smtplib
import subprocess
import sys
import time

VERSION = "0.6.9"


def init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="the stupid configuration tracker using the stupid content tracker",
                                     usage="%(prog)s [--dry-run] <argument>")
    parser.add_argument("--version", action="version", version=VERSION)
    maingrp = parser.add_mutually_exclusive_group()
    maingrp.add_argument("--_copy_conditional_paths", dest="copy_conditional_paths", action="store_true",
                         help=argparse.SUPPRESS)
    maingrp.add_argument("--init", dest="init", action="store_true",
                         help="open config, init git repo, add files then commit")
    maingrp.add_argument("--commit", dest="commit", type=str, metavar="msg",
                         help="git add and commit your changes to tracked files")
    maingrp.add_argument("--push", dest="push", action="store_true",
                         help="git push (caution, ensure remote is private)")
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
    maingrp.add_argument("--job", dest="job", type=str, metavar="name",
                         help="run commands for job with name")
    maingrp.add_argument("--list", dest="list", action="store_true",
                         help="show list of jobs")
    maingrp.add_argument("--sysck", dest="system_checks", action="store_true",
                         help="run commands for system checks and commit output")
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
        self.email = {
            "cc": None,
            "from": "myemail@domain.com",
            "html": True,
            "smtp_server": "smtp.domain.com",
            "smtp_port": 587,
            "smtp_username": "username",
            "smtp_password": "password"
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
        self.tracked_paths = {
            "/etc": {"max_size": 128000},
            os.path.expanduser("~/.config"): {"max_depth": 2, "max_size": 128000},
            os.path.expanduser("~/.local/share"): {"max_depth": 2, "max_size": 128000},
        }
        # load config
        for key in config:
            if config[key] is not None and hasattr(self, key):
                self.__setattr__(key, config[key])
        for tracked_path in self.tracked_paths:
            assert os.path.isabs(tracked_path)
        # write config file if does not exist
        if not os.path.exists(config_path):
            if not os.path.isdir(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path))
            try:
                with open(config_path, "w", encoding="utf-8", errors="surrogateescape") as json_file:
                    json.dump(vars(self), json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)
            except Exception:
                print("Error: Could not write config file to " + config_path)


def os_stat_tracked_files(config: "Config") -> None:
    stat = {}
    for tracked_path in list(config.tracked_paths):
        if os.path.isdir(tracked_path):
            for root, dirs, files in os.walk(tracked_path):
                for file_or_folder in files + dirs:
                    file_path = os.path.join(root, file_or_folder)
                    if os.path.exists(os.path.expanduser("~/.baka") + file_path):
                        file_stat = os.stat(file_path)
                        stat[file_path] = {"mode": oct(file_stat.st_mode), "uid": file_stat.st_uid, "gid": file_stat.st_gid}
        elif os.path.isfile(tracked_path):
            file_path = tracked_path
            if os.path.exists(os.path.expanduser("~/.baka") + file_path):
                file_stat = os.stat(file_path)
                stat[file_path] = {"mode": oct(file_stat.st_mode), "uid": file_stat.st_uid, "gid": file_stat.st_gid}
    with open(os.path.expanduser("~/.baka/stat.json"), "w", encoding="utf-8", errors="surrogateescape") as json_file:
        json.dump(stat, json_file, indent=2, separators=(',', ': '), sort_keys=True, ensure_ascii=False)


def copy_conditional_paths(config: "Config") -> None:
    for tracked_path in config.tracked_paths:
        if config.tracked_paths[tracked_path]:
            conditions = {"file_starts_with": "", "path_starts_with": "", "max_depth": None, "max_size": None}
            for condition in config.tracked_paths[tracked_path]:
                conditions[condition] = config.tracked_paths[tracked_path][condition]
            for root, dirs, files in os.walk(tracked_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if conditions["file_starts_with"] and not file.startswith(conditions["file_starts_with"]):
                        continue
                    if conditions["path_starts_with"] and not os.path.relpath(file_path, tracked_path).startswith(conditions["path_starts_with"]):
                        continue
                    if conditions["max_depth"] and os.path.relpath(file_path, tracked_path).count("/") >= conditions["max_depth"]:
                        del dirs
                        break
                    try:
                        if conditions["max_size"] and not os.path.islink(file_path) and os.stat(file_path).st_size > conditions["max_size"]:
                            continue
                        with open(file_path, "r", encoding="utf-8") as f:
                            _ = f.read(1)
                        if os.path.exists(os.path.expanduser("~/.baka") + file_path) and not os.path.islink(os.path.expanduser("~/.baka") + file_path):
                            os.chmod(os.path.expanduser("~/.baka") + file_path, 0o200)
                        shutil.copy2(file_path, os.path.expanduser("~/.baka") + file_path, follow_symlinks=False)
                    except Exception:
                        pass
            for root, dirs, files in os.walk(os.path.expanduser("~/.baka") + tracked_path):
                for file in files:
                    if not os.path.exists("/" + os.path.relpath(os.path.join(root, file), os.path.expanduser("~/.baka"))):
                        if not os.path.islink(os.path.join(root, file)):
                            os.chmod(os.path.join(root, file), 0o200)
                        os.removedirs(os.path.join(root, file))


def rsync_and_git_add_all(config: "Config") -> list:
    cmds = [[sys.executable, os.path.abspath(__file__), "--_copy_conditional_paths"]]
    for tracked_path in config.tracked_paths:
        if not config.tracked_paths[tracked_path]:
            if not os.path.exists(os.path.dirname(os.path.expanduser("~/.baka") + tracked_path)):
                os.makedirs(os.path.dirname(os.path.expanduser("~/.baka") + tracked_path))
            cmds.append(["rsync", "-rlpt", "--delete", tracked_path, os.path.dirname(os.path.expanduser("~/.baka") + tracked_path)])
    cmds.append(["git", "add", "--ignore-errors", "--all"])
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
    # parse arguments
    parser = init_parser()
    args = parser.parse_args()
    # init config
    config = Config()
    # change cwd to repo folder
    original_cwd = os.getcwd()
    os.chdir(os.path.expanduser("~/.baka"))
    # select commands
    if args.copy_conditional_paths:
        copy_conditional_paths(config)
        return 0
    elif args.init:
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
            ["git", "config", "user.name", "baka admin"],
            ["git", "config", "user.email", "baka@" + os.uname().nodename],
            ["touch", "error.log"],
            ["bash", "-c", "echo '"
                "history.log\n"
                "docker/**\n"
                "ignore/**\n"
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
            ["nano", os.path.expanduser("~/.baka/.gitignore")],
            ["bash", "-c", "read -p 'Press enter to add files to repository'"],
            *rsync_and_git_add_all(config),
            ["mkdir", "-p", "docker"],
            ["mkdir", "-p", "ignore"],
            ["mkdir", "-p", "scripts"],
            ["mkdir", "-p", "syscks"],
            ["mkdir", "-p", "scans"],
            ["git", "commit", "-m", "baka initial commit"]
        ]
    elif args.commit:
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka commit " + args.commit]
        ]
    elif args.push:
        cmds = [
            ["git", "push"]
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
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-install"],
            config.cmd_install + args.install,
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka install " + " ".join(args.install)]
        ]
    elif args.remove is not None:
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-remove"],
            config.cmd_remove + args.remove,
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka remove " + " ".join(args.remove)]
        ]
    elif args.upgrade:
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-upgrade"],
            config.cmd_upgrade,
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka upgrade"]
        ]
    elif args.docker:
        assert args.docker[0] in ["up", "down", "pull"] and len(args.docker) >= 2
        assert args.docker[1] != "all" or (args.docker[1] == "all" and len(args.docker) == 2)
        cmd = "up -d" if args.docker[0] == "up" else args.docker[0]
        cmds = []
        if args.docker[1] == "all":
            for folder in sorted(os.listdir("docker")):
                if not os.path.exists(os.path.join("docker", folder, ".dockerignore")):
                    assert os.path.exists(os.path.join("docker", folder, "docker-compose.yml"))
                    cmds.append(["bash", "-c", "cd docker/%s && sudo docker-compose %s" % (folder, cmd)])
        else:
            for folder in args.docker[1:]:
                assert os.path.exists(os.path.join("docker", folder, "docker-compose.yml"))
                cmds.append(["bash", "-c", "cd docker/%s && sudo docker-compose %s" % (folder, cmd)])
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
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-sysck"],
            *[["bash", "-c", "%s > syscks/%s.log" % (config.system_checks[key], key)] for key in config.system_checks],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka sysck"]
        ]
    elif args.system_scans:
        assert ("history" not in config.system_scans)
        assert all([key not in config.system_checks for key in config.system_scans])
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-scan"],
            *[["bash", "-c", "%s | tee scans/%s.log" % (config.system_scans[key], key)] for key in config.system_scans],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka scan"]
        ]
    elif args.diff:
        cmds = [
            *rsync_and_git_add_all(config),
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
    # execute commands
    command_output = []
    error_message = ""
    pending_stat = False
    return_code = 0
    try:
        for cmd in cmds:
            if args.job and "shlex_split" in config.jobs[args.job] and config.jobs[args.job]["shlex_split"]:
                if type(cmd) == list and len(cmd) == 1:
                    cmd = cmd[0]
                cmd = shlex.split(cmd)
            if args.dry_run:
                print(shlex.join(cmd))
                command_output.append("dry-run")
                command_output.append(">>> " + shlex.join(cmd))
            else:
                if args.job:
                    # run command as part of job, otherwise run command normally
                    capture_output = bool(
                        ("write" in config.jobs[args.job] and config.jobs[args.job]["write"]) or
                        ("email" in config.jobs[args.job] and config.jobs[args.job]["email"] and config.jobs[args.job]["email"]["to"])
                    )
                    verbosity = ""
                    if "verbosity" in config.jobs[args.job] and config.jobs[args.job]["verbosity"]:
                        verbosity = config.jobs[args.job]["verbosity"].lower()
                    if verbosity not in ["debug", "info", "error", "silent"]:
                        verbosity = "debug"
                    if verbosity in ["debug"]:
                        print("\033[94m%s\033[0m" % shlex.join(cmd))
                    if "interactive" in config.jobs[args.job] and config.jobs[args.job]["interactive"]:
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
                    proc_out = subprocess.PIPE
                    proc_err = subprocess.PIPE
                    if not capture_output:
                        if verbosity in ["debug", "info"]:
                            proc_out = sys.stdout
                        if verbosity in ["debug", "info", "error"]:
                            proc_err = sys.stderr
                    proc = subprocess.run(cmd, stdout=proc_out, stderr=proc_err)
                    if proc.returncode != 0:
                        if "exit_non_zero" in config.jobs[args.job] and config.jobs[args.job]["exit_non_zero"]:
                            return_code = proc.returncode
                            error_message = "Error: baka job encountered a non-zero return code for `%s`, exiting" % shlex.join(cmd)
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
                elif cmd[0] == "rsync":
                    # hide permission errors for rsync, otherwise run command normally
                    proc = subprocess.run(cmd, stderr=subprocess.PIPE, universal_newlines=True)
                    for line in proc.stderr.splitlines():
                        if line and "Permission denied (13)" not in line and "(see previous errors) (code 23)" not in line:
                            print(line, file=sys.stderr)
                    pending_stat = True
                else:
                    # run command normally
                    if pending_stat:
                        os_stat_tracked_files(config)
                        pending_stat = False
                    proc = subprocess.run(cmd)
                    if proc.returncode != 0 and not (cmd[0] == "git" and cmd[1] == "commit"):
                        return_code += 1
    except Exception as e:
        error_message = "Error baka line: %s For: %s %s %s" % (sys.exc_info()[2].tb_lineno, shlex.join(cmd), type(e).__name__, e.args)
        command_output.append(error_message)
        print(error_message, file=sys.stderr)
    # write log
    if not (args.dry_run or args.diff or args.log or args.show):
        log_entry = time.ctime()
        for key in vars(args):
            if vars(args)[key] or (key == "remove" and args.remove is not None):
                log_entry += " " + key + " " + str(vars(args)[key])
        if error_message:
            log_entry += " " + error_message
        with open(os.path.expanduser("~/.baka/history.log"), "a", encoding="utf-8", errors="surrogateescape") as log_file:
            log_file.write(log_entry + "\n")
    # email or write command output
    if args.job:
        command_output = "\n".join(command_output)
        if "email" in config.jobs[args.job] and config.jobs[args.job]["email"] and config.jobs[args.job]["email"]["to"]:
            try:
                send_email(config.email, config.jobs[args.job]["email"], command_output)
            except Exception as e:
                error_email = "--- %s ---\nEmail Error: %s %s\nMessage:\n%s" % (time.ctime(), type(e).__name__, e.args, command_output)
                with open(os.path.expanduser("~/.baka/error.log"), "a", encoding="utf-8", errors="surrogateescape") as log_file:
                    log_file.write(error_email + "\n")
        if "write" in config.jobs[args.job] and config.jobs[args.job]["write"]:
            file_path = os.path.abspath(datetime.datetime.now().strftime(config.jobs[args.job]["write"]))
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8", errors="backslashreplace") as f:
                f.write(command_output)
    return return_code


if __name__ == "__main__":
    sys.exit(main())

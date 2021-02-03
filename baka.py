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
import json
import os
import shlex
import smtplib
import subprocess
import sys
import time


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
    maingrp.add_argument("--job", dest="job", type=str, metavar="name",
                         help="run commands for job with name")
    maingrp.add_argument("--status", dest="status", action="store_true",
                         help="run commands to track status of various things")
    maingrp.add_argument("--verify", dest="verify", action="store_true",
                         help="run commands to verify system integrity")
    maingrp.add_argument("--diff", dest="diff", action="store_true",
                         help="show git diff --color-words")
    maingrp.add_argument("--log", dest="log", action="store_true",
                         help="show pretty git log")
    maingrp.add_argument("--show", dest="show", action="store_true",
                         help="show most recent commit")
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
                "interactive": False,
                "verbosity": "one of: debug (default if null), info, error, silent",
                "write": "./jobs/example job %Y-%m-%d %H:%M.log (supports strftime format codes) or null"
            }
        }
        self.status_checks = {
            "ip_rules_v4": "sudo cat /etc/iptables/rules.v4",
            "ip_rules_v6": "sudo cat /etc/iptables/rules.v6",
            "SMART-sda": "sudo smartctl -a /dev/sda",
            "SMART-sdb": "sudo smartctl -a /dev/sdb",
        }
        self.system_integrity = {
            "debsums": "sudo debsums -ac"
        }
        self.tracked_paths = [
            "/etc",
            os.path.expanduser("~/.config"),
            os.path.expanduser("~/.local/share")
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


def rsync_and_git_add_all(config: "Config") -> list:
    for path in config.tracked_paths:
        if not os.path.exists(os.path.dirname(os.path.expanduser("~/.baka") + path)):
            os.makedirs(os.path.dirname(os.path.expanduser("~/.baka") + path))
    cmds = [["rsync", "-rlpt", "--delete", path, os.path.dirname(os.path.expanduser("~/.baka") + path)] for path in config.tracked_paths]
    cmds += [["git", "add", "--ignore-errors", "--all"]]
    return cmds


def send_email(config_email: dict, job_email: dict, body: str) -> int:
    message = email.message.EmailMessage()
    message["From"] = config_email["from"]
    message["To"] = job_email["to"]
    if config_email["cc"]:
        message["Cc"] = config_email["cc"]
    message["Subject"] = job_email["subject"]
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
            ["git", "config", "user.name", "baka admin"],
            ["git", "config", "user.email", "baka@" + os.uname().nodename],
            ["bash", "-c", "echo '"
                "history.log\n"
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
            ["git", "commit", "-m", "baka initial commit"]
        ]
    elif args.commit:
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka commit " + args.commit]
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
    elif args.job:
        cmds = config.jobs[args.job]["commands"]
    elif args.status:
        assert ("history" not in config.status_checks)
        assert all([key not in config.system_integrity for key in config.status_checks])
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-status"],
            ["mkdir", "-p", "status"],
            *[["bash", "-c", "%s > status/%s.log" % (config.status_checks[key], key)] for key in config.status_checks],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka status"]
        ]
    elif args.verify:
        assert ("history" not in config.system_integrity)
        assert all([key not in config.status_checks for key in config.system_integrity])
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "commit", "-m", "baka pre-verify"],
            ["mkdir", "-p", "verify"],
            *[["bash", "-c", "%s | tee verify/%s.log" % (config.system_integrity[key], key)] for key in config.system_integrity],
            ["git", "add", "--ignore-errors", "--all"],
            ["git", "commit", "-m", "baka verify"]
        ]
    elif args.diff:
        cmds = [
            *rsync_and_git_add_all(config),
            ["git", "status", "-s"],
            ["git", "diff", "--color-words", "--cached", "--minimal"]
        ]
    elif args.log:
        cmds = [[
            "git", "log", "--abbrev-commit", "--all", "--decorate", "--graph", "--stat",
            "--format=format:%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(bold yellow)%d%C(reset)%n%C(bold white)%s%C(reset)%C(dim white) - %an%C(reset)"
        ]]
    elif args.show:
        cmds = [["git", "show", "--color-words"]]
    # execute commands
    command_output = []
    error_message = ""
    return_code = 0
    try:
        for cmd in cmds:
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
                            print(line)
                else:
                    # run command normally
                    subprocess.run(cmd)
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

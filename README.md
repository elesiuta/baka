# baka admin konfiguration assistant
This is mostly just a wrapper around git along with some other commands to help with managing servers or home directories  
If you're looking for something similar but not stupid, see [etckeeper](https://wiki.archlinux.org/title/Etckeeper) or other [alternatives](https://wiki.archlinux.org/title/Dotfiles)  
Otherwise, you can install from [PyPI](https://pypi.org/project/bakabakabaka/) with `pip install bakabakabaka`  
```
usage: baka [--dry-run] <argument>

the stupid configuration tracker using the stupid content tracker

options:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
  --init         open config, init git repo, add files then commit
  --commit msg   git add and commit your changes to tracked files
  --push         git push (caution, ensure remote is private)
  --pull         git pull (does not restore files over system)
  --untrack ...  untrack path(s) from git
  --install ...  install package(s) and commit changes
  --remove ...   remove package(s) and commit changes
  --upgrade      upgrade packages on system and commit changes
  --docker ...   usage: --docker <up|down|pull> <all|names...>
  --podman ...   usage: --podman <up|down|pull> <all|names...>
  --file ...     usage: --file <save|restore> <all|names...>
  --job name     run commands for job with name
  --list         show list of jobs
  --sysck        run commands for system checks and commits output
  --scan         run commands for scanning system, prints and commits output
  --diff         show git diff --color-words
  --log          show pretty git log
  --show         show most recent commit
  -e             toggles 'exit_non_zero' setting for current run of job
  -y             supplies 'y' to job commands, similar to yes | job
  -i             force job to run in interactive mode
  -n, --dry-run  print commands instead of executing them
```

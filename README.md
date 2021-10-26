# baka
the stupid configuration tracker using the stupid content tracker  
```
pip install bakabakabaka
```
  
I made this to help with monitoring logs, performing common actions, and tracking changes I make to my home server  
This is mostly just a wrapper for some rsync and git commands, if you're looking for something similar but with more features, see [etckeeper](https://wiki.archlinux.org/title/Etckeeper), or other alternatives [here](https://wiki.archlinux.org/title/Dotfiles)  
```
usage: baka [--dry-run] <argument>

Baka Admin's Kludge Assistant

optional arguments:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
  --init         open config, init git repo, add files then commit
  --commit msg   git add and commit your changes to tracked files
  --push         git push (caution, ensure remote is private)
  --untrack ...  untrack path(s) from git
  --install ...  install package(s) and commit changes
  --remove ...   remove package(s) and commit changes
  --upgrade      upgrade packages on system and commit changes
  --docker ...   usage: --docker <up|down|pull> <all|names...>
  --job name     run commands for job with name
  --list         show list of jobs
  --sysck        run commands for system checks and commit output
  --scan         run commands for scanning system, prints and commits output
  --diff         show git diff --color-words
  --log          show pretty git log
  --show         show most recent commit
  -i             force job to run in interactive mode
  -n, --dry-run  print system commands instead of executing them
```

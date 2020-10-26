# baka
the stupid configuration tracker using the stupid content tracker  
```
pip install bakabakabaka
```
  
I made this to help with tracking changes I make to my home server  
This is literally just a wrapper for some rsync and git commands, if you're looking for something similar but with more features, see etckeeper  
```
usage: baka [--dry-run] <argument>

Baka Admin's Kludge Assistant

optional arguments:
  -h, --help     show this help message and exit
  --init         open config, init git repo, add files then commit
  --commit msg   git add -u and commit your changes to tracked files
  --install ...  install package(s) and commit changes
  --remove ...   remove package(s) and commit changes
  --upgrade      upgrade packages on system and commit changes
  --job name     run commands for job with name
  --status       run commands to track status of various things
  --verify       run commands to verify system integrity
  --diff         show git diff --color-words
  --log          show pretty git log
  --show         show most recent commit
  -n, --dry-run  print system commands instead of executing them
```

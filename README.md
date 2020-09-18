# baka
the stupid configuration tracker using the stupid content tracker  
```
pip install bakabakabaka
```
  
I made this to help with tracking changes I make to my home server  
This is literally just a wrapper for some git commands, if you're looking for something similar but with more features, see etckeeper  
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
  --verify       verify all packages on system
  --diff         show git diff --stat
  --log          show pretty git log
  --git ...      wrapper to run git command with args
  -n, --dry-run  print system commands instead of executing them
```

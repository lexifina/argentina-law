#!/bin/sh
# Push the working folder (no .cache) to the `wip` branch of lexifina/argentina-law,
# from a separate clone so main (law builds only) is never touched.
set -e
SRC=C:/Users/alany/Documents/lexifina/scripts/argentina-law
WIP=C:/Users/alany/Documents/argentina-law-wip
if [ ! -d "$WIP/.git" ]; then
  git clone -q https://github.com/lexifina/argentina-law.git "$WIP"
fi
cd "$WIP"
git checkout -q --orphan wip-tmp 2>/dev/null || git checkout -q wip-tmp
git rm -rq --cached . >/dev/null 2>&1 || true
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p wip
( cd "$SRC" && tar --exclude=.cache --exclude=__pycache__ -cf - . ) | ( cd wip && tar -xf - )
if [ -f wip/corpus.json ] && [ "$(wc -c < wip/corpus.json)" -gt 50000000 ]; then rm wip/corpus.json; fi
git add -A
git -c user.name=gitlaw-AR -c user.email=corpus@lexifina.com commit -qm "wip: scripts/argentina-law snapshot" || true
git push -qf origin HEAD:wip
git log -1 --format='wip pushed %h'

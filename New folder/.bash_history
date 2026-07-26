git status
git log --oneline -5
gh auth status
git config --get remote.origin.url
git remote -v
git remote add origin https://github.com/nuwal01/Investor-doc-Finder.git
git push -u origin fix1-signal3-signal5-doctype-gate
git remote add origin https://github.com/nuwal01/Investor-doc-Finder.git
git push -u origin fix1-signal3-signal5-doctype-gate
git log main --oneline -10
git fetch origin
git checkout main
git pull origin main
git merge fix1-signal3-signal5-doctype-gate
git add <resolved files>
git commit
git push origin main
git diff fund_filter.py
git add fund_filter.py test_fund_filter.py .gitattributes
git commit -m "wip: fund filter changes"
git fetch origin
git show origin/main --stat
git push origin fix1-signal3-signal5-doctype-gate:main --force
git checkout main
git reset --hard origin/main
git push origin --delete fix1-signal3-signal5-doctype-gate
git branch -d fix1-signal3-signal5-doctype-gate

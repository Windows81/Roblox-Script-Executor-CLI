d=`date +"%Y-%m-%d"`

cd workspace/logs
git add .
git commit -m $d
git push

cd ../
git add .
git commit -m $d
git push

cd ../
git add .
git commit -m $d
git push
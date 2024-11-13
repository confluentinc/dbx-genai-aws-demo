#!/usr/bin/env sh

if [ -z "$1" ]; then
    echo "Usage: $0 <properties file> <crd file>"
    exit 1
fi

if [ -z "$2" ]; then
    echo "Usage: $0 <properties file> <crd file>"
    exit 1
else
  FILES="$2"
fi

source ./export.sh $1

for FILE in $FILES; do
  if [ ! -f "./$FILE" ]; then
    continue
  fi

  echo "Deploying $FILE"

  envsubst < "./$FILE" > "./$FILE.tmp"
  if [ $? -ne 0 ]; then
    echo "==> Deployment failed"
    exit 1
  fi

  echo kubectl apply -f "./$FILE.tmp" --namespace csp-demo

  kubectl apply -f "./$FILE.tmp" --namespace csp-demo
  if [ $? -ne 0 ]; then
    echo "==> Deployment failed"
    exit 1
  fi

  rm -f "./$FILE.tmp"

done

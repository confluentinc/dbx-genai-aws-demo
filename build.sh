#!/usr/bin/env sh

if [ -z "$3" ]; then
    echo "Usage: $0 <dockerfile> <app_name> <version>"
    exit 1
fi

docker buildx build --platform linux/amd64 . -f ./$1 -t $2:$3-amd64 -t 635910096382.dkr.ecr.us-east-1.amazonaws.com/$2:$3-amd64
docker push 635910096382.dkr.ecr.us-east-1.amazonaws.com/$2:$3-amd64

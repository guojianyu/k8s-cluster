#!/usr/bin/env bash
export GOPATH=`pwd`
echo `pwd`

mkdir -p src/github.com/prometheus
mv alertmanager src/github.com/prometheus/
cd src/github.com/prometheus/alertmanager
make build
docker build -t lenovo.com/cloud_server/prometheus/alertmanager:$1 .


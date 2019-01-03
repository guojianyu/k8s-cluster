#!/usr/bin/env bash
cd ..
export GOPATH=`pwd`

mkdir -p src/github.com/grafana
cp grafana src/github.com/grafana/ -r
cd src/github.com/grafana/grafana
go run build.go build

mkdir tmp_docker
cp bin/linux-amd64/grafana-server   /home/
cp bin/linux-amd64/grafana-cli      /home/

docker build -t lenovo.com/cloud_server/digitalocean/ceph_exporter:$1  tmp_docker


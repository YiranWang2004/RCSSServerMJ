#!/bin/bash

# 停止旧的服务器进程
echo "Stopping old rcssservermj processes..."
pkill -f rcssservermj

sleep 1

# 启动新的服务器
echo "Starting rcssservermj with PiPlus support..."
rcssservermj -a 127.0.0.1 -c 60000 -m 60001 -f hl_adult_2020 -b hl_adult_2025

echo "Server started. PiPlus robot should now be available."

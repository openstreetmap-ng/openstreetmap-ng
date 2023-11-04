#!/bin/sh
set -e

echo "Initiating MongoDB replica set..."
sleep 1

# disable telemetry
mongosh --nodb --eval 'disableTelemetry()'

# wait for MongoDB to start
until mongosh --host db --eval 'db.runCommand({ ping: 1 })'
do
    echo "$(date) - Waiting for MongoDB to start"
    sleep 1
done

if [ "$(mongosh --host db --eval 'rs.status().ok')" = "0" ]; then
    echo "Initiating replica set..."
    mongosh --host db --eval "rs.initiate({_id: 'rs0', members:[{_id: 0, host:'$1'}]})"
fi

echo "Replica set initiated"

#!/bin/bash
set -e

# Path to the hazelcast.xml file
HAZELCAST_CONFIG="/opt/geoserver/data_dir/cluster/hazelcast.xml"

# Disable auto-detection
xmlstarlet ed -L -u "/hazelcast/network/join/auto-detection/@enabled" -v "false" $HAZELCAST_CONFIG

# Disable multicast
xmlstarlet ed -L -u "/hazelcast/network/join/multicast/@enabled" -v "false" $HAZELCAST_CONFIG

# Enable TCP-IP
xmlstarlet ed -L -u "/hazelcast/network/join/tcp-ip/@enabled" -v "true" $HAZELCAST_CONFIG

# Remove existing member-list if it exists
xmlstarlet ed -L -d "/hazelcast/network/join/tcp-ip/member-list" $HAZELCAST_CONFIG

# Add new member-list
xmlstarlet ed -L -s "/hazelcast/network/join/tcp-ip" -t elem -n "member-list" $HAZELCAST_CONFIG

# Add members
xmlstarlet ed -L \
  -s "/hazelcast/network/join/tcp-ip/member-list" -t elem -n "member" -v "master" \
  -s "/hazelcast/network/join/tcp-ip/member-list" -t elem -n "member" -v "node1" \
  -s "/hazelcast/network/join/tcp-ip/member-list" -t elem -n "member" -v "node2" \
  -s "/hazelcast/network/join/tcp-ip/member-list" -t elem -n "member" -v "node3" \
  $HAZELCAST_CONFIG

echo "Hazelcast configuration updated successfully."

# Execute the original entrypoint command
exec "$@"
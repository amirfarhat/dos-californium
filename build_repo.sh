#!/bin/bash

# Remove demo executables from the last build
echo "Removing executables..."
rm demo-apps/run/*.jar

# Compile the repo without running any tests
echo "Building source..."
mvn --quiet clean install -DskipTests

# Run tests for the packages that proxy uses
echo "Running tests..."
mvn --quiet surefire:test -pl demo-apps,californium-proxy2,californium-core
#!/bin/bash
set -ex

###################################################################
# This script will get executed *once* the Docker container has
# been built. Commands that need to be executed with all available
# tools and the filesystem mount enabled should be located here.
###################################################################

# Tell git the workspace repository is safe, else upcoming commands will fail.
git config --global --add safe.directory /workspaces/notification-admin

chown -R vscode:vscode /workspaces/notification-admin || true
sudo -u vscode -i -- /usr/local/bin/installations.sh

#!/bin/bash
set -ex

###################################################################
# This script will get executed *once* the Docker container has
# been built. Commands that need to be executed with all available
# tools and the filesystem mount enabled should be located here.
###################################################################

# Define aliases
echo -e "\n\n# User's Aliases" >> ~/.zshrc
echo -e "alias fd=fdfind" >> ~/.zshrc
echo -e "alias l='ls -al --color'" >> ~/.zshrc
echo -e "alias ls='exa'" >> ~/.zshrc
echo -e "alias l='exa -alh'" >> ~/.zshrc
echo -e "alias ll='exa -alh@ --git'" >> ~/.zshrc
echo -e "alias lt='exa -al -T -L 2'" >> ~/.zshrc

# Warm up git index prior to display status in prompt else it will
# be quite slow on every invocation of starship.
git status

pip3 install pip-tools
pip-compile --resolver=backtracking requirements.in
pip-compile --resolver=backtracking requirements_for_test.txt
pip-sync
# pip3 install -r requirements.txt
# pip3 install -r requirements_for_test.txt

npm rebuild node-sass
make generate-version-file
make babel

npm ci install
npm run build
#!/bin/bash

rm -rf codeval
# this unset line is a horrible hack. cert finding seems to be broken with pyz
unset REQUESTS_CA_BUNDLE
python3 -m pip install -r requirements.txt --target codeval
rm -rf codeval/*.dist-info
rm -rf codeval/*.egg-info
cp -r distributed *.py *.sh parse* codeval
python3 -m zipapp codeval

#!/bin/bash
LANG=en_US.utf-8

# This is a wrapper for
#   ofxstatement convert -t raiffeisencz input.csv output.ofx
# which:
# - if there is any input-fees.csv, it runs again
# - reformats output.ofx to be human readable

# ToDo:
# - merge input-fees.ofx with output.ofx

# Dependency:
# - bash
# - ofxstatement
# - ofxstatement-raiffeisencz (plugin)
# - uuidgen
# - xmllint

if [[ "x$1" = "x" ]]; then
  echo "Expects bank statement history CSV file as input (Menu: Account // Movements on account)"
  echo "Usage:"
  echo "  $0 input.csv"
  exit 1
fi

if [[ ! -f "${1}" ]]; then
  echo "File ${1} does not exist or is not readable"
  exit 1
fi

inputf="$(basename "${1}" .csv)"
inputd="$(dirname "${1}")"



# Run ofxstatement 
ofxstatement convert -t raiffeisencz:CZK "${1}" "${inputd}/${inputf}.ofx" \
  || { echo "ofxstatement 1 failed."; exit 1; }

tmpf="$(uuidgen)"
cat "${inputd}/${inputf}.ofx" | xmllint --format  --encode UTF-8 - > "${inputd}/${tmpf}"
mv "${inputd}/${tmpf}" "${inputd}/${inputf}.ofx"

#!/bin/bash
# based on https://unix.stackexchange.com/a/436713

source ../common.sh

SCRIPT_NAME=correlation-length
SCRIPT_PATH=./${SCRIPT_NAME}.py
BASE_OUT=./experiment

BASE_IN=../step-1/experiment

FILES=$(find "${BASE_IN}" -name "cutin-tiff-small.tiff")
NUM_FILES=$(echo "$FILES" | wc -l)
IDX_FILE=0

SL=0

echo "$FILES" | (
  while read filepath; do
  
    #[ -z "${filepath##*12.5*}" ] && continue

    IDX_FILE=$(( IDX_FILE + 1 ))
    TMP=$(dirname "$filepath")
    CASE_PATH=${TMP##${BASE_IN}/}

    OUT=${BASE_OUT}/${CASE_PATH}
    [ -d "${OUT}" ] || mkdir -p "${OUT}"

    for CH in 0; do
      ARGS=""

      echo "Processing $filepath ${IDX_FILE}/${NUM_FILES}..."
      { ${SCRIPT_PATH} --tiff "$filepath" --channels ${CH} --slices ${SL} ${ARGS} --out "${OUT}/${SCRIPT_NAME}.pickle" 2>&1; } >"${OUT}/${SCRIPT_NAME}.log" &
      [ $CH -eq 0 ] && cp "$TMP/metadata.json" "${OUT}/"
      if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
    done
    if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
  done
  wait
)

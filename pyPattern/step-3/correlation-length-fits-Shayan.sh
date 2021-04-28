#!/bin/bash
# based on https://unix.stackexchange.com/a/436713

source ../common.sh

SCRIPT_NAME=correlation-length
SCRIPT_PATH=./${SCRIPT_NAME}-fits.py
BASE_IN=../step-2/experiment
BASE_OUT=./experiment

[ -d "${BASE_OUT}" ] || mkdir -p "${BASE_OUT}"
BASEDIR=${BASE_OUT}

FILES=$(find "${BASE_IN}" -name "${SCRIPT_NAME}.pickle")
NUM_FILES=$(echo "$FILES" | wc -l)
IDX_FILE=0

echo "$FILES" | (
  while read FILEPATH; do
  
    IDX_FILE=$(( IDX_FILE + 1 ))
    TMP=$(dirname "$FILEPATH")
    CASE_PATH=${TMP##${BASE_IN}/}
    #CASE_PATH=$(echo "$CASE_PATH" | tr -s ' ' '_' | tr -s '/' '_') 

    OUTDIR="${BASEDIR}/${CASE_PATH}"
    [ -d "${OUTDIR}" ] || mkdir -p "${OUTDIR}"
    
    for m in scldblexp; do #exp dblexp
      echo "Processing ${FILEPATH} => fitting ${m}..."
      { ${SCRIPT_PATH} --data "${FILEPATH}" "${TMP}/metadata.json" --out "${OUTDIR}/${SCRIPT_NAME}-fits-${m}.pickle" --model ${m} 2>&1; } >"${OUTDIR}/${SCRIPT_NAME}-${PREFIX}-${m}.log" &

      if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
    done
    if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
  done
  if [[ $(jobs -r -p | wc -l) ]]; then wait -n; fi
)

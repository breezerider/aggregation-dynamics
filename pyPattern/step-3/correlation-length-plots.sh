#!/bin/bash
# based on https://unix.stackexchange.com/a/436713

source ../common.sh

SCRIPT_NAME=correlation-length
SCRIPT_PATH=./${SCRIPT_NAME}-plots.py
BASE_IN=./experiment
BASE_OUT=./

[ -d "${BASE_OUT}/" ] || mkdir -p "${BASE_OUT}/"
BASEDIR=${BASE_OUT}/

m=scldblexp
FILES=$(find "${BASE_IN}" -name "${SCRIPT_NAME}-fits-${m}.pickle")

#experiment overview
SUBDIRS=("DMSO/" "Taxol 12.5uM/" "Taxol 25 uM/" "Taxol 50 uM/" )
REGION=("75,135" "30,175" "75,225" "75,225" )

ARGS=()
for ((j = 0; j < ${#SUBDIRS[@]}; j++)); do
  s=${SUBDIRS[$j]}
  suffix=$(echo "$s" | sed -e 's#/#_#g')
  echo $s
  touch "plots-files_${suffix}.dat"

  for ((i = 0; i < ${#FILES[@]}; i++)); do
    f=${FILES[$i]}
    if [ -z "${f##*$s*}" ]; then
      echo "$f">>"plots-files_${suffix}.dat"
    fi
  done
  
  [ -n "${REGION[$j]}" ] && echo ":region ${REGION[$j]}">>"plots-files_${suffix}.dat"

  ARGS+=("--data" "plots-files_${suffix}.dat" "${suffix}")
done

${SCRIPT_PATH} "${ARGS[@]}" --out ${BASEDIR}/overview-experiment_${m}.png
${SCRIPT_PATH} "${ARGS[@]}" --region --out ${BASEDIR}/overview-experiment_roi_${m}.png
#${SCRIPT_PATH} "${ARGS[@]}" --avgplot --maximum 2 --out ${BASEDIR}/overview-experiment_avg_${m}.png

for ((j = 0; j < ${#SUBDIRS[@]}; j++)); do
  s=${SUBDIRS[$j]}
  suffix=$(echo "$s" | sed -e 's#/#_#g')
  rm "plots-files_${suffix}.dat"
done

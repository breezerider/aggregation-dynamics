#!/bin/bash
# based on https://unix.stackexchange.com/a/436713

source ../common.sh

METADATA_SCRIPT=../metadata/get-metadata-file.py
METADATA_PATH=../metadata/json

SCRIPT_NAME=cutin-tiff
SCRIPT_PATH=./${SCRIPT_NAME}.py
BASE_OUT=./experiment/

DATA_PATHS=/path/to/data
DATA_FILENAMES=(
  # DMSO
  "DMSO/20201018/MAX_Pos005_S001.tif" "DMSO/20201018/MAX_Pos022_S001.tif" "DMSO/20201018/MAX_Pos027_S001.tif"
  "DMSO/20201227/Max_12-1.tif" "DMSO/20201227/Max_17.tif" "DMSO/20201227/Max_18.tif" "DMSO/20201227/Max_22-1.tif" "DMSO/20201227/Max_25-1.tif"
  #"DMSO/MAX_Pos028_S001.tif"
  # Taxol 12.5uM
  "Taxol 12.5uM/20201018/MAX_Taxol R2.lif - Position 5.tif" "Taxol 12.5uM/20201018/MAX_Taxol R2.lif - Position 9.tif" "Taxol 12.5uM/20201018/MAX_Taxol R2.lif - Position 14.tif"
  #"Taxol 12.5uM/MAX_Taxol R2.lif - Position 15.tif" 
  "Taxol 12.5uM/20201018/MAX_Taxol R2.lif - Position 19.tif"  "Taxol 12.5uM/20201018/MAX_Taxol R2.lif - Position 20.tif"
  "Taxol 12.5uM/20201227/Max_13-1.tif" "Taxol 12.5uM/20201227/Max_17-1.tif" 
  "Taxol 12.5uM/20201227/Max_24-1.tif" "Taxol 12.5uM/20201227/Max_25-2.tif" "Taxol 12.5uM/20201227/Max_26-1.tif" "Taxol 12.5uM/20201227/Max_27.tif"
  # Taxol 25uM
  "Taxol 25 uM/20201018/MAX_Pos007_S001.tif" "Taxol 25 uM/20201018/MAX_Pos013_S001.tif" "Taxol 25 uM/20201018/MAX_Pos016_S001.tif" "Taxol 25 uM/20201018/MAX_Pos021_S001.tif"
  "Taxol 25 uM/20201227/Max_8-1.tif" "Taxol 25 uM/20201227/Max_9-1.tif" "Taxol 25 uM/20201227/Max_10-1.tif" "Taxol 25 uM/20201227/Max_12-1.tif" "Taxol 25 uM/20201227/Max_13-1.tif" "Taxol 25 uM/20201227/Max_15-1.tif"
  # Taxol 50uM
  "Taxol 50 uM/20201018/MAX_Taxol.lif - Position 1.tif" "Taxol 50 uM/20201018/MAX_Taxol.lif - Position 13.tif"
  "Taxol 50 uM/20201227/Max_5-1.tif" "Taxol 50 uM/20201227/Max_6.tif" "Taxol 50 uM/20201227/Max_7-1.tif" 
  "Taxol 50 uM/20201227/Max_8-1.tif" "Taxol 50 uM/20201227/Max_11-1.tif" "Taxol 50 uM/20201227/Max_14-2.tif"
  )

[ -d "${BASE_OUT}" ] || mkdir -p "${BASE_OUT}"

SL=0
CH=0

NUM_FILES=${#DATA_FILENAMES[@]}
FILE_NO=0

for ((i = 0; i < ${#DATA_FILENAMES[@]}; i++)); do
  FILENAME=${DATA_FILENAMES[$i]}
  METAFILE=$(${METADATA_SCRIPT} "$FILENAME")
  OUT=${BASE_OUT}/${FILENAME%%.tif*}
  FILE_NO=$((FILE_NO+1))
  
  ARGS="--cutin"
  [ -z "${FILENAME##*12.5*}" -o -z "${FILENAME##*50*}" ] && ARGS="--cutin --segmentation 2"
  [ -z "${FILENAME##*50*}" -a -z "${FILENAME##*Position 1*}" ] && ARGS="--cutin --segmentation 1"
  [ -z "${FILENAME##*12.5*}" -a -z "${FILENAME##*Position 19*}" ] && ARGS="--cutin --segmentation 1"
  [ -z "${FILENAME##*12.5*}" -a -z "${FILENAME##*Position 9*}" ] && ARGS="--cutin --segmentation 1"
  
  [ -z "${FILENAME##*12.5*}" -a -z "${FILENAME##*20201227*}" ] && ARGS="--cutin --segmentation 1"
  [ -z "${FILENAME##*12.5*}" -a -z "${FILENAME##*20201227*}" -a -n "${FILENAME##*13*}" ] && ARGS="--cutin --segmentation 0"
  [ -z "${FILENAME##*12.5*}" -a -z "${FILENAME##*20201227*}" -a -n "${FILENAME##*17*}" ] && ARGS="--cutin --segmentation 0"
  [ -z "${FILENAME##*50*}" -a -z "${FILENAME##*20201227*}" ] && ARGS="--cutin --segmentation 0"

  echo "Processing $FILENAME (${FILE_NO}/${NUM_FILES})..."
  [ -d "${OUT}" ] || mkdir -p "${OUT}"
  [ -f "${OUT}/${SCRIPT_NAME}-small.tiff" ] && continue
  {
    set -x;
    ${SCRIPT_PATH} --tiff "${DATA_PATHS}/${FILENAME}" --channels ${CH} --slices ${SL} --out "${OUT}/${SCRIPT_NAME}-small.tiff" ${ARGS} 2>&1;
    #${SCRIPT_PATH} --tiff "${DATA_PATHS}/${FILENAME}" --channels ${CH} --slices ${SL} --out "${OUT}/${SCRIPT_NAME}-full.tiff" ${ARGS} --full 2>&1;
  } >"${OUT}/${SCRIPT_NAME}.log" &
  cp "${METADATA_PATH}/${METAFILE}" "${OUT}/metadata.json"
  if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
done;
wait

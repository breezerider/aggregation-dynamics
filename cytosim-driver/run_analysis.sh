#!/bin/bash

if [ $# -lt 1 ]; then
  echo "Error: at least one argument is required"
  exit 1
fi

[ -n "${CYM_STATS}" ] && CYM_STATS_ESC=$(echo "$CYM_STATS" | tr ',' '-')
#[ -z "${CYM_STATS}" ] && { echo "No operation is set. Exiting"; exit 1; }
[ -z "${CYM_CHANNELS}" ] || exit 1

# loop over input arguments (log files)
for f in $@; do
  F=$(realpath "$f")
  if [ ! -f "${F}" ]; then
    echo "'${F}' is not a valid log file name."
    continue
  fi

  for d in $(cat "$F"); do
    
    INVALID=

    # process the path
    tmp=${d%/*};
    CASE_ID=${tmp##*/}
    SIM_ID=${d##*/}

    if [ -z "${tmp}" -o -z "${SIM_ID}" -o -z "${CASE_ID}" ]; then
      echo "Failed to extract info from path $d"
      continue
    fi

    FILE_NAME=${CASE_ID}_${SIM_ID};

    # check if TIFF file is already present
    if [ -n "$CYM_STATS" ]; then
      rm "$d/*.pickle"
      if [ -f  "$d/*.pickle" ]; then
        echo "'$d/${FILE_NAME}*.pickle' found. Skipping this time course..."
        INVALID=1
      fi     
    else
      if [ -f  "$d/$FILE_NAME.tiff" ]; then
        echo "'$d/$FILE_NAME.tiff' found. Skipping this time course..."
        INVALID=1
      fi
    fi

    # test if it's a directory
    if [ ! -d "${d}" ]; then
      echo "$d is not a valid directory path."
      INVALID=1
    fi
    # test if it contains the required simulation files
    if [ ! -f "${d}/objects.cmo" ]; then
      echo "objects.cmo is missing in $d. Skipping this time course..."
      INVALID=1
    fi
    if [ ! -f "${d}/properties.cmo" ]; then
      echo "properties.cmo is missing in $d. Skipping this time course..."
      INVALID=1
    fi

    [ -n "$INVALID" ] && continue

    # get number of frames
    if [ -f "${d}/${CASE_ID}.cym" ]; then
      NUM_FRAMES=0
      for n in $(cat "${d}/${CASE_ID}.cym" | grep 'nb_frames' | sed -e 's/[^0-9]*//g'); do
        NUM_FRAMES=$(( NUM_FRAMES + n ))
      done
      echo "$FILE_NAME has ${NUM_FRAMES} frames"
    else
      echo "Warning: Cytosim model file (${CASE_ID}.cym) not found in $d. Skipping this time course..."
      continue
    fi

    # process the time course
    echo "Processing $d...";
    FRAMES=$(seq -s, 0 $FRAME_STEP $NUM_FRAMES)
    NUM_FRAMES=$(echo "$FRAMES" | tr -s ',' '\n' | wc -l)
    NUM_CHANNELS=$(echo "$CYM_CHANNELS" | tr -s ',' '\n' | wc -l)
    echo "# channels = $NUM_CHANNELS; # frames = $NUM_FRAMES; # movie frames to be produced: $((NUM_FRAMES * NUM_CHANNELS))"

    if [ -n "$CYM_STATS" ]; then
      $SHELL -c "${HOME}/pyCytosim/import_data.py --simdir $d --op ${CYM_STATS} --out $d/${FILE_NAME} --frames $FRAMES >$d/stats.log";
    else
      echo "xvfb-run -a -s '-screen 0 1024x1024x24' ${HOME}/pyCytosim/make_tiff.py --simdir $d --channels $CYM_CHANNELS --out $d/$FILE_NAME.tiff --frames $FRAMES >$d/movie.log"
      $SHELL -c "xvfb-run -a -s '-screen 0 1024x1024x24' ${HOME}/pyCytosim/make_tiff.py --simdir $d --channels $CYM_CHANNELS --out $d/$FILE_NAME.tiff --frames $FRAMES >$d/movie.log"; 
    fi
  done
done

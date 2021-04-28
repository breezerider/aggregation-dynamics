#!/bin/bash

# deterimine the script location
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# check if configuration is available
[ -f "$DIR/cytosim-driver.conf" ] && source "$DIR/cytosim-driver.conf"

# check if cytosim is on the path
if [ -n "$CYTOSIM_PATH" ]; then
  [ -z "$CYTOSIM_PATH" ] &&  CYTOSIM_PATH=${HOME}/.\${DISTRIB_CODENAME}/bin
  TEST_CYTOSIM_PATH=$(eval "echo $CYTOSIM_PATH")
  for s in sim report play; do
    if [ ! -e "$TEST_CYTOSIM_PATH/$s" -o ! -x "$TEST_CYTOSIM_PATH/$s" ]; then
      echo "invalid cytosim path '$TEST_CYTOSIM_PATH': one of the executables ($s) is missing or the executable bit is not set";
      exit 1;
    fi
  done
else
  for s in sim report play; do
    if [ -z "$(command -v $s)" ]; then
      echo "cytosim is not on the path. Trying to load via 'module load cytosim'";
      module load cytosim #|| exit 1
      break
    fi
  done
fi

# output directory for model files
if [ ! -d "$CYM_OUTDIR" ]; then
  CYM_OUTDIR=$DIR/submitted
  mkdir -p $CYM_OUTDIR
fi

# output directory  for data
[ -d "${JOBID_DIR}" ] || mkdir -p "${JOBID_DIR}"
[ -d "${STORE_DIR}/.logs" ] || mkdir -p "${STORE_DIR}/.logs"

join_by() { local IFS="$1"; shift; echo "$*"; }

urldecode() { printf "%b\n" "$(sed 's/+/ /g;s/%\(..\)/\\x\1/g;')"; }

cym_usage() {
  prog="${0##*/}"
  cat >&2 <<EOF
  CYM generator options

  +y, ++yes
  +t, ++test
  +n, ++nucleation
  +f, ++fibers-only
  +e, ++exponetial-fiber-length
  +g, ++grow-fiber
  +x, ++catastrophy-factor <floating_point_number>
  +l, ++side-len <floating_point_number>[x<floating_point_number>]
  +w, ++wave <num_frames> <num_sections> <num_frames>
  +b, ++burn-in <num_frames>
  +d, ++delete-fiber <percentage> <num_frames>
  +r, ++frames <num_frames>
  +o, ++motor-factor <number>
  +p, ++positive-motor <percentage>
  +m, ++sticky-motor <percentage>
  +s, ++sticky <percentage>
  +a, ++passive-crosslinkers <percentage>
  +v, ++fiber-viscosity <floating_point_number>
  +q, ++fiber-quantity-factor <floating_point_number>
  +c, ++conf-id <conf_id>

EOF
}

_is_float() { [[ "$1" =~ ^[[:digit:].e+-]+$ ]] && return 0; return 1; }

_handle_cym_option () {
  opt=
  opt_sz=1
  case "$1" in
    +y|++yes)
      CYM_YES=true
      ;;
    +t|++test)
      CYM_TEST=true
      ;;
    +n|++nucleation)
      CYM_NUCLEATION=true
      ;;
    +f|++fibers-only)
      CYM_FIBERONLY=true
      ;;
    +e|++exponetial-fiber-length)
      CYM_EXPFIBERLEN=true
      ;;
    +g|++grow-fiber)
      CYM_GROWFIBER=true
      ;;
#     +u|++bounding-frame)
#       CYM_BOUNDINGBOX=true
#       ;;
    +x|++catastrophy-factor)
      if _is_float $2; then
        CYM_CATASTROPHYFACTOR=$2
      else
        echo "invalid catastrophy factor \"$2\", must be a positive floating point number"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +l|++side-len)
      if [ -n "$2" ]; then
        if [ -z "${2##*x*}" ]; then
          CYM_SHORTSIDE=${2%%x*}
          CYM_LONGSIDE=${2##*x}
        elif [ "$2" -eq "$2" ]; then
          CYM_SHORTSIDE=$2
          CYM_LONGSIDE=$2
        else
          echo "invalid side length \"$2\""
          cym_usage
          exit 1
        fi
      fi
      opt_sz=2
      ;;
    +w|++wave)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" -a -n "$3" -a "$3" -eq "$3" -a "$3" -gt "0" -a -n "$4" -a "$4" -eq "$4" -a "$4" -gt "0" ]; then
        CYM_WAVE_BEGIN=$2
        CYM_WAVE_SECTIONS=$3
        CYM_WAVE_DELAY=$4
      else
        echo "invalid wave begin time "$2", number of wave sections "$3" or wave activation delay "$4", all must be positive integers"
        cym_usage
        exit 1
      fi
      opt_sz=4
      ;;
    +b|++burn-in)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" ]; then
        CYM_BURNIN=$2
      else
        echo "invalid burn-in number of frames \"$2\", must be an positive integer"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +d|++delete-fiber)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" -a "$2" -le "100" -a -n "$3" -a "$3" -eq "$3" ]; then
        CYM_DELETEFIBER=$2
        CYM_DELETEFIBER_FRAMES=$3
      else
        echo "invalid delete fibers percentage \"$2\", must be an integer in range (0; 100] OR invalid frame number \"$3\", must be an integer. Zero is treated specially"
        cym_usage
        exit 1
      fi
      opt_sz=3
      ;;
    +r|++frames)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" ]; then
        CYM_FRAMES=$2
        #echo "frames ${CYM_FRAMES}"
      else
        echo "invalid number of frames \"$2\", must be a positive integer"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +o|++motor-factor)
      if _is_float $2; then
        CYM_MOTORFACTOR=$2
        echo "motor factor ${CYM_MOTORFACTOR}"
      else
        echo "invalid motor factor \"$2\", must be a float"
        cym_usage
        exit 1
      fi
      opt_sz=2 
      ;;
    +p|++positive-motor)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -ge "0" -a "$2" -le "100" ]; then
        CYM_POSITIVEMOTOR=$2
      else
        echo "invalid positive motor percentage \"$2\", must be an integer in range (0; 100)"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +m|++sticky-motor)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" -a "$2" -lt "100" ]; then
        CYM_STICKYMOTOR=$2
      else
        echo "invalid sticky motor wall percentage \"$2\", must be an integer in range (0; 100)"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +s|++sticky)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" ]; then
        CYM_STICKY=$2
      else
        echo "invalid sticky wall density \"$2\", must be a positive integer"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +a|++passive-crosslinks)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" ]; then
        CYM_CROSSLINKS=$2
      else
        echo "invalid passive crosslinks number \"$2\", must be a positive integer"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +v|++fiber-viscosity)
      if _is_float $2; then
        CYM_FIBER_VISCOSITY=$2
      else
        echo "invalid medium viscosity for fibers \"$2\", must be a positive float"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    +q|++fiber-quantity-factor)
      if _is_float $2; then
        CYM_MTNUMBERFACTOR=$2
      else
        echo "invalid fiber factor \"$2\", must be a float"
        cym_usage
        exit 1
      fi
      opt_sz=2 
      ;; 
    +c|++conf-id)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt "0" -a "$2" -lt "37" ]; then
        CYM_CONFID=$2
      else
        echo "invalid configuration \"$2\", must be an integer in range 1..36"
        cym_usage
        exit 1
      fi
      opt_sz=2
      ;;
    '?')
      echo "Unrecognized option: -$OPTARG" >&2
      exit 2
      ;;
    *)
      echo "Unrecognized option: \"$1\"" >&2
      exit 2
      ;;
  esac 
}

generate_cym() {
  while [ $# -gt 0 ]; do
    if [ "${1#+}" == "$1" ]; then
      shift
      continue
    fi
    case "$1" in
      ++?*)  # long option
        _handle_cym_option "$@"
        ;;
      +?*)  # one or more short options
        OPTIND=1
        while getopts :tnsc opt -"${1#+}"; do
          _handle_cym_option "$@"
        done
        ;;
      *)
        echo "Unrecognized option: $1" >&2
        exit 2
        ;;
    esac
    while ((opt_sz--)); do
      shift
    done
  done

  if ! [ -n "$CYM_CONFID" ]; then
    echo "error: configuration id is not defined"
    exit 1
#  elif [ "$CYM_CONFID" -gt "36" -o "$CYM_CONFID" -lt "1" ]; then
#    echo "conf id must be an integer in range 1..36"
#    exit 1
  fi

  if [ -n "${CYM_NUCLEATION}" ]; then
    [ -n "${CYM_EXPFIBERLEN}" ] && echo "WARNING: nucleation is enabled, fixed  exponetial fiber length cannot be enforced"
    [ -n "${CYM_GROWFIBER}" ] && echo "WARNING: nucleation is enabled, fiber growth cannot be enforced"
    unset CYM_EXPFIBERLEN
    unset CYM_GROWFIBER
  fi

  if [ -n "${CYM_FIBERONLY}" ]; then
    [ -n "${CYM_STICKYMOTOR}" ] && echo "WARNING: fiber only simulation, sticky motors are excluded"
    unset CYM_STICKYMOTOR
  fi

  if [ -n "${CYM_WAVE_SECTIONS}" -a -z "${CYM_STICKYMOTOR}" ]; then
    echo "WARNING: activation wave ignored without sticky motors"
    unset CYM_WAVE_SECTIONS
  fi

  CYM_FRAMES=${CYM_FRAMES:-7200}
  CYM_CONFNAME='' #'fig5a-left-'
  CYM_CONFNAME=$(printf "${CYM_CONFNAME}%04d" $CYM_CONFID)
  [ -n "${CYM_TEST}" ] && CYM_CONFNAME="${CYM_CONFNAME}_tst"
  [ -n "${CYM_STICKY}" ] && CYM_CONFNAME="${CYM_CONFNAME}_stk"
  [ -n "${CYM_BOUNDINGBOX}" ] && CYM_CONFNAME="${CYM_CONFNAME}_bbx"
  [ -n "${CYM_CROSSLINKS}" ] && CYM_CONFNAME="${CYM_CONFNAME}_crs"
  [ -n "${CYM_STICKYMOTOR}" ] && CYM_CONFNAME="${CYM_CONFNAME}_stm"
  [ -n "${CYM_POSITIVEMOTOR}" ] && CYM_CONFNAME="${CYM_CONFNAME}_pls"
  [ -n "${CYM_MOTORFACTOR}" ] && CYM_CONFNAME="${CYM_CONFNAME}_mot"
  [ -n "${CYM_NUCLEATION}" ] && CYM_CONFNAME="${CYM_CONFNAME}_nuc"
  [ -n "${CYM_EXPFIBERLEN}" ] && CYM_CONFNAME="${CYM_CONFNAME}_exp"
  [ -n "${CYM_MTNUMBERFACTOR}" ] && CYM_CONFNAME="${CYM_CONFNAME}_mts"
  [ -n "${CYM_FIBERONLY}" ] && CYM_CONFNAME="${CYM_CONFNAME}_fib"
  [ -n "${CYM_GROWFIBER}" ] && CYM_CONFNAME="${CYM_CONFNAME}_grow"
  [ -n "${CYM_DELETEFIBER}" ] && CYM_CONFNAME="${CYM_CONFNAME}_del"
  [ -n "${CYM_FIBERONLY}" ] && CYM_CONFNAME="${CYM_CONFNAME}_fib"
  [ -n "${CYM_FIBER_VISCOSITY}" ] && CYM_CONFNAME="${CYM_CONFNAME}_vis"
  [ -n "${CYM_WAVE_SECTIONS}" ] && CYM_CONFNAME="${CYM_CONFNAME}_wav"
  if [ -z "${CYM_SHORTSIDE}" -o -z "${CYM_LONGSIDE}" ]; then
    CYM_SHORTSIDE=20
    CYM_LONGSIDE=20
  else
    CYM_CONFNAME="${CYM_CONFNAME}_${CYM_SHORTSIDE}x${CYM_LONGSIDE}"
  fi
  CYM_FILENAME="${CYM_CONFNAME}.cym"
  CYM_FILEPATH=$(mktemp "${CYM_OUTDIR}/${CYM_FILENAME}_XXXXXX")

  MT_NUMBER=2560
  MOTOR_NUMBER=(1280 2560 5120 10240 20480 40960)
  GROWING_SPEED=(0.005 0.01 0.015 0.02 0.025 0.03)
  CATASTROPHE_RATE=(0.002 0.004 0.006 0.008 0.01 0.012)

  IDX_GS=$(( (CYM_CONFID - 1) / 6))
  IDX_MN=$(( (CYM_CONFID - 1) % 6))
  GSPEED=${GROWING_SPEED[$IDX_GS]}
  CRATE=${CATASTROPHE_RATE[$IDX_GS]}
  MOTORNUM=${MOTOR_NUMBER[$IDX_MN]}
  [ -n "${CYM_MTNUMBERFACTOR}" ] && MT_NUMBER=$(( MT_NUMBER * CYM_MTNUMBERFACTOR ))
  [ -n "${CYM_MOTORFACTOR}" ] && MOTORNUM=$(( MOTORNUM * CYM_MOTORFACTOR ))
  [ -n "${CYM_CATASTROPHYFACTOR}" ] && CRATE=$(echo "scale=8; x = $CRATE * $CYM_CATASTROPHYFACTOR; if (length (x) == scale (x) && x != 0) { if (x < 0) print \"-\",0,-x else print 0,x } else print x" | bc)

  [ -n "${CYM_TEST}" ] && echo "\tTEST CONFIGURATION!"
  echo -n "Configuration ${CYM_CONFNAME} ("$(echo 2*${CYM_SHORTSIDE} | bc)"x"$(echo 2*${CYM_LONGSIDE} | bc)"um domain), produce ${CYM_FRAMES} frames with: $MT_NUMBER MTs with growing_speed=$GSPEED and catastrophe_rate = $CRATE; $MOTORNUM motors"
  [ -n "${CYM_MOTORFACTOR}" ] && echo -n " with motor factor ${CYM_MOTORFACTOR}"
  [ -n "${CYM_POSITIVEMOTOR}" ] && echo -n " and ${CYM_POSITIVEMOTOR}% plus-directed motor"
  [ -n "${CYM_FIBER_VISCOSITY}" ] && echo -n "; with apparent fiber viscosity ${CYM_FIBER_VISCOSITY} pN.s/um^2 (Pa.s)"
  echo -n ";"
  [ -n "${CYM_BURNIN}" ] && echo -n " ${CYM_BURNIN} frames for equilibration;"
  [ -n "${CYM_STICKY}" ] && echo -n " ${CYM_STICKY}% sticky sites"
  [ -n "${CYM_BOUNDINGBOX}" ] && echo -n " at each side of the abounding box"
  [ -n "${CYM_STICKY}" -a  -n "${CYM_BOUNDINGBOX}" ] && echo -n ";"
  [ -n "${CYM_STICKYMOTOR}" ] && echo -n " ${CYM_STICKYMOTOR}% wall-bound motors;"
  [ -n "${CYM_NUCLEATION}" ] && echo -n " nucleation;"
  [ -n "${CYM_EXPFIBERLEN}" ] && echo -n " fixed exponetial fiber length;"
  [ -n "${CYM_FIBERONLY}" ] && echo -n " fibers only;"
  [ -n "${CYM_GROWFIBER}" ] && echo -n " grow fibers; "
  [ -n "${CYM_DELETEFIBER}" ] && echo -n " delete ${CYM_DELETEFIBER}% fibers after ${CYM_DELETEFIBER_FRAMES} frames;"
  [ -n "${CYM_WAVE_SECTIONS}" ] && echo -n " motor activation wave after ${CYM_WAVE_BEGIN} frames with ${CYM_WAVE_SECTIONS} steps delayed by ${CYM_WAVE_DELAY} frames each;"
  echo " written to ${CYM_FILEPATH}"
  if [ ! -n "${CYM_YES}" ]; then
    while true; do
      read -p "Proceed? [y]/n " yn
      case $yn in
        [Yy]* ) break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
      esac
    done
  fi

  if [ -n "${CYM_FIBER_VISCOSITY}" ]; then
    FIBER_VISCOSITY="${CYM_FIBER_VISCOSITY}"
  else
    FIBER_VISCOSITY="0.2"
  fi

  cat >$CYM_FILEPATH <<EOF
% Aster dynamics ${CYM_CONFNAME}
% generated with ${ARGS[@]}

set simul sim
{
  time_step = 0.01
  viscosity = 0.2
  steric = 1, 50
  display = { style=2; tile=1; line_width=2; point_size=2; label=(${CYM_CONFNAME} $(echo 2*${CYM_SHORTSIDE} | bc)x$(echo 2*${CYM_LONGSIDE} | bc)um - );}
}

set space cell
{
  geometry = periodic $CYM_SHORTSIDE $CYM_LONGSIDE 0.2
}

set fiber microtubule
{
  rigidity         = 30
  segmentation     = 1
  viscosity        = $FIBER_VISCOSITY

  activity         = classic
  confine          = inside, 100

  growing_speed    = $GSPEED
  shrinking_speed  = -0.5
  catastrophe_rate = $CRATE

  steric           = 1, 0.05

  rescue_rate      = 0
  growing_force    = 1.67
  persistent       = 0
  min_length       = 0.02
  display          = { style=line; color=white; }
}

set hand kinesin
{
  binding = 5, 0.1
  unbinding = 0.1, 5
  %unbinding_rate_end = 0.1

  hold_growing_end = 1
  bind_also_end = 1

  activity = move
  max_speed = 0.03
  stall_force = 5
  display = { size=2; color=red; visible=1; }
}

set hand dynein
{
  binding = 5, 0.1
  unbinding = 0.1, 5
  %unbinding_rate_end = 0.1

  hold_growing_end = 1
  bind_also_end = 1

  activity = move
  max_speed = -0.03
  stall_force = 5
  display = { size=2; color=green; visible=1; }
}

set hand dyneininactive
{
  binding = 0.5, 0.1
  unbinding = 0.1, 5
  %unbinding_rate_end = 0.1

  hold_growing_end = 1
  bind_also_end = 1

  activity = move
  max_speed = -0.03
  stall_force = 5
  display = { size=2; color=green; visible=1; }
}

set couple motor
{
  hand1 = kinesin
  hand2 = kinesin
  activity = bridge

  length = 0.08
  stiffness = 100
  fast_diffusion = 1
  diffusion = 10
}

set couple minusmotor
{
  hand1 = dynein
  hand2 = dynein
  activity = bridge

  length = 0.08
  stiffness = 100
  fast_diffusion = 1
  diffusion = 10
}

set couple minusmotorinactive
{
  hand1 = dyneininactive
  hand2 = dyneininactive
  activity = bridge

  length = 0.08
  stiffness = 100
  fast_diffusion = 1
  diffusion = 10
}

set hand nucleator
{
  unbinding = 0, 3
  activity = nucleate
  nucleate = 0.1, microtubule, ( fiber_length=0.025; plus_end=grow; )
  display = { size=2; color=green; visible=1; }
}

set single creator
{
  hand = nucleator
  diffusion = 1
}

set hand binder
{
  binding_rate = 10
  binding_range = 0.1
  bind_only_end = plus_end
  bind_end_range = 0.1
  unbinding_rate = 1
  unbinding_force = 1.5
  display = ( color=blue; size=7; width=7; visible=1; )
}

set single grafted
{
  hand = binder
  stiffness = 1
  activity = fixed
}

set single graftedmotor
{
  hand = dynein
  stiffness = 100
  activity = fixed
}

set couple crosslink
{
  hand1 = binder
  hand2 = binder
  activity = bridge

  length = 0.08
  stiffness = 100
  fast_diffusion = 1
  diffusion = 10
}

% initialize the simulation
EOF

  if [ -n "$CYM_IMPORT" ]; then
    # TODO import frame
    echo "error: import not implemented"
    exit 1
  else
    echo "new space cell" >>$CYM_FILEPATH

    if [ -n "$CYM_NUCLEATION" ]; then
      echo "new $MT_NUMBER single creator" >>$CYM_FILEPATH
      [ -n "${CYM_DELETEFIBER}" -a "${CYM_DELETEFIBER_FRAMES}" -eq "0" ] && echo "delete $(( CYM_DELETEFIBER * MT_NUMBER / 100 )) creator" >>$CYM_FILEPATH
    else
      local CYM_FIBERPROPS=()
      [ -n "$CYM_EXPFIBERLEN" ] && CYM_FIBERPROPS+=("length = 2.5, exponential")
      [ -n "$CYM_GROWFIBER" ] && CYM_FIBERPROPS+=("plus_end = grow" "persistent = 1" "rescue_rate = 0.1")

      if [ "${#CYM_FIBERPROPS[@]}" -gt "0" ]; then
        CYM_FIBERPROPS=$(join_by \; "${CYM_FIBERPROPS[@]}")
        CYM_FIBERPROPS=" { ${CYM_FIBERPROPS} }"
      else
        CYM_FIBERPROPS=""
      fi
      echo "new $MT_NUMBER fiber microtubule ${CYM_FIBERPROPS}" >>$CYM_FILEPATH
      [ -n "${CYM_DELETEFIBER}" ] && [ "${CYM_DELETEFIBER_FRAMES}" -eq "0" ] && echo "delete $(( CYM_DELETEFIBER * MT_NUMBER / 100 )) microtubule" >>$CYM_FILEPATH
    fi

    _run_simul() {
      local FRAMES=$1
      cat >>$CYM_FILEPATH <<EOF

run $(( FRAMES * 125 )) simul *
{
  nb_frames = $FRAMES
}
EOF
    }

    if [ -z "$CYM_NUCLEATION" -a -z "${CYM_BURNIN}" ]; then
      _run_simul 10
    elif [ -n "${CYM_BURNIN}" ]; then
      _run_simul ${CYM_BURNIN}
    fi

    if [ -n "$CYM_STICKY" ]; then
      for (( curr_sec=1; curr_sec<=11; curr_sec+=2 )); do
        local curr_pos=$(echo "scale=2; $CYM_SHORTSIDE * (1.0 - 2.0 * (${curr_sec}.0 - 1.0) / 11.0 )" | bc)
        local curr_motors=$(( CYM_STICKY * MT_NUMBER / 100 ))
        local zone_width="1.0"
        echo "new ${curr_motors} single grafted { position = line $(( 2 * CYM_SHORTSIDE )) $zone_width turn degree 90 at $curr_pos 0.0; mark = $curr_sec; }" >>$CYM_FILEPATH
      done
    
      #echo "new $(( CYM_STICKY * MT_NUMBER / 100 )) single grafted ( line $(( 2 * CYM_SHORTSIDE )) 1.0 at 0.0 ${CYM_LONGSIDE} )" >>$CYM_FILEPATH
      #if [ -n "$CYM_BOUNDINGBOX" ]; then
        #echo "new $(( CYM_STICKY * MT_NUMBER / 100 )) single grafted ( line $(( 2 * CYM_SHORTSIDE )) 1.0 turn degree 90 at ${CYM_LONGSIDE} 0.0 )" >>$CYM_FILEPATH
	#echo "new $(( CYM_STICKY * MT_NUMBER / 100 )) single grafted ( line $CYM_SHORTSIDE 0.1 at $CYM_LONGSIDE 0 turn degree 90 )" >>$CYM_FILEPATH
	#echo "new $(( CYM_STICKY * MT_NUMBER / 100 )) single grafted ( line $CYM_SHORTSIDE 0.1 at -$CYM_LONGSIDE 0 turn degree 90 )" >>$CYM_FILEPATH
      #fi
    fi

    if [ -n "$CYM_CROSSLINKS" ]; then
      echo "new $(( CYM_CROSSLINKS )) couple crosslink" >>$CYM_FILEPATH
      _run_simul ${CYM_BURNIN}
    fi

    if [ -z "${CYM_FIBERONLY}" ]; then
      local FREEMOTORS=${MOTORNUM}
      if [ -n "${CYM_STICKYMOTOR}" ]; then
        local BOUNDMOTORS=$(( CYM_STICKYMOTOR * FREEMOTORS / 100 ))
        FREEMOTORS=$(( FREEMOTORS - BOUNDMOTORS ))
        if [ -z "${CYM_WAVE_SECTIONS}" ]; then
          echo "new ${BOUNDMOTORS} graftedmotor ( line $(( 2 * CYM_SHORTSIDE )) 0.1 at 0 $CYM_LONGSIDE )" >>$CYM_FILEPATH
        else
          local curr_motors=$(( BOUNDMOTORS / CYM_WAVE_SECTIONS ))
          local rest_motors=$(( BOUNDMOTORS - curr_motors * CYM_WAVE_SECTIONS ))
          local zone_width=$(echo "scale=2; $CYM_SHORTSIDE * 2.0 / ${CYM_WAVE_SECTIONS}.0" | bc)
          for (( curr_sec=1; curr_sec<=$CYM_WAVE_SECTIONS; curr_sec++ )); do
            local curr_pos=$(echo "scale=2; $CYM_SHORTSIDE * (1.0 - 2.0 * (${curr_sec}.0 - 1.0) / ${CYM_WAVE_SECTIONS}.0 )" | bc)
            [ $curr_sec -eq ${CYM_WAVE_SECTIONS} ] && curr_motors=$(( curr_motors + rest_motors ))
            echo "new ${curr_motors} couple minusmotorinactive { position = line $(( 2 * CYM_SHORTSIDE )) $zone_width turn degree 90 at $curr_pos 0.0; mark = $curr_sec; }" >>$CYM_FILEPATH
          done
        fi
      fi

      if [ -n "${CYM_POSITIVEMOTOR}" ]; then
        PLUSFREEMOTORS=$(( CYM_POSITIVEMOTOR * FREEMOTORS / 100 ))
        MINUSFREEMOTORS=$(( (100 - CYM_POSITIVEMOTOR) * FREEMOTORS / 100 ))
        [ "${PLUSFREEMOTORS}" -gt "0" ] && echo "new ${PLUSFREEMOTORS} couple motor" >>$CYM_FILEPATH
        [ "${MINUSFREEMOTORS}" -gt "0" ] && echo "new ${MINUSFREEMOTORS} couple minusmotor" >>$CYM_FILEPATH
      else
        echo "new ${FREEMOTORS} couple motor" >>$CYM_FILEPATH
      fi

      if [ -n "${CYM_STICKYMOTOR}" -a -n "${CYM_WAVE_SECTIONS}" ]; then
        local curr_motors=$(( BOUNDMOTORS / CYM_WAVE_SECTIONS ))
        local rest_motors=$(( BOUNDMOTORS - curr_motors * CYM_WAVE_SECTIONS ))
        local zone_width=$(echo "scale=2; $CYM_SHORTSIDE * 2.0 / ${CYM_WAVE_SECTIONS}.0" | bc)
        PLUSFREEMOTORS=$(( CYM_POSITIVEMOTOR * curr_motors / 100 ))
        MINUSFREEMOTORS=$(( (100 - CYM_POSITIVEMOTOR) * curr_motors / 100 ))

        _run_simul ${CYM_WAVE_BEGIN}
        for (( curr_sec=1; curr_sec<=$CYM_WAVE_SECTIONS; curr_sec++ )); do
#          echo "change couple minusmotor { mark = $curr_sec; diffusion = 10; }" >>$CYM_FILEPATH
          local curr_pos=$(echo "scale=2; $CYM_SHORTSIDE * (1.0 - 2.0 * (${curr_sec}.0 - 1.0) / ${CYM_WAVE_SECTIONS}.0)" | bc)
          if [ $curr_sec -eq ${CYM_WAVE_SECTIONS} ]; then
            curr_motors=$(( curr_motors + rest_motors ))
            PLUSFREEMOTORS=$(( CYM_POSITIVEMOTOR * curr_motors / 100 ))
            MINUSFREEMOTORS=$(( (100 - CYM_POSITIVEMOTOR) * curr_motors / 100 ))
          fi
#          echo "delete all graftedmotor { mark = $curr_sec; }" >>$CYM_FILEPATH
          echo "delete all minusmotorinactive { mark = $curr_sec; }" >>$CYM_FILEPATH

          [ "${PLUSFREEMOTORS}" -gt "0" ] && echo "new ${PLUSFREEMOTORS} couple motor { position = line $(( 2 * CYM_SHORTSIDE )) $zone_width turn degree 90 at $curr_pos 0; }" >>$CYM_FILEPATH
          [ "${MINUSFREEMOTORS}" -gt "0" ] && echo "new ${MINUSFREEMOTORS} couple minusmotor { position = line $(( 2 * CYM_SHORTSIDE )) $zone_width turn degree 90 at $curr_pos 0; }" >>$CYM_FILEPATH

          [ $curr_sec -eq ${CYM_WAVE_SECTIONS} ] || _run_simul ${CYM_WAVE_DELAY}
        done
      fi
    fi

    if [ -n "${CYM_DELETEFIBER}" -a "${CYM_DELETEFIBER_FRAMES}" -gt "0" ]; then
      _run_simul ${CYM_DELETEFIBER_FRAMES}
      if [ -n "$CYM_NUCLEATION" ]; then
        echo "delete $(( CYM_DELETEFIBER * MT_NUMBER / 100 )) creator" >>$CYM_FILEPATH
      else
        echo "delete $(( CYM_DELETEFIBER * MT_NUMBER / 100 )) microtubule" >>$CYM_FILEPATH
      fi
    fi

    if [ -n "$CYM_TEST" ]; then
      _run_simul 90
    else
      _run_simul ${CYM_FRAMES}
    fi
  fi
}

# Job-related functions
job_usage() {
  prog="${0##*/}"
  cat >&2 <<EOF
  Generate a cym file and submit a respective cytosim batch job

  $prog [<options>] [<generator_options>]

  Options

  -h, --help
  -q, --quiet
  -d, --dry-run
  -n, --job-name
  -a, --job-array-size
  -r, --job-runtime
  -l, --log-jobs

EOF
  fname=`declare -f cym_usage`
  [ -n "$fname" ] && cym_usage
}

_handle_job_option () {
  opt=
  opt_sz=1
  case "$1" in
    -d|--dry-run) dryrun=true ;;
    -q|--quiet)  quiet=true ;;
    -n|--job-name)
      JOB_NAME=$2
      echo "run job under the name '$JOB_NAME'"
      opt_sz=2
      ;;
    -a|--job-array-size)
      if [ -n "$2" && "$2" -eq "$2" ]; then
        JOB_ARRAY_SIZE=$2
        echo "run an array job, size=$JOB_ARRAY_SIZE"
      else
        echo "invalid array size "$2", must be an integer"
        job_usage
        exit 1
      fi
      opt_sz=2
      ;;
    -r|--job-runtime)
      if [ -n "$2" -a "$2" -eq "$2" -a "$2" -gt 0 ]; then
        JOB_RUNTIME=$2
        echo "job runtime=$JOB_RUNTIME hours"
      else
        echo "invalid array size "$2", must be an integer greater than 0"
        job_usage
        exit 1
      fi
      opt_sz=2
      ;;
    -l|--log-jobs)
      if [ -w "$2" -o -w "$(dirname $2)" ] && [ ! -d "$2" ]; then
        JOBID_LOG=$2
        echo "log jobs to "$JOBID_LOG""
      else
        echo "invalid log file "$2""
        job_usage
        exit 1
      fi
      opt_sz=2
      ;;
    -h|--help)
      job_usage
      exit
      ;;
    '?')
      echo "Unrecognized option: -$OPTARG" >&2
      exit 2
      ;;
    *)
      echo "Unrecognized option: $1" >&2
      exit 2
      ;;
  esac 
}


# store args
ARGS=$@
while [ $# -gt 0 ]; do
  if [ "${1#-}" == "$1" ]; then
    shift
    continue
  fi
  case "$1" in
    --?*)  # long option
      _handle_job_option "$@"
      ;;
    -?*)  # one or more short options
      OPTIND=1
      while getopts :qnarh opt -"${1#-}"; do
        _handle_job_option "$@"
      done
      ;;
    *)
      echo "Unrecognized option: $1" >&2
      exit 2
      ;;
  esac
  while ((opt_sz--)); do
    shift
  done
done

# generate the cym file
generate_cym $ARGS

# prepare the sbatch vars
SBATCH_ARRAY=
SBATCH_OUTPUT_SUFFIX="_%A"
if ! [ -z "$JOB_ARRAY_SIZE" ]; then
  SBATCH_ARRAY="#SBATCH --array=1-$JOB_ARRAY_SIZE"
  SBATCH_OUTPUT_SUFFIX="_%A_%a"
fi

run_cmd()
{
tmp=`mktemp`

JOBID_LOG=${JOBID_DIR}/$(date +"%d-%m-%Y")_${CYM_CONFNAME}.log

cat >$tmp <<EOF
#!/bin/sh
#SBATCH --job-name=${CYM_CONFNAME}_${JOB_NAME}
#SBATCH --output=${SLURM_LOGS}/${CYM_CONFNAME}_${JOB_NAME}${SBATCH_OUTPUT_SUFFIX}.out
#SBATCH --error=${SLURM_LOGS}/${CYM_CONFNAME}_${JOB_NAME}${SBATCH_OUTPUT_SUFFIX}.err
#SBATCH --time=${JOB_RUNTIME}:00:00
#SBATCH --partition=defaultp
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#Do not requeue the job in the case it fails.
#SBATCH --no-requeue
#
#Do not export the local environment to the compute nodes
#SBATCH --export=NONE
$SBATCH_ARRAY

unset SLURM_EXPORT_ENV

export OMP_NUM_THREADS=\${SLURM_CPUS_PER_TASK}

# Timestamp
echo "\$(hostname) began at \$(date +'%Y %b %d, %a, %H:%M:%S')"

# Print the task id.
if [ -n "\${SLURM_ARRAY_JOB_ID}" ]; then
  echo "SLURM_ARRAY_JOB_ID: \${SLURM_ARRAY_JOB_ID}"
  echo "SLURM_ARRAY_TASK_ID: \${SLURM_ARRAY_TASK_ID}"
else
  echo "SLURM_JOB_ID: \${SLURM_JOB_ID}"
fi

# generate the output directory
OUT_DIR=${STORE_DIR}/${CYM_CONFNAME}
if [ -n "\${SLURM_ARRAY_JOB_ID}" ]; then
  OUT_DIR=\${OUT_DIR}/\${SLURM_ARRAY_JOB_ID}_\${SLURM_ARRAY_TASK_ID}
else
  OUT_DIR=\${OUT_DIR}/\${SLURM_JOB_ID}
fi
mkdir -p \${OUT_DIR}

# generate the working directory
WORK_DIR=/localhome/${USER}/${CYM_CONFNAME}/
if [ -n "\${SLURM_ARRAY_JOB_ID}" ]; then
  WORK_DIR=\${WORK_DIR}/\${SLURM_ARRAY_JOB_ID}_\${SLURM_ARRAY_TASK_ID}
else
  WORK_DIR=\${WORK_DIR}/\${SLURM_JOB_ID}
fi
mkdir -p \${WORK_DIR}

# test if workdir has been created
ls -lah \${WORK_DIR}

# log the jobs
echo "\${OUT_DIR}" | tee -a ${JOBID_LOG:-/dev/null}
echo "\${SLURMD_NODENAME} \${WORK_DIR}" 1>&2

# copy the binaries into a subdirectory
if [ -n "${CYTOSIM_PATH}" ]; then
  mkdir -p \${WORK_DIR}/.cytosim
  for s in sim report play; do cp ${CYTOSIM_PATH}/\$s \${WORK_DIR}/.cytosim/; done
  touch \${WORK_DIR}/.cytosim/.\${DISTRIB_CODENAME}
else
  module load cytosim
fi

# copy the model file into the working and output directories
cp ${CYM_FILEPATH} \${WORK_DIR}/${CYM_FILENAME}
cp ${CYM_FILEPATH} \${OUT_DIR}/${CYM_FILENAME}

# run cytosim in the working directory
cd \${WORK_DIR}
if [ -d ".cytosim" ]; then
  srun .cytosim/sim ${CYM_FILENAME}
else
  srun sim ${CYM_FILENAME}
fi


# Timestamp
echo "Simulation completed at \$(date +'%Y %b %d, %a, %H:%M:%S')"

# copy the data
mv *.cmo \${OUT_DIR}
[ -d ".cytosim" ] && mv .cytosim \${OUT_DIR}
rm ${CYM_FILENAME}

if [ "\$(ls -1 | wc -l)" -gt "0" ]; then
  echo "The work directory still contains some files, please delete it manually" 1>&2
else
  cd ${HOME}
  rm -r \${WORK_DIR} || echo "Could not remove wor dir!" 1>&2
fi

# Timestamp
echo "Ended at \$(date +'%Y %b %d, %a, %H:%M:%S')"
EOF

if [ -n "$dryrun" ]; then
  if [ -z "$quiet" ]; then	
    echo ">> $tmp"
    cat $tmp
    echo "<<"
    echo ">> ${CYM_FILEPATH}"
    cat ${CYM_FILEPATH}
    echo "<<"
  fi
  rm ${CYM_FILEPATH}
else
  sbatch $tmp
fi
rm $tmp
}

run_cmd

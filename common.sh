#!/bin/bash
# Netboot Studio
# by James Bishop (jamesbishop2006@gmail.com)

# Common utility functions

COMMON_PREFIX="################  "


BANNER_1="############################################################################################################################################################################################################################################################"
BANNER_2="------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"


function status_ok {
    echo " [ OK ]"
}

function status_fail {
    echo " [ FAIL ]"
    exit 1
}

# show where we are trying to cd to, and bail if it fails
# this is helpful for debugging safety, as we dont keep running commands after failing to cd
function cd_to {
  local REAL_PATH
  realpath "$1" >/dev/null 2>&1 || {
    echo -n "${COMMON_PREFIX} navigate to: $1"
    status_fail
  }
  REAL_PATH=$(realpath "$1")
  echo -n "${COMMON_PREFIX} navigate to: $REAL_PATH"
  cd "$1" 2>/dev/null && status_ok || status_fail
}

# show what command will be run before running it
function do_cmd {
    local COMMAND
    COMMAND="$@"
    echo "${COMMON_PREFIX} Running command: $COMMAND"
    $COMMAND || status_fail
    echo "${COMMON_PREFIX} Done"
}

function get_version {
  local VERSION
  VERSION=$(tr -d '[:space:]' < VERSION)
  echo "$VERSION"
}


function check_root {
  local THIS_USER
  THIS_USER=$(id -u)
  if [ "$THIS_USER" -eq 0 ]; then
    echo "Must NOT be run as root!!"
    exit 1
  fi
}

function check_deps {
  echo "Checking dependencies: $@"
  for DEPENDENCY in $@ ; do
    command -v "$DEPENDENCY" >/dev/null || {
      echo "ERROR: missing dependency: $DEPENDENCY"
      exit 1
    }
  done
  echo "Dependency check: OK"
}

function announce {
  local MESSAGE="$*"
  echo ""
  echo "$BANNER_1"
  echo "    $MESSAGE"
  echo "$BANNER_1"
}

function announce_step {
  local MESSAGE="$*"
  echo ""
  echo "$BANNER_2"
  echo "    $MESSAGE"
  echo "$BANNER_2"
}

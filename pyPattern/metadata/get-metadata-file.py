#!/usr/bin/env python3

import os
import sys

import common

if(len(sys.argv) < 2):
  print('not enough arguments, filename is required', file=sys.stderr)
  quit()

filepath = sys.argv[1]
#if(not os.path.isfile(filepath)):
#  print(f'invalid arguments: file path {filepath} is not a file', file=sys.stderr)
#  quit()
  
print(common.get_safe_filepath(filepath) + '.json')

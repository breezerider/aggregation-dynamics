#!/usr/bin/env python3

import os

def get_safe_filepath(filename):
  return filename.replace(os.sep,'_').replace(' ','_').replace('.','_')

def get_json_path(filename):
  if not filename.endswith('.josn'):
    filename += '.json'
  return os.path.join('json', filename)

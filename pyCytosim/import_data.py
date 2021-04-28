#!/usr/bin/env python3

import os
#import sys
#import time
#import pickle
#import tempfile
#import subprocess
#import numpy as np
#import pandas as pd

#import locale

import click

import cytosim

@click.command()
@click.option("--simdir", default=None, help="The directory with cytosim simulation data.")
@click.option("--out", default=None, help="Output file name")
@click.option("--op", help="A comma-separated list of operations to perform: " + ", ".join(cytosim.opts_dict.keys()))
@click.option("--frames", default='all', type=str,
              help="A comma-separated list of frames which to dump. "
                   "Defaults to 'all'")
def main(simdir : str, out : str, op : str, frames : str ='all'):
  # frame indexes
  frames_idx = None
  if('all' != frames):
    frames = frames.split(',')
    frames_idx = set()
    try:
      for str_frm in frames:
        frames_idx.add(int(str_frm))
      frames_idx = sorted(frames_idx)
    except ValueError:
      click.echo(f'Invalid frame index: {str_frm} is cannot be converted to an integer')
      return

  if(not os.path.isdir(simdir)):
    click.echo(f'Invalid simulation path: {simdir} is not a directory')
    return

  ops = []
  op_lst = op.split(',')
  for o in op_lst:
    o = o.strip()
    valid = False
    for key in cytosim.opts_dict.keys():
      if(o.startswith(key)):
        ops.append(key)
        valid = True
        break
    if(not valid):
      click.echo(f'Invalid operation: "{o}" is not recognized')

  for o in ops:
    fname = os.path.join(simdir, cytosim.CytosimReportSubprocessFactory.filename(o, frames_idx))
    if os.path.isfile(fname):
      click.echo(f'Found file {fname}, cancelling \'{o}\'')
      ops.remove(o)
    else:
      click.echo(f'Did not find file {fname}')

  if(len(ops)):
    args = { 'kind' : 'report', 'simdir' : simdir, 'ops' : ops, 'frames' : frames_idx, 'out' : out }
    cytosim.run_cytosim_async_loop(args)
  else:
    click.echo(f'Nothing to be done')

if __name__ == "__main__":
  main()

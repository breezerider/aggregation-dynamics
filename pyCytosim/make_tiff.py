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

import errno
import shutil
import numpy as np
import matplotlib.image
import tifffile
import tempfile

import click

import cytosim

class TemporaryDirectory(object):
  """Context manager for tempfile.mkdtemp() so it's usable with "with" statement."""
  def __enter__(self):
    self.name = tempfile.mkdtemp()
    return self.name

  def __exit__(self, exc_type, exc_value, traceback):
    shutil.rmtree(self.name)

@click.command()
@click.option("--simdir", default=None, help="The directory with cytosim simulation data.")
@click.option("--channels", default=None, help="A comma-separated list of dataset entities to represnt as different channels in the dataset.")
@click.option("--size", default=800, help="Size of the image.")
@click.option("--out", default=None, help="Output file name")
@click.option("--frames", default='all', type=str,
              help="A comma-separated list of frames which to dump. "
                   "Defaults to 'all'")
def main(simdir : str, channels : str, size : int, out : str, frames : str ='all'):

  # check simulation path
  if(simdir is None)or(not os.path.isdir(simdir)):
    click.echo(f'Invalid simulation path: \'{simdir}\' is not a directory')
    return

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

  if(channels is not None):
    channels = channels.split(',')

  if(out is None):
    out = tempfile.NamedTemporaryFile(suffix='.tiff').name
    with open(out,'w') as f:
      pass

  if(not os.path.isfile(os.path.join(simdir,'properties.cmo'))):
    click.echo(f'Invalid simulation path: {simdir} must contain a "properties.cmo" file')
    return

  props_channels = {}
  new_props_cmo = []
  simul_display = f' display = (style=2; tile=1; label=off; zoom=1.07177345; window_size={size}; )\n'
  with open(os.path.join(simdir,'properties.cmo'),'r') as f:
    text = f.readlines()
    searchSection = False
    inSection = False
    doneSection = False
    sectionFiber = False
    sectionName = None
    sectionSimul = False
    for idx, line in enumerate(text):
      new_props_cmo.append(line)
      if line.startswith('set hand') or line.startswith('set fiber') or line.startswith('set simul'):
        searchSection = True
        sectionSimul = line.startswith('set simul')
        sectionFiber = line.startswith('set fiber')
        sectionName = line.split()[2]
        continue
      if searchSection and line.startswith('{'):
        searchSection = False
        inSection = True
        doneSection = False
        continue
      if inSection and line.startswith('}'):
        inSection = False
#        if not doneSection:
        if sectionSimul:
          new_props_cmo.insert(-1, simul_display)
        else:
          props_channels[sectionName] = { 'idx' : len(new_props_cmo)-2, 'fiber' : sectionFiber }
        doneSection = False
        continue
      if inSection:
        if 'display' in line:
#          if doneSection:
          new_props_cmo.pop()
 #         else:
#          props_channels[sectionName] = idx
#          doneSection = True

  if(channels is not None):
    for CH in channels:
      if not CH in props_channels.keys():
        click.echo(f'Channel {CH} was not found in the dataset')
        return
  else:
    channels = props_channels.keys()
  
  tmpdirs = []
  for CH in channels:
    tdir = tempfile.mkdtemp(suffix=CH)
    tmpdirs.append(tdir)
    isFiber = props_channels[CH]['fiber']
    with open(os.path.join(tdir,f'properties.cmo'),'w') as f:
      for idx, line in enumerate(new_props_cmo):
        for ch, val in props_channels.items():
          if val['idx'] == idx:
            if ch == CH:
              print(f'{ch} is white')
              line += ' display = (color=white; visible=1;)\n'
            else:
              if not isFiber and val['fiber']:
                print(f'{ch} is black')
                line += ' display = (color=black; visible=1;)\n'
              else:
                print(f'{ch} is invisible')
                line += ' display = (visible=0;)\n'
        f.write(line)

  if(len(channels)):
    args = { 'kind' : 'play', 'channels' : channels, 'simdir' : simdir, 'frames' : frames_idx, 'tmpdirs' : tmpdirs }
    result = cytosim.run_cytosim_async_loop(args)

    print(result)

    # ImageJ dataset properties
    slices = 1
    metadata = {'unit':'micrometer','tinterval':10,'spacing':20/size}
    ijmetadata = {'images':len(frames_idx)*len(channels),'channels':len(channels),'slices':slices,'mode':'composite',
                'frames':len(frames_idx),'hyperstack':True,'loop':False}

    # Determine dataset size
    ch_sz = np.zeros(len(channels), dtype=np.uint16)
    for ich, ch in enumerate(channels):
      for ifrm, frm in enumerate(frames_idx):
        click.echo(f"Checking " + os.path.join(tmpdirs[ich],f"image{frm:04d}.png") + f" for position {ifrm}:0:{ich}")
        ch_sz[ich] = ifrm
        try:
          im = matplotlib.image.imread(os.path.join(tmpdirs[ich],f"image{frm:04d}.png"))[:, :, 0]
        except (IOError, OSError) as e:
          click.echo(f"Failed! Channel {ch} (#{ich}) is only {ifrm} frames long")
          break
    
    for ich, ch in enumerate(channels):
      if(ch_sz[ich]==0):
        click.echo(f"Failed! Channel {ch} (#{ich}) is empty")
        quit()

    # Dataset format TZCYX
    image_stack = np.zeros((np.max(ch_sz),slices,len(channels),size,size,1), dtype=np.uint16)

    for ich, ch in enumerate(channels):
      for ifrm, frm in enumerate(frames_idx):
        if(ifrm >= ch_sz[ich]):
          break
        click.echo(f"Loading " + os.path.join(tmpdirs[ich],f"image{frm:04d}.png") + f" into position {ifrm}:0:{ich}")
        try:
          im = matplotlib.image.imread(os.path.join(tmpdirs[ich],f"image{frm:04d}.png"))[:, :, 0]
        except (IOError, OSError) as e:
          break
        image_stack[ifrm, 0, ich, :, :, 0] = np.where(np.ceil(im) < 1, 0, 255)

    # save the result
    tifffile.imsave(
      out,
      image_stack,
      byteorder='>',
      #append = 'force',
      imagej = True,
      metadata = metadata,
      ijmetadata = ijmetadata)
    click.echo(f'TIFF dataset written to {out}')
    for d in tmpdirs:
      try:
        shutil.rmtree(d)
      except OSError as e:
        # Reraise unless ENOENT: No such file or directory
        # (ok if directory has already been deleted)
        if e.errno != errno.ENOENT:
          raise
  else:
    click.echo(f'Nothing to be done')


if __name__ == "__main__":
  main()

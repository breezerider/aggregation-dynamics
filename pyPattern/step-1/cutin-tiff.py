#!/usr/bin/env python3

import os
import sys

import tifffile

import pickle

import numpy as np

import scipy.ndimage
import skimage.filters
import skimage.measure
import skimage.morphology

import click

# Helper class
# "First In, First Out" container
class FifoList:
  def __init__(self, max_size=0, data=[]):
    self._data = data
    self._max_size = max_size
  def __len__(self):
    return len(self._data)
  def __getitem__(self, key):
    return self._data[key]
  def __reversed__(self):
    return reversed(self._data)
  def __str__(self):
    return str(self._data)
  def append(self, elem):
    self._data.append(elem)
    if(self._max_size > 0)and(len(self._data) > self._max_size):
      self._data.pop(0)
  def pop(self):
    return self._data.pop(0)

@click.command()
@click.option("--tiff", default=None, help="Path to TIFF file.")
@click.option("--channels", default='all', help="A comma-separated list of channels in the dataset.")
@click.option("--slices", default='all', help="A comma-separated list of slices in the dataset.")
@click.option("--out", default=None, help="Output file name for TIFF file")
@click.option("--cutin", is_flag=True, help="Cut into the image")
@click.option("--segmentation", default=0, help="Segmentation parameter (peak for background cut-off)")
@click.option("--frames", default='all', type=str,
              help="A comma-separated list of frames which to dump. "
                   "Defaults to 'all'")
@click.option("--full", is_flag=True, help="Output full cutin")
def main(tiff : str, channels : str, slices : str, out : str, cutin : bool =False, segmentation : int =0, frames : str ='all', full : bool =False):

  # input file
  if (tiff is None)or(not os.path.isfile(tiff)):
    click.echo(f'Invalid data path: {tiff} must be a valid file path')
    return

  # channels
  channels_idx = None
  if('all' != channels):
    channels = channels.split(',')
    channels_idx = set()
    try:
      for str_ch in channels:
        channels_idx.add(int(str_ch))
      channels_idx = sorted(channels_idx)
    except ValueError:
      click.echo(f'Invalid channel index: {str_ch} is cannot be converted to an integer')
      return

  # slices
  slices_idx = None
  if('all' != slices):
    slices = slices.split(',')
    slices_idx = set()
    try:
      for str_sl in slices:
        slices_idx.add(int(str_sl))
      slices_idx = sorted(slices_idx)
    except ValueError:
      click.echo(f'Invalid slice index: {str_sl} is cannot be converted to an integer')
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
  
  # which peak to threshold
  if(segmentation < 0):
    click.echo(f'Invalid threshold parameter: peak index must be a non-negative integer')
    return

  # output file
  if(out is None)or(os.path.isdir(out))or(not os.path.isdir(os.path.dirname(out))):
    click.echo(f'Invalid output path: "{out}" must be a writable file path')
    return
  else:
    out_filepath = out

  # TIFF processing
  with tifffile.TiffFile(tiff) as imfile, open(out_filepath, 'wb') as handle:
    click.echo(f'opened TIFF file "{imfile.filename}"')
    for s in imfile.series:
      num_frames = s.shape[0]
      if len(s.shape) > 4:
        num_slices = s.shape[1]
        num_channels = s.shape[2]
        size = s.shape[3:5]
      elif len(s.shape) > 3:
        num_slices = 1
        num_channels = s.shape[1]
        size = s.shape[2:4]
      else:
        num_slices = 1
        num_channels = 1
        size = s.shape[1:3]
      click.echo(f'TIFF serie: frame size = {size}, # frames = {num_frames}, # channels = {num_channels}, # slices = {num_slices}')

      # frames
      if(frames_idx is not None):
        frames = sorted(set(frames_idx).intersection(set(range(num_frames))))
        if(len(frames)==0):
          click.echo(f'Invalid frame index: file "{tiff}" does not contain any of provided frame indexes {frames_idx}')
          return
      else:
        frames = range(num_frames)

      # slices
      if(slices_idx is not None):
        slices = sorted(set(slices_idx).intersection(set(range(num_slices))))
        if(len(slices)==0):
          click.echo(f'Invalid slice index: file "{tiff}" does not contain any of provided channel indexes {slices_idx}')
          return
      else:
        slices = range(num_slices)

      if(len(slices)>1):
        click.echo(f'Invalid slice index: too many slices matched')
        return

      # channels
      if(channels_idx is not None):
        channels = sorted(set(channels_idx).intersection(set(range(num_channels))))
        if(len(channels)==0):
          click.echo(f'Invalid channel index: file "{tiff}" does not contain any of provided channel indexes {channels_idx}')
          return
      else:
        channels = range(num_channels)

      if(len(channels)>1):
        click.echo(f'Invalid channel index: too many channels matched')
        return

      # processing
      sl = slices[0]
      ch = channels[0]
      click.echo(f'Processing frames (channel #{ch}, slice #{sl})...')

      # masks
      mask = np.zeros((size[0],size[1]),dtype=bool)
      mask2 = np.zeros((size[0],size[1]),dtype=bool)
      mask_boundary = np.zeros((size[0],size[1]),dtype=bool)

      # region vars
      params = np.zeros((len(frames), 3), dtype=np.float)
      mask_cell = np.zeros((len(frames),size[0],size[1]), dtype=np.bool)

      # histogram
      num_hist_bins = 256

      tholds = FifoList(max_size=10)
      for ifrm, frm in enumerate(frames):
        click.echo(f'Frame {frm}...')

        page = s.pages[ifrm*num_slices*num_channels + sl*num_channels + ch]
        img = skimage.util.img_as_float32(page.asarray())

        if(max(np.ravel(img)) == 0.0):
          continue

        # threshold
        histogram, bin_edges = np.histogram(np.ravel(img), bins=num_hist_bins, range=(0, 1))
        dhdx = np.diff(np.sign(np.diff(histogram)))
        
        idx = np.where(dhdx < 0)[0] + 2 # for 2 np.diff
        if(len(idx)>segmentation):
          idx = idx[segmentation]
        elif(len(idx)>0):
          idx = idx[0]
        else:
          continue
        thold = bin_edges[idx]
        tholds.append(thold)
        thold = np.mean(tholds)

        #if(ifrm == 0):
        #  click.echo(f'bin_edges {bin_edges}...')
        #click.echo(f'histogram {histogram}...')

        # Cell
        mask = img > thold
        skimage.morphology.remove_small_objects(mask, (min(size)//8)**2, in_place=True)
        scipy.ndimage.binary_fill_holes(mask, output=mask2)
        scipy.ndimage.morphology.binary_erosion(mask2, iterations=5, output=mask)

        # cell boundary
        scipy.ndimage.morphology.binary_dilation(mask, iterations=5, output=mask2)
        mask_cell[ifrm,:,:] = mask2
        mask_boundary.fill(False)
        mask_boundary[~mask & mask2] = True
        edges_where = np.where(mask_boundary)
        edges_coords = np.asarray(edges_where).T
        
        # fit a circle
        circle = skimage.measure.CircleModel()
        circle.estimate(edges_coords)
        params[ifrm, :] = circle.params[:] # yc, xc, r
        
        if 0:
          import matplotlib.pyplot as plt
          import matplotlib.colors as clr
          import matplotlib.ticker as tck
          import matplotlib.cm as cm

          import dufte
          plt.rc('text', usetex=True)
          plt.rc('font', family = 'serif', serif = 'cm10', size = 12)
          plt.style.use(dufte.style)
          plt.style.use('dark_background')

          fig = plt.figure(figsize=(16,8))
          
          ax = fig.add_subplot(1, 3, 1)
          ax.set_title('Original Image', fontsize=48)
          ax.imshow(img.T, interpolation="none", norm=clr.Normalize(1/255,30/255), cmap=plt.cm.gray)
          
          ax = fig.add_subplot(1, 3, 2)
          ax.set_title('Segmented Image', fontsize=48)
          if(cutin):
            start = (int(params[ifrm, 0] - np.sqrt(2)/2 * params[ifrm, 2]), int(params[ifrm, 1] - np.sqrt(2)/2 * params[ifrm, 2]))
            end   = (int(params[ifrm, 0] + np.sqrt(2)/2 * params[ifrm, 2]), int(params[ifrm, 1] + np.sqrt(2)/2 * params[ifrm, 2]))
            rs, cs = skimage.draw.rectangle(start , end=end, shape=img.shape)
            #print(f'start = {start}; end = {end}')
            img_test = np.zeros(img.shape)
            img_tmp = img[rs, cs]
            img_test[:img_tmp.shape[0], :img_tmp.shape[1]] = img_tmp
            #img_test[~mask] = 0
          else:
            img_test = img
            img_test[~mask] = 0
            
          #rc, cc = skimage.draw.circle(params[ifrm, 0], params[ifrm, 1], params[ifrm, 2], size)
          #img_test[rc, cc] = 1.0
          
          ax.imshow(img_test.T, interpolation="none", norm=clr.Normalize(1/255,30/255), cmap=plt.cm.gray)
          
          ax = fig.add_subplot(1, 3, 3)
          ax.set_title('Histogram', fontsize=48)
          #ax.set_xscale('log')
          ax.hist(histogram, bins=bin_edges*255, density=True)
          ax.plot(np.asarray(range(1,255)), np.sign(dhdx) < 0)

          fig.savefig(os.path.join(os.path.dirname(out),f'cell-boundary-{ifrm}.png'))
          plt.close(fig)
      
      # get segmentation params
      cavg = int(np.ceil(np.mean(params[:,0],axis=0)))
      ravg = int(np.ceil(np.mean(params[:,1],axis=0)))
      rmax = np.ceil(np.max(params[:,2],axis=0))
      if(full):
        rmax *= 2/np.sqrt(2)
      #else:
      #  rmax /= np.sqrt(2)

      click.echo(f'Saving results (channel #{ch}, slice #{sl})...')
      if(cutin):
        start = (int(ravg - np.sqrt(2)/2 * rmax), int(cavg - np.sqrt(2)/2 * rmax))
        end   = (int(ravg + np.sqrt(2)/2 * rmax), int(cavg + np.sqrt(2)/2 * rmax))
        rs, cs = skimage.draw.rectangle(start , end=end, shape=size)
        img = np.zeros(size)
        img = img[rs, cs]
        img_out = np.zeros((len(frames),1,1,img.shape[0],img.shape[1]), dtype=np.uint8) # TZCYX
        for ifrm, frm in enumerate(frames):
          click.echo(f'Frame {frm}...')
          
          page = s.pages[frm*num_slices*num_channels + sl*num_channels + ch]
          img = skimage.util.img_as_float32(page.asarray())
          
          img_out[ifrm,0,0,:,:] = skimage.util.img_as_ubyte(img[rs, cs])
          
        channels = ['cutin']
      else:
        img_out = np.zeros((len(frames),1,3,size[0],size[1]), dtype=np.uint8) # TZCYX
        for ifrm, frm in enumerate(frames):
          click.echo(f'Frame {frm}...')

          page = s.pages[frm*num_slices*num_channels + sl*num_channels + ch]
          img = skimage.util.img_as_float32(page.asarray())
          
          # circle center
          #col, row = [int(round(x)) for x in params[ifrm,0:2]]
          
          # circle radius
          r = params[ifrm, 2]
          
          # process the image
          img[~mask_cell[ifrm,:,:]] = -1.0
          img_polar = skimage.transform.warp_polar(img, center=(ravg, cavg), radius=rmax)
          
          # draw the ROI
          rc, cc = skimage.draw.circle(ravg, cavg, rmax, size)
          
          
          # output image
          img_out[ifrm,0,0,:,:] = skimage.util.img_as_ubyte(img)
          img_out[ifrm,0,1,:img_polar.shape[0],:img_polar.shape[1]] = skimage.util.img_as_ubyte(img_polar)
          img.fill(0)
          img[rc, cc] = 1.0;
          img_out[ifrm,0,2,:,:] = skimage.util.img_as_ubyte(img)

        channels = ['denoised original','polar','ellipse']

      ijmetadata = { 'images':len(frames)*len(channels),'channels':len(channels),'slices':1,'mode':'composite','frames':len(frames),'hyperstack':True,'loop':False }
      tifffile.imsave(
        out_filepath,
        img_out.astype(np.uint8),
        byteorder='>',
        ijmetadata = ijmetadata,
        imagej = True)

      click.echo(f'done TIFF serie')
    click.echo(f'done processing')

if __name__ == '__main__':
  main()


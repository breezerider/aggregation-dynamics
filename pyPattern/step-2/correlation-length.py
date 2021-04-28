#!/usr/bin/env python3

import os
import sys

import tifffile

import pickle
import json

import pyfftw

import numpy as np
import scipy.signal
import scipy.optimize

import skimage.util

import click

def write_out(handle, *args):
  for v in args:
    pickle.dump(v, handle, protocol=pickle.HIGHEST_PROTOCOL)

@click.command()
@click.option("--tiff", default=None, help="Path to TIFF file.")
@click.option("--channels", default='all', help="A comma-separated list of channels in the dataset.")
@click.option("--slices", default='all', help="A comma-separated list of slices in the dataset.")
@click.option("--out", default=None, help="Output directory name")
@click.option("--frames", default='all', type=str,
              help="A comma-separated list of frames which to dump. "
                   "Defaults to 'all'")
@click.option("--metadata", default=None, help="Metadata file.")
@click.option("--polar", default=None, help="Polar coordinates.")
@click.option("--binary", is_flag=True, help="Binary image.")
def main(tiff : str, channels : str, slices : str, out : str, frames : str ='all', metadata : str=None, polar : str=None, binary : bool=False):

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

  # output file
  if(out is None)or(os.path.isdir(out))or(not os.path.isdir(os.path.dirname(out))):
    click.echo(f'Invalid output path: "{out}" must be a writable file path')
    return
  else:
    out_filepath = out

  # Metadata
  meta = None
  if(metadata is not None):
    try:
      with open(metadata, 'r') as handle:
        meta = json.load(handle)
    except:
      click.echo(f'Invalid metadata filepath "{metadata}"')
      return
  
  # polar ACF
  do_polar = 0
  if(polar is not None)and(len(polar)):
    if(polar.startswith('rad')):
      do_polar = 1
    elif(polar.startswith('ang')):
      do_polar = 2
      

  # initialize the data structures
  zero_pad = True
  do_psd = False
  n_frm_write_out = 10
  frm_acf = None
  frm_spect = None
  frm_avg_acf = None
  frm_psd = None
  
  offset = 100
  cutoff = 200

  with tifffile.TiffFile(tiff) as imfile, open(out_filepath, 'wb') as handle:
    click.echo(f'opened TIFF file "{imfile.filename}"')
    print(len(imfile.series))
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

      #frm_acf = np.zeros([num_frames,size[0],size[1]],dtype=np.float)
      #frm_spect = np.zeros([num_frames,size[0],size[1]],dtype=np.float)
      if(do_polar==1):
        frm_avg_acf = np.zeros([len(frames),size[1]],dtype=np.float)
      elif(do_polar==2):
        frm_avg_acf = np.zeros([len(frames),360],dtype=np.float)
      else:
        frm_avg_acf = np.zeros([len(frames),np.max(size)],dtype=np.float)
      if(do_psd):
        frm_psd = np.zeros([len(frames),np.max(size)//2],dtype=np.float)

      click.echo('Processing frames...')

      # processing vars
      img_tmp = np.zeros(size, dtype=np.float)
      img_acf = np.zeros(size, dtype=np.float)
      #img_test = np.zeros([2*size[0],2*size[1]], dtype=np.float)
      
      debug = False
      
      if(do_polar < 1):
        res_acf = np.zeros((np.max(size)),dtype=np.float)
      else:
        res_acf = np.zeros((360),dtype=np.float)
      if(do_polar==0):
        xi = range(np.max(size))
        X, Y = np.meshgrid(xi, xi)
        rho = np.floor(np.sqrt(X**2 + Y**2))

      # FFT vars
      original_fft = pyfftw.empty_aligned([2*size[0],2*size[1]], dtype='complex64')
      transform_fft = pyfftw.empty_aligned([2*size[0],2*size[1]], dtype='complex64')
      fft_object = pyfftw.FFTW(original_fft, transform_fft, axes=[0,1], direction='FFTW_FORWARD', flags=['FFTW_DESTROY_INPUT'])
      ifft_object = pyfftw.FFTW(transform_fft, original_fft, axes=[0,1], direction='FFTW_BACKWARD', flags=['FFTW_DESTROY_INPUT'])

      if debug:
        frm_residuals = np.zeros((len(frames),np.max(size)), dtype=np.float)
        frm_residuals.fill(np.nan)

        frm_params = np.zeros((len(frames),3), dtype=np.float)
        frm_params.fill(np.nan)
        
        num_panels = 4 if do_polar else 5

      frm_img_avg_med = np.zeros((len(frames),2), dtype=np.float)
      frm_img_avg_med.fill(np.nan)
      
      for ifrm, frm in enumerate(frames):
        click.echo(f'Frame {frm}...')

        page = s.pages[frm*num_slices*num_channels + sl*num_channels + ch]
        #print(f'max(img) = {np.max(np.ravel(img))}')
        if(binary):
          img = page.asarray()
          img[img > 0.0] = 1.0
        else:
          img = skimage.util.img_as_float32(page.asarray())
          mask = img == 0.0
          img[mask] = np.nan

        original_fft.fill(0)
        if(do_polar):
          img_mean = np.nanmean(np.ravel(img[:,offset:cutoff]))
          img_median = np.nanmedian(np.ravel(img[:,offset:cutoff]))
          
          img_tmp = img - img_mean
          img_total = np.nansum(np.ravel(img_tmp[:,offset:cutoff]**2))
          if(not binary):
            img_tmp[mask] = 0.0
          original_fft[:360,offset:cutoff] = img_tmp[:360,offset:cutoff]
          original_fft[360:720,offset:cutoff] = img_tmp[:360,offset:cutoff]
        else:
          img_mean = np.nanmean(255*np.ravel(img))
          img_std = np.nanstd(255*np.ravel(img), dtype=np.float128)
          img_kurt = 
          img_median = np.nanmedian(np.ravel(img))
          
          print(f'mean(img) = {img_mean}')
          print(f'median(img) = {img_median}')
          
          img_tmp = img - img_mean
          img_total = np.nansum(np.ravel(img_tmp**2))
          if(not binary):
            img_tmp[mask] = 0.0
          original_fft[:size[0],:size[1]] = img_tmp[:]

        frm_img_avg_med[ifrm,:] = img_mean, img_median, img_kurt

        #img_test[:] = original_fft[:].real

        #import matplotlib.pyplot as plt
        #import matplotlib.colors as clr
        #import matplotlib.ticker as tck
        #import matplotlib.cm as cm

        #import dufte
        #plt.rc('text', usetex=True)
        #plt.rc('font', family = 'serif', serif = 'cm10', size = 12)
        #plt.style.use(dufte.style)
        #plt.style.use('dark_background')

        #fig = plt.figure(figsize=(8,8))
        #ax = fig.add_subplot(1, 1, 1)
        #ax.set_title('Test Image', fontsize=48)
        #ax.imshow(img_test.T, interpolation="none", cmap=plt.cm.gray)

        #fig.savefig(os.path.join(os.path.dirname(out),f'test-acf-{ifrm}.png'))
        #plt.close(fig)

        #if(ifrm > 10):
          #quit()

        #continue
        
        if(np.isnan(img_total))or(img_total <= 0.0):
          continue

        fft  = fft_object()
        transform_fft *= transform_fft.conj()
        ifft = ifft_object()

        img_acf[:] = original_fft[:size[0],:size[1]].real / img_total

        # Get the average radial profile fo the Autocorrelation Function
        res_acf.fill(0)
        if(do_polar==1):
          for ri in range(len(res_acf)):
            res_acf[ri] = np.nanmean(img_acf[:360,ri])
        elif(do_polar==2):
          for fi in range(0,360):
            res_acf[fi] = np.nanmean(img_acf[fi,:])
        else:
          for ri in range(len(res_acf)):
            xyi = rho == ri
            res_acf[ri] = np.nanmean(img_acf[xyi])

        if debug:
          import matplotlib.pyplot as plt
          import matplotlib.colors as clr
          import matplotlib.ticker as tck
          import matplotlib.cm as cm
          
          import dufte
          plt.rc('text', usetex=True)
          plt.rc('font', family = 'serif', serif = 'cm10', size = 12)
          plt.style.use(dufte.style)
          plt.style.use('dark_background')
          
          fig = plt.figure(figsize=(8*num_panels,8))

          ax = fig.add_subplot(1, num_panels, 1)
          ax.set_title('Original', fontsize=48)
          #extent = [0, dx*img_acf.shape[0], dx*img_acf.shape[1], 0]
          if(do_polar > 0):
            img[:,0:offset] = np.nan
            img[:,cutoff:] = np.nan
            ax.imshow(img[:360,:], interpolation="none", norm=clr.Normalize(1/255,30/255), cmap=plt.cm.gray)
          else:
            ax.imshow(img, interpolation="none", cmap=plt.cm.gray) #norm=clr.Normalize(1/255,30/255), cmap=plt.cm.gray)

          #avg[ifrm] = img_mean
          #median[ifrm] = img_median
          
          ax = fig.add_subplot(1, num_panels, 2)
          ax.set_xlabel('Time')
          ax.set_title('Intensity')
          #ax.set_ylim([1e-2, 1e-1])
          #ax.set_yscale('log')
          ax.plot(np.asarray(range(len(frames))), frm_img_avg_med[:,0], label='Mean')
          ax.plot(np.asarray(range(len(frames))), frm_img_avg_med[:,1], label='Median')
          ax.legend()

          ax = fig.add_subplot(1, num_panels, 3)
          ax.set_title('2-D ACF (Real)', fontsize=48)
          #extent = [0, dx*img_acf.shape[0], dx*img_acf.shape[1], 0]
          if(do_polar > 0):
            ax.set_ylabel('Angle')
            ax.imshow(img_acf[:360,:], interpolation="none", norm=clr.Normalize(-1,1), cmap=plt.cm.seismic)
          else:
            ax.imshow(img_acf, interpolation="none", norm=clr.Normalize(-1,1), cmap=plt.cm.seismic)

          ax = fig.add_subplot(1, num_panels, 4)
          ax.set_title('Avg ACF', fontsize=48)
          if(do_polar==1):
            ax.set_ylim([-0.05, 1])
            ax.set_xlabel('Radial Distance')
            ax.plot(np.linspace(0,len(res_acf)-1,len(res_acf)), res_acf)
          elif(do_polar==2):
            ax.set_ylabel('Angle')
            ax.plot(res_acf, np.linspace(0,359,360))
            ax.invert_yaxis()
          else:
            #peaks, properties = scipy.signal.find_peaks(-res_acf, prominence=None, width=10)
            #if(len(peaks)):
              #def f(x, a, b):
                #return a + np.exp(b * x)
              #xdata = np.asarray(range(peaks[0]+1))
              #ydata = res_acf[0:peaks[0]+1]
              #popt, pcov = scipy.optimize.curve_fit(f, xdata, ydata, p0=[1,-1], bounds=((-np.inf, -np.inf), (np.inf, 0)), maxfev=10000)
              #print(popt)
              #A[ifrm] = popt[1]
              #ax.plot(xdata, f(xdata, *popt))
            xdata = np.asarray(range(len(res_acf)))
            ydata = res_acf
            #for c in range(1,11):
            if 1:
              def f(x, a, b, c):
                return a *  np.exp( - b * x ) + (1 - a) * np.exp( - c * x ) #np.power(1 + x, -b)#a * np.exp( -b * x ) + (1 - a) * np.exp( -c * x )
              popt, pcov = scipy.optimize.curve_fit(f, xdata, ydata, p0=[0.5, 1, 10], bounds=((0, 0, 0), (1, np.inf, np.inf)), maxfev=10000)
              print(popt)
              frm_params[ifrm,:] = popt[:]
              
              frm_residuals[ifrm] = np.linalg.norm(f(xdata, *popt) - ydata)
              ax.plot(xdata, f(xdata, *popt), label=f'Fit')
            
            #window_size = 10
            #dcdx = np.diff(res_acf)/res_acf[:-1]
            #dcdx_avg = np.zeros((len(res_acf)-window_size), dtype=np.float)
            #for idt in range(len(dcdx_avg)):
              #dcdx_avg[idt] = np.mean(dcdx[idt:idt+window_size])

            #ax.plot(xdata[:len(dcdx_avg)], dcdx_avg, label='Avg dc/dx')
            
            ax.set_ylim([-0.05, 1])
            ax.set_xlabel('Radial Distance')
            ax.plot(np.linspace(0,len(res_acf)-1,len(res_acf)), res_acf, label='Avg ACF')
            ax.legend()
          
          if(do_polar==0):
            ax = fig.add_subplot(1, num_panels, 5)
            ax.set_ylim([1e-3, 1e3])
            ax.set_yscale('log')
            ax.set_xlabel('Time')
            ax.set_title('Decay Exponent (pixels, 1 pixel ~ 1-1.5 um)')
            
            #A = frm_params[:,0] - np.sqrt(frm_params[:,0])
            #B = frm_params[:,0] + np.sqrt(frm_params[:,0])
            
            ax.plot(np.asarray(range(len(frames))), frm_params[:,0], label='A')
            ax.plot(np.asarray(range(len(frames))), frm_params[:,1], label='B')
            ax.plot(np.asarray(range(len(frames))), frm_params[:,2], label='C')
            
            ax2 = ax.twinx()
            ax2.plot(np.asarray(range(len(frames))), frm_residuals, 'r--', label='Residuals')
            ax2.set_ylabel('Residuals')
            
            #for c in range(10):
              #ax.plot(np.asarray(range(len(frames))), frm_params[:,c], label=f'fit {c}')
            
            #ax.plot(np.asarray(range(len(frames))), frm_params[:,2], label='C')
            
            #ax.plot(np.asarray(range(len(frames))), -np.log(0.1)/A[:, 0], label='10-fold distance')
            #ax.plot(np.asarray(range(len(frames))), np.power(0.1, -1.0/A[:, 0])-1, label='10-fold distance')
            ax.legend()

          #ax.xaxis.set_major_formatter(tck.FormatStrFormatter('%g $\mu m$'))
          #ax.xaxis.set_major_locator(tck.MultipleLocator(base=40.0))
          #ax.yaxis.set_major_formatter(tck.FormatStrFormatter('%g $\mu m$'))
          #ax.yaxis.set_major_locator(tck.MultipleLocator(base=40.0))

          fig.tight_layout()
          if(do_polar>0):
            fig.savefig(os.path.join(os.path.dirname(out),f'acf-polar-{ifrm}.png'))
          else:
            fig.savefig(os.path.join(os.path.dirname(out),f'acf-cartesian-{ifrm}.png'))
          plt.close(fig)

        # Get the average radial Power Spectral Density
        if(do_psd):
          maxdim = max(img_flt.shape)
          xi = []
          if maxdim % 2 == 0:
            xi = [range(-maxdim//2,0), range(1,maxdim//2+1)]
          else:
            xi = range(-maxdim//2,maxdim//2)
          X, Y = np.meshgrid(xi, xi)
          rho = np.floor(np.sqrt(X**2 + Y**2))
          res_psd = np.zeros((maxdim//2),dtype=np.float)
          for ri in range(maxdim//2):
            xyi = rho == ri
            res_psd[ri] = np.abs(np.nanmean(img_c_spect_cmb[xyi]))**2
          res_psd /= img_total

        # store the data
        #frm_spect[ifrm,:,:] = np.abs(img_spect[img_flt.shape[0]//2:img_flt.shape[0]//2+img_flt.shape[0],img_flt.shape[1]//2:img_flt.shape[1]//2+img_flt.shape[1]])
        #frm_acf[ifrm, :, :] = img_acf
        frm_avg_acf[ifrm, :] = res_acf
        if(do_psd):
          frm_psd[ifrm, :] = res_psd

        if((frm % n_frm_write_out)==0):
          handle.seek(0)
          if(do_psd):
            write_out(handle, frm_avg_acf[:ifrm+1,:], frm_psd[:ifrm+1,:])
          else:
            write_out(handle, frm_avg_acf[:ifrm+1,:])
          write_out(handle, frm_img_avg_med[:ifrm+1,:])
          if debug:
            write_out(handle, frm_residuals[:ifrm+1])
          #write_out(handle, frm_spect[:ifrm+1,:,:], frm_acf[:ifrm+1,:,:], frm_avg_acf[:ifrm+1,:], frm_psd[:ifrm+1,:])

      if(do_psd):
        write_out(handle, frm_avg_acf[:ifrm+1,:], frm_psd[:ifrm+1,:])
      else:
        write_out(handle, frm_avg_acf[:ifrm+1,:])
      write_out(handle, frm_img_avg_med[:ifrm+1,:])
      if debug:
        write_out(handle, frm_residuals[:ifrm+1])
      click.echo(f'done TIFF serie')
    click.echo(f'done processing')

if __name__ == '__main__':
  main()


#!/usr/bin/env python3

import os
import sys

import pickle
import json

import numpy as np
#import scipy.signal
import scipy.optimize

import click

import matplotlib.pyplot as plt
import matplotlib.colors as clr
import matplotlib.ticker as tck
import matplotlib.cm as cm
import matplotlib.lines as ln

import dufte
plt.rc('text', usetex=True)
plt.rc('font', family = 'serif', serif = 'cm10', size = 12)
plt.style.use(dufte.style)
plt.style.use('dark_background')

import clfmodels

def read_in(handle, *args):
  vals = list()
  for v in args:
    vals.append(pickle.load(handle))
  return tuple(vals[:])

def write_out(handle, *args):
  for v in args:
    pickle.dump(v, handle, protocol=pickle.HIGHEST_PROTOCOL)


@click.command()
@click.option("--data", required=True, multiple=True, type=click.Tuple([str, str]), help="Path to data file and metadata.")
@click.option("--out", required=True, type=str, help="Output file name")
@click.option("--model", required=True, type=str, help="Model for the fit")
@click.option("--shift", is_flag=True, help="Shift")
@click.option("--polar", is_flag=True, help="Polar")
def main(data : list, out : str, model : str, shift : bool=False, polar : bool=False):

  # input data file
  DX = dict()
  DT = dict()
  for f in data:
    print(f)
    if(not os.path.isfile(f[0])):
      click.echo(f'Invalid data path: {f[0]} must be a valid file path')
      return
    if(f[1].startswith(':')):
      click.echo(f'Warning: metadata file path was ommitted, expecting ":dx:dt" to be present')
    else:
      if(not os.path.isfile(f[1])):
        click.echo(f'Invalid data path: {f[1]} must be a valid file path')
        return

  # model
  if(model not in clfmodels.Models.keys()):
    click.echo(f'Invalid model: "{model}" is not one of {clfmodels.Models.keys()}')
    return

  # output file
  if(os.path.isdir(out))or(not os.path.isdir(os.path.dirname(out))):
    click.echo(f'Invalid output path: "{out}" must be a writable file path')
    return
  else:
    out_filepath = out

  # initialize the data structures
  frm_avg_acf = list()
  frm_img_avg_med = list()
  #frm_errors = list()

  # import data
  TXT = list()
  dT = list()
  dX = list()
  EV = list()
  for f in data:
    with open(f[0], 'rb') as handle:
      click.echo(f'opened data file "{f[0]}"')
      acf, avg_med = read_in(handle, frm_avg_acf, frm_img_avg_med) #, frm_errors) # frm_psd, frm_acf, frm_spect
      frm_avg_acf.append(acf)
      frm_img_avg_med.append(avg_med)
      #frm_errors.append(err)
    if(f[1].startswith(':')):
      tmp = f[1].split(':')
      if(len(tmp) < 3):
        click.echo(f'Invalid :dx:dt definition')
        return 1
      dX.append(float(tmp[1]))
      dT.append(float(tmp[2]))
      EV.append(list())
    else:
      with open(f[1], 'rb') as handle:
        click.echo(f'opened metadata file "{f[0]}"')
        meta = json.load(handle)
      dT.append(float(meta['time-step']))
      dX.append(float(meta['um-per-pixel']))
      EV.append(meta['events'])
    d = None
    if(f[1].endswith(':')):
      d = f[1].split(':')
      if(len(d) > 3):
        d = d[3]
    if(d is None):
      d = os.path.dirname(f[0])
      d = d.split(os.sep)[-1]
      d = d.replace('_',' ')
    TXT.append(d)

  # correlation length model fits
  click.echo(f'Fitting {model}...')
  fitModel = clfmodels.Models[model]
  fitModel = fitModel()
  fit_every_nth=1
  for acf, avg_med, dx, dt, txt, ev in zip(frm_avg_acf, frm_img_avg_med, dX, dT, TXT, EV):
    xdata = np.asarray(range(acf.shape[1]), dtype=float) * dx
    errors = np.zeros(acf.shape, dtype=float)
    errors.fill(np.nan)
    params = np.zeros((acf.shape[0], len(fitModel.initialguess())), dtype=float)
    params.fill(np.nan)
    popt = None
    for t in range(0,acf.shape[0],fit_every_nth):
      click.echo(f'Time point {t}...')
      ydata = acf[t, :]

      #out_plotpath = os.path.dirname(out_filepath)
      #fig = plt.figure(figsize=(8, 8))
      #ax = fig.add_subplot(1, 1, 1)
      #ax.plot(xdata, ydata, '-', linewidth=1)
      #fig.savefig(f'{out_plotpath}/{model}-{t}.png')

      if(popt is not None):
        ig = popt
      else:
        ig = fitModel.initialguess()

      cnt = 0
      while True:
        print(f'IG: {ig}')
        
        try:
          popt, pcov = scipy.optimize.curve_fit(fitModel.function, xdata, ydata, ig, jac=fitModel.jac, method='trf', bounds=fitModel.bounds(), max_nfev=1000, verbose=2)
        except:
          if(cnt > 0):
            quit()
          ig = popt
          cnt += 1

        if(all(popt != ig)):
          break
        else:
          ig = fitModel.initialguess()

      #print(f'Sucessful? => {popt.success}')
      print(f'Fit = {popt}')
      params[t, :] = popt
      errors[t, :] = fitModel.error(popt, xdata, ydata)

    # write data
    click.echo(f'Write out results to {out_filepath}...')
    with open(out_filepath, 'wb') as handle:
      write_out(handle, params, errors, dx, dt, txt, ev, model, acf, avg_med)

    # plot
    click.echo(f'Plotting results...')
    out_plotpath = os.path.dirname(out_filepath)

    fig = plt.figure(figsize=(16, 8))
    fig.suptitle(f'{txt} == {model}', fontsize=48)

    ax = fig.add_subplot(1, 2, 1)
    for t in range(0,acf.shape[0],fit_every_nth):
      ydata = acf[t, :]
      ax.plot(xdata, ydata, '-', linewidth=2)
      p = params[t, :]
      ax.plot(xdata, fitModel.function(xdata, *p), '--', linewidth=1)

    ax.set_ylim([-0.05, 1])
    ax.set_xlabel('Distance, $\mu$ m', fontsize=22)
    ax.set_ylabel('Correlation', fontsize=22)

    ax = fig.add_subplot(1, 2, 2)
    tdata = np.asarray(range(acf.shape[0]),dtype=np.float)*dt/60.0
    res = np.linalg.norm(errors, axis=1)
    ax.plot(tdata[::fit_every_nth], res[::fit_every_nth], 'r--', label='Error')
    print(f'params.shape = {params.shape}')
    for i in range(params.shape[1]):
      if((model=='scldblexp')and(i==0))or(model=='hyp'):
        p = params[::fit_every_nth,i]
      else:
        p = 1.0/params[::fit_every_nth,i]
      ax.plot(tdata[::fit_every_nth], p, label=f'Param {i}')

    ax.set_ylim([1e-3, 1e3])
    ax.set_yscale('log')
    ax.set_xlabel('Time, min', fontsize=22)
    ax.set_ylabel('Correlation Distance, $\mu$ m', fontsize=22)
    ax.legend()

    fig.tight_layout()
    click.echo(f'Saving to {out_plotpath}/{model}.png...')
    fig.savefig(f'{out_plotpath}/{model}.png')
    plt.close(fig)

  return 0

if __name__ == '__main__':
    main()


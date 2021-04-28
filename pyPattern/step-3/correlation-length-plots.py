#!/usr/bin/env python3

import os
import sys

import pickle
import json

import numpy as np
import scipy as sp
import scipy.interpolate
#import scipy.stats
#import scipy.signal
#import scipy.optimize

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
@click.option("--data", required=True, multiple=True, type=(str, str), help="Path to file with fit data.")
@click.option("--out", required=True, type=str, help="Output file name")
@click.option("--avgplot", is_flag=True, default=False, help="Plot average intensity")
@click.option("--simulation", is_flag=True, default=False, help="Use secondary length scale")
@click.option("--region", is_flag=True, default=False, help="Show only a given region")
@click.option("--events", is_flag=True, default=False, help="Show events")
@click.option("--logX", is_flag=True, default=False, help="Use log scale")
@click.option("--logY", is_flag=True, default=False, help="Use log scale")
@click.option("--clus", default=None, type=str, help="Path to file with cluster data.")
@click.option("--fiber", default=None, type=str, help="Path to file with fiber length data.")
@click.option("--maximum", default=10.0, type=float, help="Maximal value in plot")
@click.option("--subgroups", is_flag=True, default=False, help="Plot averaged data per subgroup")
def main(data : str, out : str, avgplot : bool=False, simulation : bool=False, region : bool=False, events : bool=False, logx : bool=False, logy : bool=False, clus : str=None, fiber : str=None, maximum : float=10.0, subgroups : bool=False):

  # input data file
  for d in data:
    if(not os.path.isfile(d[0])):
      click.echo(f'Invalid data path: {d} must be a valid file path')
      return -1

  # output file
  if(os.path.isdir(out))or(not os.path.isdir(os.path.dirname(out))):
    click.echo(f'Invalid output path: "{out}" must be a writable file path')
    return
  else:
    out_filepath = out

  # input clus file
  if(clus is not None)and(not os.path.isfile(clus)):
    click.echo(f'Invalid cluster data path: {clus} must be a valid file path')
    return -1

  # input clus file
  if(fiber is not None)and(not os.path.isfile(fiber)):
    click.echo(f'Invalid fiber data path: {fiber} must be a valid file path')
    return -1

  # read data
  REGION = dict()
  DATA = dict()
  for d in data:
    REGION[d[1]] = None
    with open(d[0], 'r') as handle:
      tmp=list()
      for line in handle.readlines():
        line = line.rstrip()
        if(len(line)==0):
          continue
        if(line.startswith(":region ")):
          REGION[d[1]] = list(map(int, line.lstrip(":region ").split(","))) 
          continue
        if(not os.path.isfile(line)):
          click.echo(f'Invalid data path: {line} must be a valid file path')
          return -1
        tmp.append(line)
    DATA[d[1]] = tmp

  # read clus
  if(clus is not None):
    with open(clus, 'r') as handle:
      clus=list()
      for line in handle.readlines():
        line = line.rstrip()
        if(len(line)==0):
          continue
        if(not os.path.isfile(line)):
          click.echo(f'Invalid data path: {line} must be a valid file path')
          return -1
        clus.append(line)

  # read fiber
  if(fiber is not None):
    with open(fiber, 'r') as handle:
      fiber=list()
      for line in handle.readlines():
        line = line.rstrip()
        if(len(line)==0):
          continue
        if(not os.path.isfile(line)):
          click.echo(f'Invalid data path: {line} must be a valid file path')
          return -1
        fiber.append(line)

  # initialize the data structures
  #frm_avg_acf = list()
  frm_img_avg_med = dict()
  frm_params = dict()
  frm_model = dict()

  frm_dx = dict()
  frm_dt = dict()
  frm_txt = dict()
  frm_ev = dict()

  ## import data
  #TXT = list()
  #dT = list()
  #dX = list()
  #M = list()
  #EV = list()

  for k, d in DATA.items():
    frm_img_avg_med[k] = list()
    frm_params[k] = list()

    frm_dx[k] = list()
    frm_dt[k] = list()
    frm_txt[k] = list()
    frm_ev[k] = list()
    frm_model[k] = list()

    for f in d:
      with open(f, 'rb') as handle:
        click.echo(f'opened data file "{f}"')

        params, _, dx, dt, txt, ev, model, _, avg_med = read_in(handle, frm_params, tmp, frm_dx, frm_dt, frm_txt, frm_ev, frm_model, tmp, frm_img_avg_med)

        frm_params[k].append(params)
        frm_dx[k].append(dx)
        frm_dt[k].append(dt)
        frm_txt[k].append(txt)
        frm_ev[k].append(ev)
        frm_model[k].append(model)
        frm_img_avg_med[k].append(avg_med)

  if(clus is not None):
    sd=None
    frm_clusters = list()
    for f in clus:
      with open(f, 'rb') as handle:
        click.echo(f'opened cluster data file "{f}"')
        sd, clusters = read_in(handle, sd, frm_clusters)

        # average aster size
        avg_cluster_size = np.zeros([int(len(clusters)/10) + 1])
        avg_cluster_size.fill(np.nan)
        j = 0
        for i, k in enumerate(clusters.keys()):
          if((i % 10)!=0):
            continue
          c = clusters[k]
          cluster_size = []
          for idx, fibers in c.items():
            cluster_size.append(len(fibers))
          if(len(cluster_size)):
            avg_cluster_size[j] = np.nanmean(cluster_size)
          j+=1

        frm_clusters.append(avg_cluster_size)

  if(fiber is not None):
    sd=None
    frm_fiber_length = list()
    frm_fiber_count = list()
    for f in fiber:
      with open(f, 'rb') as handle:
        click.echo(f'opened fiber data file "{f}"')
        sd, fiber_length = read_in(handle, sd, sd)

        # average aster size
        avg_fiber_length = np.zeros([int(len(fiber_length)/10) + 1])
        avg_fiber_length.fill(np.nan)
        avg_fiber_count = np.zeros([int(len(fiber_length)/10) + 1])
        avg_fiber_count.fill(np.nan)
        j = 0
        for i, k in enumerate(fiber_length.keys()):
          if((i % 10)!=0):
            continue
          l = fiber_length[k]
          if(l['avg'][0] > 0.0):
            avg_fiber_length[j] = l['avg'][0]
          if(l['count'][0] > 0.0):
            avg_fiber_count[j] = l['count'][0]
          j += 1

        frm_fiber_length.append(avg_fiber_length)
        frm_fiber_count.append(avg_fiber_count)

  # plot
  click.echo(f'Plotting results...')
  
  ncols=2
  nrows=int(np.ceil(len(data)/float(ncols)))

  fig = plt.figure(figsize=(8*nrows, 8*ncols))
  
  # plot correlation length model fits
  cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
  for idx, d in enumerate(DATA):
    click.echo(f'Plot #{idx}...')
    ax = fig.add_subplot(nrows, ncols, idx+1)
    #ax2 = ax.twinx()
    txt = list(DATA.keys())
    title=txt[idx].replace('_', ' ')
    ax.set_title(title, fontsize=36)
    
    reg = REGION[txt[idx]]
    
    #LS_IDX[txt[idx]] = dict()

    # plot correlation length model fits
    t_min, t_max = np.nan, np.nan
    ls_data = []
    for f, params, dx, dt, ev, model, avgdata in zip(DATA[txt[idx]], frm_params[d], frm_dx[d], frm_dt[d], frm_ev[d], frm_model[d], frm_img_avg_med[d]):
      click.echo(f'Processing {f}...')
      
      
      label = f.replace('_', '\_')

      if(avgplot):
        
        tdata = np.asarray(range(avgdata.shape[0]), dtype=np.float) * dt/60.0
        
        #tck = sp.interpolate.splrep(tdata, avgdata[:,1], s=0.9)
        #median = sp.interpolate.splev(tdata, tck, der=0)
        
        #plotdata = avgdata[:,1] / avgdata[:,0] #avgdata[:,0] / median
        
        avg = avgdata[:,0] / avgdata[0,0]
        cov = avgdata[:,1] / avgdata[:,0]
        
        line, = ax.plot(tdata, avg, label=label, linewidth=3)
        ax.fill_between(tdata, avg + cov, avg - cov, color=line.get_color(), alpha=0.5)

        #print(np.std(avgdata[:,0]) / np.mean(avgdata[:,0]))
        
      else:
        tdata = np.asarray(range(params.shape[0]), dtype=np.float) * dt/60.0
        
        length_scale = np.zeros(params.shape[0], dtype=np.float)
        if(model == 'exp'):
          length_scale[:] = 1.0/params[:]
        elif(model == 'dblexp'):
          length_scale[:] = 1.0/np.min(params, axis=1)
        elif(model == 'scldblexp'):
          if(simulation):
            mask = params[:,0] <  0.5
            length_scale[mask] = 1.0/params[mask,1]
            mask = params[:,0] >= 0.5
            length_scale[mask] = 1.0/params[mask,2]
          else:
            mask = params[:,0] >  0.5
            length_scale[mask] = 1.0/params[mask,1]
            mask = params[:,0] <= 0.5
            length_scale[mask] = 1.0/params[mask,2]
          
          #length_scale[:] = params[:,0]/params[:,1] + (1.0 - params[:,0])/params[:,2]

          #ax.plot(tdata,params[:,0],'c')
          #ax.plot(tdata,params[:,1],'b')
          #ax.plot(tdata,params[:,2],'g')
        else:
          raise RuntimeError('Invalid model')

        if(subgroups):
          
          t1 = tdata.tolist()
          t1.append(t_min)
          t2 = tdata.tolist()
          t2.append(t_max)

          t_min, t_max = np.nanmin(t1), np.nanmax(t2)
          ls_data.append( (tdata, length_scale) )
        else:
          ax.scatter(tdata, length_scale, label=label)

      # process the events
      if(events and (len(ev) > 0)):
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        colors_idx = 0
        ev_colors = dict()
        for _ev in ev:
          print(_ev)
          #for i, e in _ev:
          i = _ev[0]
          e = _ev[1]

          if e not in ev_colors.keys():
            ev_colors[e] = colors[colors_idx]
            colors_idx += 1

        for i, e in ev:
          ax.vlines(tdata[int(i)], 1e-3, 1e3, linestyles="dotted", colors=ev_colors[e], label=e)
      
      if(clus is not None):
        clusters = frm_clusters[idx-1]
        
        ax2 = ax.twinx()
        
        ax2.plot(tdata,clusters,'y')
        ax2.set_ylim([1e0, 1e3])
        ax2.set_yscale('log')
        ax2.set_ylabel('Cluster size', fontsize=22)
        ax2.tick_params(axis='y', colors='y')

      if(fiber is not None):
        flenght = frm_fiber_length[idx-1]
        fcount = frm_fiber_count[idx-1]

        ax2 = ax.twinx()

        ax2.plot(tdata,flenght,'y')
        ax2.plot(tdata,fcount,'m')
        ax2.set_ylim([1e-3, 3e3])
        ax2.set_yscale('log')
        ax2.set_ylabel('Avg Length, $\mu$ m / Fiber Count', fontsize=22)
        ax2.tick_params(axis='y', colors='y')

    if(logy):
      ax.set_ylim([maximum*1e-2, maximum])
      ax.set_yscale('log')
    else:
      ax.set_ylim([0, maximum])
    
    if(region and (reg is not None)):
      ax.set_xlim(reg)
      #ax.axvspan(reg[0], reg[1], color='red', alpha=0.1)

    ax.set_xlabel('Time, min', fontsize=22)
    ax.set_ylabel('Correlation Distance, $\mu$ m', fontsize=22)
        
    if(subgroups):
      tavg = np.arange(t_min, t_max, 5.0)
      mavg = np.zeros(tavg.shape, dtype=np.float)
      savg = np.zeros(tavg.shape, dtype=np.float)
      
      lavg = list()
      for idx2 in range(len(tavg)):
        lavg.append([])
      
      for t, ls in ls_data:
        idx2 = np.digitize(t, tavg)
        for idx3, val in zip(idx2, ls):
          lavg[idx3-1].append(val)
          #print(f'{idx3} -> {val}')
      
      for idx2 in range(len(mavg)):
        mavg[idx2] = np.nanmean(np.asarray(lavg[idx2]))
        savg[idx2] = np.nanstd(np.asarray(lavg[idx2]))

      ax.plot(tavg, mavg, color=cycle[idx])
      ax.fill_between(tavg, mavg + savg, mavg - savg, color=cycle[idx], alpha=0.5)
    #ax.legend()

  fig.tight_layout()
  click.echo(f'Saving to {out_filepath}...')
  fig.savefig(f'{out_filepath}')
  plt.close(fig)

if __name__ == '__main__':
    main()


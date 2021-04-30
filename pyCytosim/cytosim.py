#!/usr/bin/env python3

import os
import sys

import asyncio
import pickle
import time
#import locale
import traceback


CS_FIBER_CLUS = 'clus'
CS_FIBER_POS  = 'pos'
CS_FIBER_END  = 'end'
CS_FIBER_LEN  = 'length'

CS_SINGLE_FORCE = 'single-force'

opts_dict = { CS_FIBER_CLUS : 'fiber:cluster', CS_FIBER_POS : 'fiber:position', CS_FIBER_END : 'fiber:end', CS_FIBER_LEN : 'fiber:length', CS_SINGLE_FORCE : 'single:force' }

###
# Report
###

# Report Protocol
class CytosimReportProtocol(asyncio.SubprocessProtocol):
  """
  Cytosim Live Ouput _parser
    done_future : future semaphore
    op          : operation (one of the listed above)
    simdir      : data & output directory
  """
  def __init__(self, done_future, op, simdir, fname):
    super().__init__()
    self._done_future = done_future
    self._op_name = opts_dict.get(op, lambda: 'invalid').replace(':','_')
    self._parser = getattr(self, self._op_name, None)
    if not callable(self._parser):
      raise RuntimeError('invalid operation')
    self._simdir = simdir
    self._fname = fname

    self._frm_idx = None
    self._buf = None
    self._data = dict()
    print(f"CytosimReportProtocol init")
  
  #
  # Single
  #
  
  def single_force(self, line):
    if(line is None):
      pass
      #self._data[self._frm_idx] = { 'count' : [], 'avg' : [], 'dev' : [], 'min' : [], 'max' : [], 'tot' : [] }
    if(line is not None):
      print('single_force: ' + line)
    
  #
  # Fiber analysis
  #

  def fiber_length(self, line):
    if(line is None):
      self._data[self._frm_idx] = { 'count' : [], 'avg' : [], 'dev' : [], 'min' : [], 'max' : [], 'tot' : [] }
    else:
      if(len(line) == 0):
        return
      try:
        cols = line.split(' ')
        fclass = cols[0]
        cols = list(map(float, filter(lambda x: len(x) > 0, cols[1:])))
      except:
        print('conversion failed: ' + line)
        return
      cnt = cols[0]
      len_avg = cols[1]
      len_dev = cols[2]
      len_min = cols[3]
      len_max = cols[4]
      len_tot = cols[5]
      self._data[self._frm_idx]['count'].append(cnt)
      self._data[self._frm_idx]['avg'].append(len_avg)
      self._data[self._frm_idx]['dev'].append(len_dev)
      self._data[self._frm_idx]['min'].append(len_min)
      self._data[self._frm_idx]['max'].append(len_max)
      self._data[self._frm_idx]['tot'].append(len_tot)

  def fiber_end(self, line):
    if(line is None):
      self._data[self._frm_idx] = dict()
    else:
      if(len(line) == 0):
        return
      try:
        cols = line.split(' ')
        cols = list(map(float, filter(lambda x: len(x) > 0, cols)))
      except:
        print('conversion failed: ' + line)
        return
      #fclass = cols[0]
      identity = int(cols[1])
      #length = cols[2]
      #stateM = cols[3]
      posM = cols[4:6]
      #dirM = cols[6:8]
      #stateP = cols[8]
      posP = cols[9:11]
      #dirP = cols[11:13]
      self._data[self._frm_idx][identity] = [posM, posP]

  def fiber_position(self, line):
    if(line is None):
      self._data[self._frm_idx] = dict()
    else:
      if(len(line) == 0):
        return
      try:
        cols = line.split(' ')
        cols = list(map(float, filter(lambda x: len(x) > 0, cols)))
      except:
        print('conversion failed: ' + line)
        return
      #fclass = cols[0]
      identity = int(cols[1])
      #length = cols[2]
      posC = cols[3:5]
      dirC = cols[5:7]
      #end2end = cols[7]
      cosC = cols[8]
      #aster = cols[9]
      self._data[self._frm_idx][identity] = [posC, dirC, cosC]

  def fiber_cluster(self, line):
    #print(f'CytosimReportProtocol fiber_cluster: {self._frm_idx} -> {line}')
    if(line is None):
      self._data[self._frm_idx] = dict()
    else:
      line = line.split(':')
      if(len(line) < 2):
        return
      clus_stats = list(filter(None, line[0].split(' ')))
      clus_fiber = list(filter(None, line[1].split(' ')))
      try:
        identity = int(clus_stats[0]) 
        fibers = list(map(int, clus_fiber))
      except:
        print('conversion failed: ' + line)
        return
      self._data[self._frm_idx][identity] = fibers

  #
  # pipe-driven I/O
  #
  
  # data received handle
  def pipe_data_received(self, fd, data):
    print(f"CytosimReportProtocol pipe_data_received: " + data.decode('ascii').rstrip())
    if(1 == fd):
      lines = data.decode('ascii')
      if(self._buf is not None):
        lines = self._buf + lines
        self._buf = None
      if(lines[-1] != '\n'):
        pos = lines.rfind('\n')
        self._buf = lines[(pos+1):]
        if pos == -1: return
        lines = lines[:pos]

      lines = lines.split('\n')
      for line in lines:
        line = line.rstrip()
        if(line[0:2] == '% '):
          # service line
          serv_str = line[2:]
          if(serv_str[0:5] == 'frame'):
            self._frm_idx = int(serv_str[5:].strip())
            print(f'processing frame index {self._frm_idx}')
            self._parser(None)
          if(serv_str[0:3] == 'end'):
            if(self._frm_idx is None):
              print('something went wrong: a frame ended before it began')
            else:
              print(f'frame index {self._frm_idx} DONE')
              self._frm_idx = None
          continue # ignore other service lines
        if( self._frm_idx is not None)and(len(line)):
          self._parser(line)
    if(2 == fd):
      print(f"CytosimReportProtocol pipe_data_received stderr: " + data.decode('ascii').rstrip())

  # process exited
  def process_exited(self):
    print(f"CytosimReportProtocol process_exited")
    if(self._buf is not None):
      print(f"CytosimReportProtocol process_exited: buffer = '{self._buf}'")
    with open(os.path.join(self._simdir, self._fname), 'wb') as handle:
      pickle.dump(self._simdir, handle, protocol=pickle.HIGHEST_PROTOCOL)
      pickle.dump(self._data,   handle, protocol=pickle.HIGHEST_PROTOCOL)
    self._done_future.set_result(self._data)

# Report Subprocess Factory
class CytosimReportSubprocessFactory:
  """
  Cytosim Subprocess Factory
  """
  def __init__(self, future, op, simdir, frames, out):
    self._cmd_report = os.path.expandvars('${CYTOSIMBINPATH}/report')
    if os.path.isfile(self._cmd_report) and os.access(self._cmd_report, os.X_OK):
      pass
    else:
      self._cmd_report = os.path.expandvars('${HOME}/.${DISTRIB_CODENAME}/bin/report')
    
    if os.path.isfile(self._cmd_report) and os.access(self._cmd_report, os.X_OK):
      pass
    else:
      raise RuntimeError("report executable not found")

    self._future = future
    self._op = op
    self._simdir = simdir
    self._frames = frames
    self._out = out
    pass

  def protocol(self):
    fname = CytosimReportSubprocessFactory.filename(self._op, self._frames)
    if(self._out is not None):
      fname = self._out + '_' + fname

    return CytosimReportProtocol(self._future, self._op, self._simdir, fname)

  def args(self):
    cmd = [self._cmd_report, opts_dict[self._op]]
    if(self._frames is not None):
      if(not isinstance(self._frames, list)):
        self._frames = [self._frames]
      cmd.append("frame=" + ",".join(map(str, self._frames)))
    print(f"args = {cmd}")
    #quit()
    return cmd

  def kwargs(self):
    print(f"cwd = {self._simdir}")
    return { 'cwd' : self._simdir }

  @staticmethod
  def filename(op, frames):
    suffix = None
    if(frames is not None):
      if(len(frames) == 1):
        suffix = str(frames[0])
      else:
        suffix = f'{min(frames)}-{max(frames)}'
    fname = opts_dict.get(op, lambda: 'invalid').replace(':','_')
    if(suffix  is not None):
      fname += '-' + suffix
    fname += '.pickle'
    return fname


###
# Play
###

# Play Protocol
class CytosimPlayProtocol(asyncio.SubprocessProtocol):
  """
  Cytosim live ouput parser
    done_future : future semaphore
    simdir      : data & output directory
  """
  def __init__(self, done_future, channel, out):
    super().__init__()
    self._done_future = done_future
    self._out = out

    print(f"CytosimPlayProtocol init")

  def pipe_data_received(self, fd, data):
    print(f"CytosimPlayProtocol pipe_data_received: " + data.decode('ascii').rstrip())
    if(1 == fd):
      print(f"CytosimPlayProtocol pipe_data_received stdout: " + data.decode('ascii').rstrip())
    if(2 == fd):
      print(f"CytosimPlayProtocol pipe_data_received stderr: " + data.decode('ascii').rstrip())

  def process_exited(self):
    print(f"CytosimPlayProtocol process_exited")
    self._done_future.set_result(self._out)

# Play Subprocess Factory
class CytosimPlaySubprocessFactory:
  """
  Cytosim Subprocess Factory
  """
  def __init__(self, future, channel, simdir, frames, tdir):
    self._cmd_play = 'play'
    if os.path.isfile(self._cmd_play) and os.access(self._cmd_play, os.X_OK):
      pass
    else:
      self._cmd_play = os.path.expandvars('$CYTOSIMBINPATH/play')
      if os.path.isfile(self._cmd_play) and os.access(self._cmd_play, os.X_OK):
        pass
      else:
        raise RuntimeError("play executable not found")

    self._future = future
    self._channel = channel
    self._simdir = simdir
    self._frames = frames
    self._tmpdir = tdir
    pass

  def protocol(self):
    return CytosimPlayProtocol(self._future, self._channel, self._tmpdir)

  def args(self):
    cmoName = os.path.join(self._simdir,f"objects.cmo")
    if(not os.path.isfile(cmoName)):
      cmoName = None
    cmd = [self._cmd_play, cmoName, "image", "image_format=png", "image_dir=" + self._tmpdir]

    if(self._frames is not None):
      if(not isinstance(self._frames, list)):
        self._frames = [self._frames]
      cmd.append("frame=" + ",".join(map(str, self._frames)))
    print(f"args = {cmd}")
    return cmd

  def kwargs(self):
    print(f"cwd = {self._tmpdir}")
    return { 'cwd' : self._tmpdir }

###
# Common
###

@asyncio.coroutine
def _run_jobs(loop, args):
  done, pending = None, None
  done_future = None

  done_futures = dict()
  transports = []
  results = dict()

  simdir = args['simdir']
  frames = args['frames'] if 'frames' in args.keys() else None

  try:
    # timing
    time_start = time.time()
    # run the process
    if(args['kind'] == 'report'):
      out = args['out'] if 'out' in args.keys() else None
      for op in args['ops']:
        results[op] = None
        done_futures[op] = asyncio.Future(loop = loop)
        factory = CytosimReportSubprocessFactory(done_futures[op], op, simdir, frames, out)

        transport, protocol = yield from loop.subprocess_exec(
          factory.protocol,
          *factory.args(),
          **factory.kwargs()
        )

        transports.append(transport)
    elif(args['kind'] == 'play'):
      for ch, tdir in zip(args['channels'],args['tmpdirs']):
        results[ch] = None
        done_futures[ch] = asyncio.Future(loop = loop)
        factory = CytosimPlaySubprocessFactory(done_futures[ch], ch, simdir, frames, tdir)

        transport, protocol = yield from loop.subprocess_exec(
          factory.protocol,
          *factory.args(),
          **factory.kwargs()
        )

        transports.append(transport)
    else:
      raise RuntimeError('unknown argument kind "' + args['kind'] + '"')

    done, pending = yield from asyncio.wait(done_futures.values(), loop=loop, return_when=asyncio.ALL_COMPLETED)

    #done_future = done.pop()
    if(args['kind'] == 'report'):
      for op in args['ops']:
        results[op] = done_futures[op].result()
    elif(args['kind'] == 'play'):
      for ch in args['channels']:
        results[ch] = done_futures[ch].result()

    #yield from done_future
  except Exception as e:
    #print(f'could not start process: {e}')
    print("Exception occured when starting a cytosim process:")
    print('BEGIN' + '-'*60)
    traceback.print_tb(e.__traceback__)
    traceback.print_exc(file=sys.stdout)
    print('END  ' + '-'*60)
  finally:
    if pending is not None:
      for future in pending: future.cancel()

    for transport in transports:
      if transport: transport.close()

    #if done_future is not None:
    #  return done_future.result()

    # timing
    time_stop = time.time()
    cnt='all'
    if(frames is not None):
      cnt=len(frames)
    num_ops = 1
    if('ops' in args.keys()):
      num_ops = len(args['ops'])

    print(f"done {num_ops} operation(s) over {cnt} frame(s) in {time_stop-time_start} seconds...", flush=True)

    return results

def run_cytosim_async_loop(args):
  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop) # bind event loop to current thread

  try:
    return loop.run_until_complete(_run_jobs(loop,args)) # run all jobs
  finally:
    loop.close()

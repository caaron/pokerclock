#!/usr/bin/env python
#
#   A Simple Poker Tournament Clock
#   (That supports sponsorship banner display)
#
# This software copyright (c) 2012 by Mayur Patel
# All Rights Reserved

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
# (1) Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# (2) Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#
#===============================================================================================
# v1.0.0 : Initial release.
# v1.1.0 : Added "perfect-fit" banner resizing, optional, slow.  
#          Made all layout management grid, not mixed grid/pack.
# v1.1.1 : Remove threads, use the Tk after() method to schedule events instead.
#          UI enhancements.
# v1.1.2 : Adjust refresh soas to make the update feel smoother without addn'l CPU load.
# v1.1.3 : Better error reporting relating to bad XML files.  
#          Experimental sound support on Mac and Linux.
# v1.2.0 : Improved performance for banner resizing
#          Support for JPEG and PNG banners (replacing PPM)
# 1.2.1 : Addressed linux, osx bugs involving full-screen frames
# 1.3.0 : Addressed more linux incompatibilities, removed full-frame, python 2.7 compatibility
#===============================================================================================
# 
#
import os
import sys
import traceback

import datetime
import math 

try:
  import tkinter
  from tkinter import filedialog
  from tkinter import messagebox
  from tkinter import tix
  from tkinter import font
  
except:
  import Tkinter as tkinter
  import tkFileDialog as filedialog
  import tkMessageBox as messagebox
  import Tix as tix
  import tkFont as font
  
 
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

import glob
import random

import nanojpeg_13b as nanojpeg # JPEG image file support
import png # PNG image file support
import array
import multiprocessing

#===============================================================================================
# free ringtones, need to be converted from mp4 to wav:
# http://www.partnersinrhyme.com/blog/download-200-free-iphone-ringtones-no-strings-attached/

if sys.platform.startswith('win') or sys.platform.startswith('cygwin') :
  import winsound
elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
  import wave
  import ossaudiodev
  try:
    from ossaudiodev import AFMT_S16_NE
  except ImportError:
    if byteorder == "little":
      AFMT_S16_NE = ossaudiodev.AFMT_S16_LE
    else:
      AFMT_S16_NE = ossaudiodev.AFMT_S16_BE
elif sys.platform.startswith('darwin'):
  import subprocess

#===============================================================================================

BOLDFONT = "Helvetica -%d bold" # size  |  negative number is pixels, positive number is points
FONT = "Helvetica -%d"

SOUND_LEVELWARNING = "warning.wav"
SOUND_LEVELCHANGE = "newlevel.wav"
SOUND_TIMEBARRIER = 10

TITLE = "Tournament Clock"

#===============================================================================================
def safe_int(i):
  "fault-tolerant conversion to integer"
  try :
    x = int(i)
  except ValueError :
    x = 0
  return x

  
def seconds_to_text(x) :
  "nice formating for hours/minutes/seconds"
  h = x // (60 * 60)
  m = (x - h * 60 * 60) // 60
  s = (x - h * 60 * 60) % 60
  ret = ''
  if 0 != h :
    ret = '%d:%02d:%02d' % (h, m, s)
  elif 0 != m :
    ret = '%d:%02d' % (m, s)
  else:
    ret = '%ds' % s
  return ret
  
def integer_to_compacttext(i) :
  ret = ''
  if i < 1000 :
    ret = "%d" % i
  elif i < 1000000 :
    x = ( i + 50 ) // 100
    ret = '%d.%dk' % (x / 10, x % 10)
  elif i < 1000000000 :
    x = ( i + 50000 ) // 100000
    ret = '%d.%dM' % (x / 10, x % 10)
  else :
    x = ( i + 50000000 ) // 100000000
    ret = '%d.%dB' % (x / 10, x % 10)
  return ret


#===============================================================================================

class Tournament(object):
  def __init__(self) :
    self._tournament_title = "Tournament"

    self._banners_path = None
    self._banners_seconds = 60
    
    self._sounds_path = None
    
    self._players_start = 0
    self._players_startstack = 10000
    self._players_paid = 0
    self._players_out = 0
    self._players_addon = 0
    self._players_addonstack = 0
    self._players_rebuy = 0
    self._players_rebuystack = 0
    
    self._timeblocks = [] # tuples of the form (start_at_seconds, duration, name, is_break)
    self._current_timeblock = 0
    
    self._pause = True # start the tournament(?)
    
  @property
  def tournament_title(self):
    return self._tournament_title

  @tournament_title.setter
  def tournament_title(self, value):
    self._tournament_title = value

  @property
  def banners_path(self):
    return self._banners_path
    
  @banners_path.setter
  def banners_path(self, value):
    self._banners_path = value
  
  @property
  def banners_seconds(self):
    return self._banners_seconds

  @banners_seconds.setter
  def banners_seconds(self, value):
    self._banners_seconds = safe_int(value)
  
  @property
  def sounds_path(self):
    return self._sounds_path
    
  @sounds_path.setter
  def sounds_path(self, value):
    self._sounds_path = value
    
  @property
  def players_startstack(self):
    return self._players_startstack
    
  @players_startstack.setter
  def players_startstack(self, value):
    self._players_startstack = safe_int(value)
    
  @property
  def players_start(self):
    return self._players_start
    
  @players_start.setter
  def players_start(self, value):
    self._players_start = safe_int(value)  
    
  @property
  def players_paid(self):
    return self._players_paid
    
  @players_paid.setter
  def players_paid(self, value):
    self._players_paid = safe_int(value)  
    
  @property
  def players_out(self):
    return self._players_out
    
  @players_out.setter
  def players_out(self, value):
    self._players_out = safe_int(value)  
    
  @property
  def players_addon(self):
    return self._players_addon
    
  @players_addon.setter
  def players_addon(self, value):
    self._players_addon = safe_int(value)  
    
  @property
  def players_addonstack(self):
    return self._players_addonstack
    
  @players_addonstack.setter
  def players_addonstack(self, value):
    self._players_addonstack = safe_int(value)
    
  @property
  def players_rebuy(self):
    return self._players_rebuy
    
  @players_rebuy.setter
  def players_rebuy(self, value):
    self._players_rebuy = safe_int(value)  

  @property
  def players_rebuystack(self):
    return self._players_rebuystack
    
  @players_rebuystack.setter
  def players_rebuystack(self, value):
    self._players_rebuystack = safe_int(value)
    
  def add_level(self, name, minutes):
    if self._timeblocks :
      last_level = self._timeblocks[-1]
      self._timeblocks.append( (last_level[0] + last_level[1], minutes * 60, name, False ))
    else :
      self._timeblocks.append( (0, minutes * 60, name, False ) )
    
  def add_break(self, name, minutes):
    if self._timeblocks :
      last_level = self._timeblocks[-1]
      self._timeblocks.append( (last_level[0] + last_level[1], minutes * 60, name, True ))
    else :
      self._timeblocks.append( (0, minutes * 60, name, True ) )
    
  def get_timeblocks(self):
    return self._timeblocks
    

#===============================================================================================

class XMLEventHandler(ContentHandler): 
  def __init__(self, tournament) :
    self._t = tournament
    
  def startElement(self, name, attrs):
    if name == 'tournament':
      self._t.tournament_title = attrs.get('title',"")
    elif name == 'banners':   
      self._t.banners_path = attrs.get('path',"")
      self._t.banners_seconds = safe_int(float(attrs.get('minutes',"")) * 60)
    elif name == 'sounds':
      self._t.sounds_path = attrs.get('path',"")
    elif name == 'players':
      self._t.players_startstack = attrs.get('startstack',"")
      self._t.players_start = attrs.get('start',"")
      self._t.players_out = attrs.get('out',"")
      self._t.players_addon = attrs.get('addon',"")
      self._t.players_addonstack = attrs.get('addonstack',"")
      self._t.players_rebuy = attrs.get('rebuy',"")
      self._t.players_rebuystack = attrs.get('rebuystack',"")
      self._t.players_paid = attrs.get('paid',"")
    elif name == 'level':
      self._t.add_level(attrs.get('name',""), safe_int(attrs.get('minutes',"")))
    elif name == 'break':
      self._t.add_break(attrs.get('name',""), safe_int(attrs.get('minutes',"")))

  def endElement(self, name): 
    pass
    
#===============================================================================================

class TimeCursor(object):
  def __init__(self, tournament):
    self._t = tournament
    self._run = False
    self._now = datetime.datetime.now()
    self._begin = datetime.datetime.now()
    self._block = 0
    
  def goto_timeblock(self, i):
    sec = 0
    blocks = self._t.get_timeblocks()
    self._block = max(0, min(i, len(blocks)-1))
    level = blocks[ self._block ]
    self._now = datetime.datetime.now()
    self._begin = self._now - datetime.timedelta(seconds=level[0])
    
    
  def goto_time(self, sec):
    self._now = datetime.datetime.now()
    self._begin = self._now - datetime.timedelta(seconds=sec)
    blocks = self._t.get_timeblocks()
    self._block = len(blocks) - 1 # end of blocks 
    for x in range(len(blocks)) :
      if blocks[x][0] + blocks[x][1] > sec :
        self._block = x
        break # early exit
    return
    
  def _get_timeblock(self, index):
    "returns a dictionary, to try to abstract out the representation"
    try:
      timeblock = self._t.get_timeblocks()[ index ]
      ret = { 'starttime' : timeblock[0], 'duration': timeblock[1] , 'name' : timeblock[2], 'isbreak' : timeblock[3] }
    except:
      ret = None
      pass
    return ret
    
  def get_current_timeblock(self):
    "returns a dictionary, to try to abstract out the representation"
    return self._get_timeblock( self._block )
    
  def get_current_timeblock_index(self):
    return self._block

  def get_next_level(self):
    "returns a dictionary, to try to abstract out the representation"
    blocks = self._t.get_timeblocks()
    for x in range(self._block+1, len(blocks)):
      if not blocks[x][3] :
        return self._get_timeblock(x) # early exit
    return None
    
  def get_next_break(self):
    "returns a dictionary, to try to abstract out the representation"
    blocks = self._t.get_timeblocks()
    for x in range(self._block+1, len(blocks)):
      if blocks[x][3] :
        return self._get_timeblock(x) # early exit
    return None
    
  def get_elapsed_seconds(self):
    return( self._now - self._begin ).total_seconds()
    
  def press_pause(self):
    if self._run :
      self._run = False
    
  def press_play(self):
    if not self._run :
      duration = self._now - self._begin
      self._now = datetime.datetime.now()
      self._begin = self._now - duration
      self._run = True
      
  def is_playing(self):
    return self._run
      
  def tick(self):
    "Called periodically to keep the cursor up to date"
    if self._run :
      self._now = datetime.datetime.now()
      sec = self.get_elapsed_seconds()
      timeblock = self._t.get_timeblocks()[ self._block ]
      if sec >= ( timeblock[0] + timeblock[1] ) :
        self._block = min( len(self._t.get_timeblocks()) - 1, self._block + 1 )
    return
    

#===============================================================================================

class SoundMan( object ):

  def __init__(self, tournament) :
    self._last_time = datetime.datetime.now()
    self._path = tournament.sounds_path
    if sys.platform.startswith('darwin'):
      self._sound_proc = None
      
  def __del__(self):
    if sys.platform.startswith('darwin'):
      if self._sound_proc is not None :
        self._sound_proc.wait()
        self._sound_proc = None

  def sound_check(self) :
    "play all sounds, to verify all works"
    self._sound_check_file( os.path.join(self._path, SOUND_LEVELWARNING))
    self._sound_check_file(os.path.join(self._path, SOUND_LEVELCHANGE))

  def play_warning(self) :
    filename = os.path.join(self._path, SOUND_LEVELWARNING)
    self._play(filename)
    
  def play_blockchange(self) :
    filename = os.path.join(self._path, SOUND_LEVELCHANGE)
    self._play(filename)
    
  def _play_block(self):
    "Don't play sounds back to back - after a sound has played, give some dead time"
    now = datetime.datetime.now()
    ret = (now - self._last_time ).total_seconds() < SOUND_TIMEBARRIER
    self._last_time = now
    return ret
    
  def _play(self, filename):
    # reference stackoverflow 3498313
    if (not self._play_block()) and os.path.isfile(filename):
      if sys.platform.startswith('win') or sys.platform.startswith('cygwin'):      
        try:
          winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NOWAIT)
        except:
          pass
      elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd') :
        try:
          fp = wave.open(filename, 'rb')
          (nchannels, sampwidth, framerate, nframes, comptype, compname) = fp.getparams()
          dsp = ossaudiodev.open(mode='w')
          dsp.setparameters(AFMT_S16_NE, nchannels, framerate)
          data = fp.read(nframes)
          fp.close()
          dsp.nonblock()
          dsp.writeall(data)
          dsp.close()
        except:
          pass
      elif sys.platform.startswith('darwin'):
        # do paths need to be absolute?  filename = os.path.abspath(filename) ?
        try:
          if self._sound_proc is not None:
            self._sound_proc.wait()
            self._sound_proc = None
            
          self._sound_proc = subprocess.Popen(['afplay', filename])
        except:
          pass
          

  def _sound_check_file(self, filename):
    if os.path.isfile(filename):
      try:
        if sys.platform.startswith('win') or sys.platform.startswith('cygwin'):
          winsound.PlaySound(filename, winsound.SND_FILENAME)
          
        elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
          fp = wave.open(filename, 'rb')
          (nchannels, sampwidth, framerate, nframes, comptype, compname) = fp.getparams()
          dsp = ossaudiodev.open(mode='w')
          dsp.setparameters(AFMT_S16_NE, nchannels, framerate)
          data = fp.read(nframes)
          fp.close()
          dsp.write(data)
          dsp.close()

        elif sys.platform.startswith('darwin'):
          # do paths need to be absolute?  filename = os.path.abspath(filename) ?
          subprocess.call(['afplay', filename])
      except:
        messagebox.showerror(TITLE, "Sound %s failed" % filename)
    else:
      messagebox.showerror(TITLE, "No file called %s" % filename)
    
#===============================================================================================

class DisplayMan(object):
  def __init__(self) :
    self._app = None
    
    self.root = tkinter.Tk()
    self.root.title(TITLE)
    self.root.columnconfigure(0, weight=1)
    self.root.rowconfigure(0, weight=1)
    width = self.root.winfo_screenwidth()
    height = self.root.winfo_screenheight()
    
    self._str_title = tkinter.StringVar()
    self._str_level = tkinter.StringVar()
    self._str_timer = tkinter.StringVar()
    self._str_next = tkinter.StringVar()
    self._str_break = tkinter.StringVar()
    
    self._str_players = tkinter.StringVar()
    self._str_addons = tkinter.StringVar()
    self._str_rebuys = tkinter.StringVar()
    self._str_avestack = tkinter.StringVar()
    self._str_totalstack = tkinter.StringVar()
    self._str_paid = tkinter.StringVar()
    
    self.root.frame_full = tkinter.Frame(self.root)
    self.root.frame_full.configure(width=width, height=height)
    self.root.frame_full.columnconfigure(0,weight=1)
    self.root.frame_full.grid(row=0,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.root.frame_full.rowconfigure(0, weight=2)
    self.root.frame_full.rowconfigure(1, weight=5)
    self.root.frame_full.rowconfigure(2, weight=1)
    self.root.frame_full.rowconfigure(3, weight=5)
    
    height_five = height * 5 // 100
    height_one = (height * 5) // 440
    
    self.font_1 = font.Font(font=BOLDFONT % height_one)
    self.font_2 = font.Font(font=BOLDFONT % (height_five * 2))
    self.font_3 = font.Font(font=BOLDFONT % (height_five * 3))
    self.font_4 = font.Font(font=BOLDFONT % height_five)
    self.font_5 = font.Font(font=BOLDFONT % ((height_five * 4) // 7))
    
    self.top_frame = tkinter.Frame(self.root.frame_full)
    self.top_frame.configure(width=width, height=height_five * 2)
    self.top_frame.grid(row=0,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    self.top_frame.columnconfigure(0,weight=1)
    
    self.label_title = tkinter.Label(self.top_frame, textvariable=self._str_title, font=self.font_4, fg="white", bg="black")
    self.label_title.grid(row=0, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.middle_frame = tkinter.Frame(self.root.frame_full)
    self.middle_frame.configure(width=width, height=height_five * 5)
    self.middle_frame.columnconfigure(0, weight=30)
    self.middle_frame.columnconfigure(1, weight=30)
    self.middle_frame.columnconfigure(2, weight=1)
    self.middle_frame.rowconfigure(0,weight=1)
    self.middle_frame.grid(row=1, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.midleft_frame = tkinter.Frame(self.middle_frame)
    self.midleft_frame.configure(width=width * 50 // 100, height=height_five * 5)
    self.midleft_frame.columnconfigure(0,weight=1)
    self.midleft_frame.grid(row=0,column=0,sticky=tkinter.N+tkinter.S+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_level = tkinter.Label(self.midleft_frame, textvariable=self._str_level, font=self.font_2, fg="black", bg="yellow")
    self.label_level.grid(row=0, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_timer = tkinter.Label(self.midleft_frame, textvariable=self._str_timer, font=self.font_3, fg="black", bg="white")
    self.label_timer.grid(row=1, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.midright_frame = tkinter.Frame(self.middle_frame)
    self.midright_frame.configure(width=width* 40 // 100, height=height_five * 5)
    self.midright_frame.columnconfigure(0,weight=1)
    self.midright_frame.grid(row=0,column=1,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_next = tkinter.Label(self.midleft_frame, textvariable=self._str_next, font=self.font_4, fg="black", bg="light gray")
    self.label_next.grid(row=2, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.label_break = tkinter.Label(self.midright_frame, textvariable=self._str_break, font=self.font_4, fg="black", bg="light gray")
    self.label_break.grid(row=0, sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_players = tkinter.Label(self.midright_frame, textvariable=self._str_players, font=self.font_4, fg="black", bg="white")
    self.label_players.grid(row=1,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_paid = tkinter.Label(self.midright_frame, textvariable=self._str_paid, font=self.font_5, fg="black", bg="light gray")
    self.label_paid.grid(row=2,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_addons = tkinter.Label(self.midright_frame, textvariable=self._str_addons, font=self.font_5, fg="black", bg="light gray")
    self.label_addons.grid(row=3,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_rebuys = tkinter.Label(self.midright_frame, textvariable=self._str_rebuys, font=self.font_5, fg="black", bg="light gray")
    self.label_rebuys.grid(row=4,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_avestack = tkinter.Label(self.midright_frame, textvariable=self._str_avestack, font=self.font_4, fg="black", bg="white")
    self.label_avestack.grid(row=5,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
  
    self.label_totalstack = tkinter.Label(self.midright_frame, textvariable=self._str_totalstack, font=self.font_4, fg="light gray", bg="white")
    self.label_totalstack.grid(row=6,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
  
    self.midcontrol_frame = tkinter.Frame(self.middle_frame)
    self.midcontrol_frame.configure(width=width * 10 // 100, height=height_five * 5)
    self.midcontrol_frame.columnconfigure(0,weight=1)
    self.midcontrol_frame.grid(row=0,column=2,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_outs_plus = tix.Button(self.midcontrol_frame, text='OUTS +', font=self.font_1, command=self.press_outs_plus)
    self.button_outs_plus.grid(row=0,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.button_outs_minus = tix.Button(self.midcontrol_frame, text='OUTS -', font=self.font_1, command=self.press_outs_minus)
    self.button_outs_minus.grid(row=1,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_entries_plus = tix.Button(self.midcontrol_frame, text='ENTRIES +', font=self.font_1, command=self.press_entries_plus)
    self.button_entries_plus.grid(row=2,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_entries_minus = tix.Button(self.midcontrol_frame, text='ENTRIES -', font=self.font_1, command=self.press_entries_minus)
    self.button_entries_minus.grid(row=3,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_paid_plus = tix.Button(self.midcontrol_frame, text='PAID +', font=self.font_1, command=self.press_paid_plus)
    self.button_paid_plus.grid(row=4,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.button_paid_minus = tix.Button(self.midcontrol_frame, text='PAID -', font=self.font_1, command=self.press_paid_minus)
    self.button_paid_minus.grid(row=5,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.button_addons_plus = tix.Button(self.midcontrol_frame, text='ADDONS +', font=self.font_1, command=self.press_addons_plus)
    self.button_addons_plus.grid(row=6,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_addons_minus = tix.Button(self.midcontrol_frame, text='ADDONS -', font=self.font_1, command=self.press_addons_minus)
    self.button_addons_minus.grid(row=7,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_rebuys_plus = tix.Button(self.midcontrol_frame, text='REBUYS +', font=self.font_1, command=self.press_rebuys_plus)
    self.button_rebuys_plus.grid(row=8,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.button_rebuys_minus = tix.Button(self.midcontrol_frame, text='REBUYS -', font=self.font_1, command=self.press_rebuys_minus)
    self.button_rebuys_minus.grid(row=9,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_level_plus = tix.Button(self.midcontrol_frame, text='LEVEL +', font=self.font_1, command=self.press_level_plus)
    self.button_level_plus.grid(row=10,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)

    self.button_level_minus = tix.Button(self.midcontrol_frame, text='LEVEL -', font=self.font_1, command=self.press_level_minus)
    self.button_level_minus.grid(row=11,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_end = tix.Button(self.midcontrol_frame, text='END', font=self.font_1, command=self.press_end)
    self.button_end.grid(row=12,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.button_pause = tix.Button(self.midcontrol_frame, text='PAUSE', font=self.font_1, command=self.press_pause)
    self.button_pause.grid(row=13,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.scale_timescrub = tkinter.Scale(self.root.frame_full, from_=0, to=60, width=6, orient=tkinter.HORIZONTAL, showvalue=0)
    self.scale_timescrub.grid(row=2,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    self.scale_timescrub.bind('<Button-1>', self.press_scrub)
    self.scale_timescrub.bind('<ButtonRelease-1>', self.release_scrub)
    
    self.bottom_frame = tkinter.Frame(self.root.frame_full)
    self.bottom_frame.configure(width=width, height=height_five * 13)
    self.bottom_frame.columnconfigure(0,weight=5)
    self.bottom_frame.grid(row=3,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self.label_banner = tkinter.Label(self.bottom_frame, fg='black', bg='white', borderwidth=0)
    self.label_banner.grid(row=0,sticky=tkinter.N+tkinter.S+tkinter.E+tkinter.W)
    
    self._last_resize = datetime.datetime.now()
    self.root.frame_full.bind("<Configure>", self.resize_fonts)
    self.root.withdraw()
    
  def resize_fonts(self, event):
    now = datetime.datetime.now()
    if (now - self._last_resize).total_seconds() > 0.5 :
      width = self.root.frame_full.winfo_width()
      height = self.root.frame_full.winfo_height()
      screenheight = self.root.frame_full.winfo_screenheight()
      
      height_five = max(1, (height-((screenheight * 40) // 100)) * 5 // 50)
      height_one = max(1, ((height-((screenheight * 40) // 100)) * 5) // 220)
      
      self.font_1.configure(size=-height_one)
      self.font_2.configure(size=(height_five * -2))
      self.font_3.configure(size=(height_five * -3))
      self.font_4.configure(size=-height_five)
      self.font_5.configure(size=(height_five * -4) // 7)
      self._last_resize = now
    return "break" # swallow the event (doesn't seem to be working)
    
  def use_warning_colors(self):
    if 'red' != self.label_timer.cget('fg') :
        self.label_timer.configure(fg='red')
    
  def unuse_warning_colors(self):
    if 'black' != self.label_timer.cget('fg') :
        self.label_timer.configure(fg='black')
    
  def init_app(self, app ):
    "open the window, set up the widgets, etc"
    self._app = app
    self._str_title.set( app.tournament.tournament_title )    
    self.display_player_info()
    
  def run(self) :
    self.root.deiconify()
    self.root.mainloop()
    self.root.quit()
    
  def start_timer(self, ms, callback, *args):
    "ms should be an integer"
    return self.root.after(int(ms), callback, *args)
  
  def cancel_timer(self, id):
    self.root.after_cancel(id)
    
  def press_scrub(self, event):
    self._app.hold()
    return
    
  def release_scrub(self, event):
    scale_widget = event.widget
    self._app.time_cursor.goto_time(scale_widget.get())
    self._app.clock_controller.update_time_info(do_force=True)
    self._app.unhold()
    
  def configure_scrub(self, min, max, current):
    self.scale_timescrub.configure(from_=min, to=max)
    self.scale_timescrub.set(current)
    return
    
  def advance_scrub(self, value) :
    self.scale_timescrub.set(value)
    return
    
  def apply_banner(self, im):
    self.label_banner.configure(image=im, fg='black', bg='white', anchor=tkinter.CENTER)
    return
    
  def get_ideal_banner_size(self):
    width = self.root.winfo_screenwidth()
    height = self.root.winfo_screenheight()
    return (width * 90 // 100, height * 40 // 100)
    
  def press_entries_plus(self):
    self._app.tournament.players_start += 1
    self.display_player_info()
  
  def press_entries_minus(self):
    self._app.tournament.players_start -= 1
    self.display_player_info()

  def press_outs_plus(self):
    self._app.tournament.players_out += 1
    self.display_player_info()
  
  def press_outs_minus(self):
    self._app.tournament.players_out -= 1
    self.display_player_info()

  def press_addons_plus(self):
    self._app.tournament.players_addon += 1
    self.display_player_info()
  
  def press_addons_minus(self):
    self._app.tournament.players_addon -= 1
    self.display_player_info()

  def press_rebuys_plus(self):
    self._app.tournament.players_rebuy += 1
    self.display_player_info()
  
  def press_rebuys_minus(self):
    self._app.tournament.players_rebuy -= 1
    self.display_player_info()

  def press_paid_plus(self):
    self._app.tournament.players_paid += 1
    self.display_player_info()
  
  def press_paid_minus(self):
    self._app.tournament.players_paid -= 1
    self.display_player_info()
    
  def press_level_plus(self):
    i = self._app.time_cursor.get_current_timeblock_index()
    self._app.time_cursor.goto_timeblock(i + 1)
    self._app.clock_controller.update_time_info(do_force=True)
  
  def press_level_minus(self):
    i = self._app.time_cursor.get_current_timeblock_index()
    self._app.time_cursor.goto_timeblock(i - 1)
    self._app.clock_controller.update_time_info(do_force=True)
    
  def press_end(self):
    if self._app :
      self._app.hold()
      if messagebox.askyesno(TITLE, "Do you want to exit?") :
        self._app.shutdown() # ends threads
        sys.exit(0)
      else :
        self._app.unhold()

  def press_pause(self):
    if self._app.time_cursor.is_playing() :
      self._app.press_pause()
    else:
      self._app.press_play()

    
  def display_player_info(self):
    remaining_players = app.tournament.players_start - app.tournament.players_out
    self._str_players.set("%d / %s" % (remaining_players, app.tournament.players_start))
    if app.tournament.players_addonstack :
      self._str_addons.set("Addons: %s" % app.tournament.players_addon)
    else:
      self._str_addons.set('')
    if app.tournament.players_rebuystack :
      self._str_rebuys.set("Rebuys: %s" % app.tournament.players_rebuy)
    else:
      self._str_rebuys.set('')
    
    if app.tournament.players_paid :
      self._str_paid.set("Paid: %s" % app.tournament.players_paid)
    else:
      self._str_paid.set('')

    if app.tournament.players_start != app.tournament.players_out :
      total_chips = app.tournament.players_start * app.tournament.players_startstack
      total_chips += app.tournament.players_addon * app.tournament.players_addonstack
      total_chips += app.tournament.players_rebuy * app.tournament.players_rebuystack
      self._str_avestack.set("Avg Chip: %s" % integer_to_compacttext( total_chips // remaining_players ))
      self._str_totalstack.set("Total Chip: %s" % integer_to_compacttext( total_chips ))
    
      
  def display_time_info(self, level_title, level_time, next_title, next_time, break_title, break_time):
    self._str_timer.set(level_time)
    self._str_level.set("%s" % level_title)
    if next_title :
      self._str_next.set("Next: %s" % next_title)
    else:
      self._str_next.set('')
    if break_title and break_time :
      self._str_break.set("%s: %s" % (break_title, break_time))
    else :
      self._str_break.set('')


#===============================================================================================
  
class ClockController( object ):
  def __init__(self, display_man, sound_man, time_cursor):
    self._display_man = display_man
    self._sound_man = sound_man
    
    self._time_cursor = time_cursor
    self._run = False
    self._timer = None
    
    self._lasttime = 999999999
    self._lastlevel = -999999

  def __del__(self):
    if self._timer :
      self._display_man.cancel_timer( self._timer )
      self._timer = None
    
  def press_pause(self):
    if self._run :
      self._run = False
    
  def press_play(self):
    if not self._run :
      self._run = True
      self.update_time_info()

  def update_time_info(self, do_force=False):
    if self._run or do_force:
      self._timer = self._display_man.start_timer( 99, self.update_time_info)

      self._time_cursor.tick()
      
      #
      # update visuals:
      #
      now = self._time_cursor.get_elapsed_seconds()      
      if int(self._lasttime) != int(now) or do_force :
        # Even though we're triggering the timer frequently, we only update
        # when a second has elapsed.  This keeps CPU load low.  We continue to
        # test for update frequently, mainly to hide studders in the timer
        # update that users might perceive.  By triggering for updates frequently
        # then we can insure that the timer is never so far out of date that the
        # user would notice when it "caught up" with itself.
        current = self._time_cursor.get_current_timeblock()    
        next_level = self._time_cursor.get_next_level()
        next_break = self._time_cursor.get_next_break()
        
        level_title = ''
        level_time = ''
        if current :
          level_title = current['name']
          level_time = seconds_to_text( 0.5 + current['starttime'] + current['duration'] - now )
        next_title = ''
        next_time = ''
        if next_level :
          next_title = next_level['name']
          next_time = seconds_to_text( 0.5 + next_level['starttime'] - now )
        break_title = ''
        break_time = ''
        if next_break :
          break_title = next_break['name']
          break_time = seconds_to_text( 0.5 + next_break['starttime'] - now )

        self._display_man.display_time_info(level_title, level_time, next_title, next_time, break_title, break_time)
        
        #
        # advance scrubber
        #
        if self._lastlevel != current['starttime'] :
          self._lastlevel = current['starttime']
          self._display_man.configure_scrub( current['starttime'], current['starttime'] + current['duration'], now )
        else:
          self._display_man.advance_scrub(now)
        
        #
        # plays sounds:
        #
        if current['starttime'] > self._lasttime :
          self._sound_man.play_blockchange()
        else:
          if current['duration'] > 60 :
            warning_threshold = current['starttime'] + current['duration'] - 60
            if self._lasttime< warning_threshold and now >= warning_threshold :
              self._sound_man.play_warning()
            warning_threshold = current['starttime'] + current['duration'] - 10
            if self._lasttime< warning_threshold and now >= warning_threshold :
              self._sound_man.play_warning()
              
        # warning colors?
        warning_threshold = current['starttime'] + current['duration'] - 10
        if now >= warning_threshold :
          self._display_man.use_warning_colors()
        else:
          self._display_man.unuse_warning_colors()
          
        self._lasttime = now

    return

#===============================================================================================
def _img_resize(Source, TgtWidth, TgtHeight):
  def get_incrlist(inwidth, outwidth, oversize=False):
    izoom = int(10000.0 * float(inwidth) / float(outwidth))
    delta = 0
    size = outwidth
    if oversize :
      size += 2
    ret = [0] * size
    for x in range(size) :
      delta += izoom
      jump = delta // 10000
      delta -= jump * 10000
      ret[x] = jump
    return ret
  
  Source_width = Source[0]
  Source_height = Source[1]
  img_list = Source[2]

  for y in range(Source_height) : # box pixels, box rows
    img_list[y] = [tuple(img_list[y][x:x+3]) for x in range(0,Source_width*3,3)]
    
  relative_width = float(Source_width) / float(TgtWidth)
  relative_height = float(Source_height) / float(TgtHeight)
  rel = max(relative_width, relative_height)
  if rel == 0 :
    return Source
  target_width = int(Source_width / rel)
  target_height = int(Source_height / rel)
  
  # cache these calculations, as python can be slow...
  xincrlist = get_incrlist(Source_width, target_width, True)
  yincrlist = get_incrlist(Source_height, target_height)
  
  i=0
  xlist = []
  for x in range(target_width):
    xlist.append(i)
    i += xincrlist[x]
    
  j = 0
  output_img = []
  for y in range(target_height) :
    output_img.append([img_list[j][xlist[x]] for x in range(target_width)])
    j += yincrlist[y]

  return (target_width, target_height, output_img)

def _read_JPG(filename) :
  try :
    nj = nanojpeg.NJ()
    nanojpeg.njInit(nj)
    buf = open(filename, 'rb').read()
    buf = array.array('B', buf)
    nanojpeg.njDecode(nj, buf, len(buf))
    width = nanojpeg.njGetWidth(nj)
    height = nanojpeg.njGetHeight(nj)
    pixels = nanojpeg.njGetImage(nj)
    row_pixels = [pixels[y:y+width*3] for y in range(0,width*height*3,width*3)] # box rows flat pixels
    return (width, height, row_pixels)
  except:
    return(0,0,None,filename)
  

def _read_PNG(filename) :
  try :
    fp = png.Reader(filename = filename)
    width, height, pixels, metadata = fp.asRGBA() # don't raise an exception with alpha, just filter it out
    if height > 0 and pixels is not None :
      no_alpha_indices = list(range(width*4))
      del no_alpha_indices[3::4]
      pixels = [[(row[x] * row[x | 0x03] + (255 - row[x | 0x03]) * 255)//255 for x in no_alpha_indices ] for row in pixels] # comp over white
      
    return (width, height, pixels, filename)
  except:
    return(0,0,None,filename)
      
def _convert_to_photoimage(img):
  width = img[0]
  height = img[1]
  pixels = img[2]
  
  Target = tkinter.PhotoImage(width=width, height=height)
  for y in range(height) :
    pixelrow = ["#%02x%02x%02x" % x for x in pixels[y]]
    pixelrow = '{%s}' % ' '.join(pixelrow)
    Target.put(pixelrow, to=(0, y))
  return Target

class BannerController( object ) :
  def __init__(self, banner_seconds, banner_path, display_man):
    
    self._banner_duration = int(banner_seconds)
    self._banner_list = []
    if os.path.isdir( banner_path ):
      messagebox.showinfo(TITLE, "Please wait while banners are processed.  It may take a few minutes.")
      pool = multiprocessing.Pool()
      for x in glob.glob( os.path.join( banner_path, "*.jpg" )) :
        self._banner_list.append(pool.apply_async(_read_JPG, (x,)))
      for x in glob.glob( os.path.join( banner_path, "*.png" )) :
        self._banner_list.append(pool.apply_async(_read_PNG, (x,)))
      pool.close()
      pool.join()
      self._banner_list = [x.get() for x in self._banner_list]
        
      for x in self._banner_list :
        if x[2] is None :
          messagebox.showerror(TITLE, "Banner %s failed to decode correctly." % x[3])
          
      self._banner_list = [(x[0], x[1], x[2]) for x in self._banner_list if x[2] is not None]
    else:
      messagebox.showerror(TITLE, "Missing banner directory %s" % banner_path)
      
    self.display_man = display_man
    img_size = self.display_man.get_ideal_banner_size()
    self.resize_banners( img_size[0], img_size[1] )
    
    self._run = True
    self._banner_cursor = -1
    self._update_time = datetime.datetime.now()  - datetime.timedelta(seconds=999)
    self._hold_time = 0
    
    self._timer = None
    self.update_banner()
    
  def __del__(self):
    if self._timer :
      self._display_man.cancel_timer( self._timer )
      self._timer = None

  def resize_banners(self, width, height):
    ret_list = []
    pool = multiprocessing.Pool()
    ret_list = [pool.apply_async(_img_resize, (x,width,height)) for x in self._banner_list]
    pool.close()
    pool.join()
    ret_list = [x.get() for x in ret_list]
    ret_list = [_convert_to_photoimage(x) for x in ret_list]
      
    self._banner_list = ret_list
    
    
  def update_banner(self):
    if self._banner_list :
      if self._run :
        self._timer = self.display_man.start_timer(self._banner_duration * 1000, self.update_banner)
      self._banner_cursor = ( self._banner_cursor + 1 ) % len( self._banner_list )
      self.display_man.apply_banner( self._banner_list[self._banner_cursor] )
      self._update_time = datetime.datetime.now()
    return
    
  def hold(self):
    if self._timer :
      self.display_man.cancel_timer(self._timer)
      self._timer = None
    if self._run :
      self._run = False
      self._hold_time = (datetime.datetime.now() - self._update_time).total_seconds()
    
  def unhold(self):
    if not self._run :
      self._run = True
      if self._timer :
        self.display_man.cancel_timer(self._timer)
      self._timer = self.display_man.start_timer(max(1, self._banner_duration - self._hold_time) * 1000, self.update_banner )
      
  def shutdown(self):
    if self._timer :
      self.display_man.cancel_timer(self._timer)
    self._timer = None

      
#===============================================================================================
  
class TournamentClockApp( object ) :
  def __init__(self) :
    # -------------------------------------------------------
    # set up GUI first:
    self.display_man = DisplayMan()
    
    # -------------------------------------------------------
    self.tournament = Tournament()
    
    # select tournament structure xml file:
    file = filedialog.askopenfilename()
    print(file)
    
    if not os.path.isfile(file) :
      messagebox.showerror(TITLE, "No Tournament XML file found")
      sys.exit(-1)
      
    # open XML file
    try:
      parser = make_parser()   
      curHandler = XMLEventHandler(self.tournament)
      parser.setContentHandler(curHandler)
      parser.parse(open(file))
    except Exception as e:
      messagebox.showerror(TITLE, "Tournament XML file does not read correctly\n\n%s" % '\n'.join(traceback.format_exception_only(type(e), e)))
      sys.exit(-1)

    # -------------------------------------------------------
    self.time_cursor = TimeCursor( self.tournament )

    # -------------------------------------------------------
    self.banner_controller = BannerController(self.tournament.banners_seconds, self.tournament.banners_path, self.display_man)
    
    # -------------------------------------------------------
    self.sound_man = SoundMan( self.tournament )
    # 
    # optional sound check
    #
    if messagebox.askyesno(TITLE, "Do sound check now?") :
      retry = True
      while retry :
        self.sound_man.sound_check()
        retry = messagebox.askyesno(TITLE, "Do sound check again?")
    
    # -------------------------------------------------------
    self.clock_controller = ClockController( self.display_man, self.sound_man, self.time_cursor )
    
    # -------------------------------------------------------
    # a hold is different from a pause.  A hold is forced, not user-requested, to avoid threading errors while the user manipulates a widget
    self._hold = False
    
    
  def press_play(self):
    self.clock_controller.press_play()
    self.time_cursor.press_play()
    
  def press_pause(self):
    self.clock_controller.press_pause()
    self.time_cursor.press_pause()
    
  def hold(self):
    if self.time_cursor.is_playing() :
      self._hold = True
      self.clock_controller.press_pause()
      self.time_cursor.press_pause()
      self.banner_controller.hold()
      
  def unhold(self):
    if self._hold :
      self._hold = False
      self.clock_controller.press_play()
      self.time_cursor.press_play()
      self.banner_controller.unhold()

  def run(self):
    self.display_man.init_app(self)
    self.clock_controller.update_time_info(do_force=True)
    return self.display_man.run()
    
  def shutdown(self):
    self.press_pause() # kills threads
    self.banner_controller.shutdown()
    
#===============================================================================================
  
if __name__ == '__main__' :

  app = TournamentClockApp()
  app.run()

  
        


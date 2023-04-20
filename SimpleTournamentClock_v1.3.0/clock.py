import datetime
import os
import traceback
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
import sys
import clockUI
from playsound import playsound

from xml.sax import make_parser
from xml.sax.handler import ContentHandler


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

def messageBox(title,msg,error=False, yesno=False ):
   msgBox = QMessageBox()
   msgBox.setIcon(QMessageBox.Information)
   msgBox.setText(msg)
   msgBox.setWindowTitle(title)
   if yesno:
    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
   else:
     msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
   msgBox.buttonClicked.connect(msgButtonClick)

   returnValue = msgBox.exec()
   return returnValue
#   if returnValue == QMessageBox.Ok:
#      print('OK clicked')

def msgButtonClick():
  pass


TITLE = "Tournament Clock"

SOUND_LEVELWARNING = "warning.wav"
SOUND_LEVELCHANGE = "newlevel.wav"
SOUND_TIMEBARRIER = 10


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
    
#===============================================================================================


class SoundMan( object ):
  def __init__(self, path) :
    self._last_time = datetime.datetime.now()
    self._path = path      # tournament.sounds_path
    self.sound_checked = False
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
    self.sound_checked = True

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
    if self.sound_checked:
      return ret
    else:
      return False
    
  def _play(self, filename):
    if (not self._play_block()) and os.path.isfile(filename):
        playsound(filename)
          

  def _sound_check_file(self, filename):
    if os.path.isfile(filename):
      try:
        playsound(filename)

      except:
        messageBox(TITLE, "Sound %s failed" % filename)
    else:
      messageBox(TITLE, "No file called %s" % filename)


#===============================================================================================
  
class ClockController( object ):
  def __init__(self, display_man, sound_man, time_cursor):
    #self._display_man = display_man
    #self._sound_man = sound_man    
    #self._time_cursor = time_cursor
    self._run = False
    self._timer = None
    
    self._lasttime = 999999999
    self._lastlevel = -999999

  def __del__(self):
    if self._timer :
      #self._display_man.cancel_timer( self._timer )
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
      #self._timer = self._display_man.start_timer( 99, self.update_time_info)
      self._timer = self.QTimer()
      self._timer.timeout.connect(self.update_time_info)
      self._timer.start(100)

      #self._time_cursor.tick()
      
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

        #self._display_man.display_time_info(level_title, level_time, next_title, next_time, break_title, break_time)
        
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
#        if now >= warning_threshold :
#          self._display_man.use_warning_colors()
#        else:
#          self._display_man.unuse_warning_colors()
          
        self._lasttime = now

    return

class player:
    def __init__(self,name) -> None:
        self.name = name
        self.rebuys = 0

class ExampleApp(QtWidgets.QMainWindow, clockUI.Ui_MainWindow):
    def __init__(self, parent=None):
        super(ExampleApp, self).__init__(parent)
        self.setupUi(self)

        self.players = 0
        self.prizePool = 0
        self.buyin = 20
        #size = self.size()


        self.tournament = Tournament()


        #(fname,ftype) = QFileDialog.getOpenFileName(self, 'Open file', '.',"XML files (*.xml)")
        fname = '/home/chall/dev/poker/SimpleTournamentClock_v1.3.0/examples/structures/QuickTest.xml'
        # open XML file
        try:
          parser = make_parser()   
          curHandler = XMLEventHandler(self.tournament)
          parser.setContentHandler(curHandler)
          fin = open(fname)

          parser.parse(fin)
          fin.close()
        except Exception as e:
          messageBox(TITLE, "Tournament XML file does not read correctly\n\n%s" % '\n'.join(traceback.format_exception_only(type(e), e)))
          sys.exit(-1)

        self.sound_man = SoundMan("./SimpleTournamentClock_v1.3.0/examples/sounds")
        #ret = int(messageBox(TITLE, "Do sound check now?",yesno=True))
        ret = -1    # TODO fix the sounds!!!!
        if ret == QMessageBox.Yes:
          retry = True
          while retry :
            self.sound_man.sound_check()
            retry = messageBox(TITLE, "Do sound check again?",yesno=True)
        

        self.pb_playerAdd.clicked.connect(self.player_add)
        self.pb_rebuy.clicked.connect(self.rebuy)
        self.refresh_screen()

    def refresh_screen(self):
      # refresh # of players, # of rebuys, prizes, 

      pass


    def player_add(self,player):
        pass

    def rebuy(self,player):
        pass
    
    def pause_pressed(self):
      pass

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
      k = super().keyPressEvent(a0)
      print('{0} ==> {1}',(str(a0.key()),a0.text()))
      return k


def main():
    app = QApplication(sys.argv)
    form = ExampleApp()
    form.show()
    app.exec_()

if __name__ == '__main__':
    main()
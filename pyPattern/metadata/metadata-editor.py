#!/usr/bin/env python3

from PyQt5 import QtCore, QtWidgets, QtGui, uic
import sys
import os
import json

import traceback

import common

# ListView data model
class EventModel(QtCore.QAbstractListModel):
  def __init__(self, *args, events=None, **kwargs):
    super(EventModel, self).__init__(*args, **kwargs)
    self._events = events or []

  def data(self, index, role):
    if role == QtCore.Qt.DisplayRole:
      # See below for the data structure.
      frame, text = self._events[index.row()]
      # Return the frame and text
      return f'#{frame} -> {text}'
    elif role == QtCore.Qt.EditRole:
      return self._events[index.row()]

  def add(self, ev):
    self._events.append(ev)

  def change(self, index, ev):
    self._events[index.row()] = ev

  def remove(self, index):
    self._events.pop(index.row())

  def rowCount(self, index):
    return len(self._events)

# Metadata Event Editor
class MetadataEventEditor(QtWidgets.QDialog):
  def __init__(self, parent):
    super(MetadataEventEditor, self).__init__(parent) # Call the inherited classes __init__ method
    uic.loadUi('event-editor.ui', self) # Load the .ui file

    # introduce validators
    dv = QtGui.QIntValidator(bottom=0)
    self.edFrame.setValidator(dv)

# Metadata Editor
class MetadataEditor(QtWidgets.QMainWindow):
  def __init__(self):
    super(MetadataEditor, self).__init__() # Call the inherited classes __init__ method
    uic.loadUi('main.ui', self) # Load the .ui file

    # initialize class members
    self._cur_idx = None
    self._filepath = None
    self._safe_filepath = None
    self._metadata = None

    # event editor
    self.eventEditor = MetadataEventEditor(self)

    # introduce validators
    dv = QtGui.QDoubleValidator(bottom=0.0)
    dv.setNotation(QtGui.QDoubleValidator.StandardNotation)
    self.edUmPerPixel.setValidator(dv)
    self.edTimeStep.setValidator(dv)

    # add button events
    #self.actSave = QtWidgets.QAction(QtGui.QIcon.fromTheme("file-save"), "Save...", self)
    #self.actSave.setStatusTip("This is your button")
    #self.actSave.triggered.connect(self.onSave)

    self.btnSave.setIcon(QtGui.QIcon.fromTheme("file-save"))
    self.btnSave.clicked.connect(self.onSave)

    self.btnAdd.clicked.connect(self.onAdd)
    self.btnEdit.clicked.connect(self.onEdit)
    self.btnRemove.clicked.connect(self.onRemove)

    # files list
    self.filesModel = QtWidgets.QFileSystemModel()
    self.filesModel.setRootPath( config['datapath'] )
    self.filesModel.setNameFilters(["*.tif", "*.tiff"])
    self.filesModel.setNameFilterDisables(True)

    self.filesView.setModel(self.filesModel)
    self.filesView.setRootIndex(self.filesModel.index( config['datapath'] ))
    self.filesView.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
    self.filesView.doubleClicked.connect(self.openMetadata)

    # events list
    self.eventsModel = EventModel()

    self.lstEvents.setModel(self.eventsModel)

    # widget view
    self.widgetPanel.setEnabled(False)

    # show the GUI
    self.show()

  # signals
  @QtCore.pyqtSlot(QtCore.QModelIndex)
  def openMetadata(self, index):
    if(self._cur_idx is not None):
      if(QtWidgets.QMessageBox.No == QtWidgets.QMessageBox.question(self, 'Abandon Changes?', "If you switch to editing another file, all your current changes will be lost. Would you like to continue?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)):
        return
    else:
      self.widgetPanel.setEnabled(True)

    self._cur_idx = index
    self._filepath=self.filesModel.filePath(index)
    self._safe_filepath = common.get_safe_filepath(self._filepath[len(config['datapath']):])

    self.lblFileName.setText(self._filepath[len(config['datapath']):])

    try:
      self._metadata = MetadataEditor.importJSON(common.get_json_path(self._safe_filepath))
    except Exception as err:
      traceback.print_exception(None,err,err.__traceback__)
      QtWidgets.QMessageBox.warning(self, 'Loading Metadata Failed', "Importing JSON failed.", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
      self._metadata = None
    if(self._metadata is not None):
      self.edUmPerPixel.setText(self._metadata.get('um-per-pixel',None))
      self.edTimeStep.setText(self._metadata.get('time-step',None))

      events = self._metadata.get('events',None)
      if(events is None):
        self._metadata['events'] = []

      for ev in events:
        if(isinstance(ev, tuple)):
          print(f'{ev} is a tuple')
    else:
      self._metadata = {'um-per-pixel' : None, 'time-step' : None, 'events' : []}

    self.eventsModel = EventModel(events=self._metadata['events'])
    self.lstEvents.setModel(self.eventsModel)

  @QtCore.pyqtSlot(bool)
  def onSave(self):
    if(self._cur_idx is not None):
      self._metadata = dict()
      try:
        self._metadata['um-per-pixel'] = self.edUmPerPixel.text()
        self._metadata['time-step'] = self.edTimeStep.text()
      except Exception as err:
        traceback.print_exception(None,err,err.__traceback__)
        QtWidgets.QMessageBox.warning(self, 'Saving Metadata Failed', "Floating-point conversion failed.\nYour changes could not be saved.", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        return

      self._metadata['events'] = self.eventsModel._events

      try:
        MetadataEditor.exportJSON(self._metadata, common.get_json_path(self._safe_filepath))
      except Exception as err:
        traceback.print_exception(None,err,err.__traceback__)
        QtWidgets.QMessageBox.warning(self, 'Saving Metadata Failed', "Exporting to JSON failed.\nYour changes could not be saved.", QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        return

  @QtCore.pyqtSlot()
  def onAdd(self):
    """
    Add an event to the events list by showing an empty New Event dialog.
    """
    ret = self.eventEditor.exec()
    if(ret == QtWidgets.QDialog.Accepted):
      self.eventsModel.add((self.eventEditor.edFrame.text(), self.eventEditor.edText.text()))
      self.eventsModel.layoutChanged.emit()

  @QtCore.pyqtSlot()
  def onEdit(self):
    """
    Edit an event in the events list using the Edit Event dialog.
    """
    idx = self.lstEvents.selectedIndexes()
    if(len(idx)):
      ev = self.eventsModel.data(idx[0], QtCore.Qt.EditRole)
      self.eventEditor.edFrame.setText(ev[0])
      self.eventEditor.edText.setText(ev[1])

      ret = self.eventEditor.exec()

      if(ret == QtWidgets.QDialog.Accepted):
        ev = (self.eventEditor.edFrame.text(), self.eventEditor.edText.text())
        self.eventsModel.change(idx[0], ev)
        self.eventsModel.layoutChanged.emit()


  @QtCore.pyqtSlot()
  def onRemove(self):
    """
    Edit an event in the events list using the Edit Event dialog.
    """
    idx = self.lstEvents.selectedIndexes()
    if(len(idx)):
      ev = self.eventsModel.remove(idx[0])
      self.eventsModel.layoutChanged.emit()

  # JSON handling
  @staticmethod
  def importJSON(filepath):
    if(os.path.isfile(filepath)):
      print(f'{filepath} file exists')
      with open(filepath, 'r') as handle:
        print(f'opened metadata file "{filepath}"')
        #for count, line in enumerate(handle.readlines()):
          #print("Line{}: {}".format(count, line.strip()))
        return json.load(handle)

  @staticmethod
  def exportJSON(obj, filepath):
    with open(filepath, 'w') as handle:
      json.dump(obj, handle)
      print(f'saved metadata file "{filepath}"')

# load config
try:
  with open('metadata-config.json', 'r') as handle:
    config = json.load(handle)
except:
  print('warning: could not load configuration, using default')
  config['datapath'] = './json/'
  pass

# main
app = QtWidgets.QApplication(sys.argv)
window = MetadataEditor()
app.exec_()

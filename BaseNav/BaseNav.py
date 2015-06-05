import os
import unittest
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import time

class BaseNavSliceletWidget:
  def __init__(self, parent=None):
    try:
      parent
      self.parent = parent
    except Exception, e:
      import traceback
      traceback.print_exc()
      logging.error("There is no parent to BaseNavSliceletWidget!")


class BaseNavSlicelet(object):

  def __init__(self, parent, parameterList=None, widgetClass=None):    
    logging.debug('BaseNavSlicelet.__init__')

    self.moduleDirectoryPath = slicer.modules.basenav.path.replace('BaseNav.py', '')

    # Used Icons
    self.recordIcon = qt.QIcon(self.moduleDirectoryPath+'/Resources/Icons/icon_Record.png')
    self.stopIcon = qt.QIcon(self.moduleDirectoryPath+'/Resources/Icons/icon_Stop.png')
    
    self.logic = BaseNavLogic()

    self.parameterNode = None
    self.parameterNodeObserver = None

    parameterNode = self.logic.getParameterNode()

    if(parameterList!=None):
        for parameter in parameterList:
            parameterNode.SetParameter(parameter, str(parameterList[parameter]))
            logging.info(parameter +' '+ parameterNode.GetParameter(parameter))

    self.setAndObserveParameterNode(parameterNode)

    self.usFrozen=False
    
    defaultCommandTimeoutSec = 15

    self.cmdStartRecording = slicer.modulelogic.vtkSlicerOpenIGTLinkCommand()
    self.cmdStartRecording.SetCommandTimeoutSec(defaultCommandTimeoutSec);
    self.cmdStartRecording.SetCommandName('StartRecording')    
    self.cmdStopRecording = slicer.modulelogic.vtkSlicerOpenIGTLinkCommand()
    self.cmdStopRecording.SetCommandTimeoutSec(defaultCommandTimeoutSec);
    self.cmdStopRecording.SetCommandName('StopRecording')
    
    self.captureDeviceName='CaptureDevice'
    
    self.connectorNode = None
    self.connectorNodeObserverTagList = []
    self.connectorNodeConnected = False
    self.setupConnectorNode()

    # Set up main frame.

    self.parent = parent

    self.sliceletDockWidget = qt.QDockWidget(self.parent)
    self.sliceletDockWidget.setObjectName('BaseNavPanel')
    self.sliceletDockWidget.setWindowTitle('BaseNav')
    
    style = "QDockWidget:title {background-color: #9ACEFF;}"    
    self.sliceletDockWidget.setStyleSheet(style)
    
    mainWindow=slicer.util.mainWindow()
    self.sliceletDockWidget.setParent(mainWindow)
    
    self.showFullScreen()
        
    self.sliceletPanel = qt.QFrame(self.sliceletDockWidget)
    self.sliceletPanelLayout = qt.QVBoxLayout(self.sliceletPanel)    
    self.sliceletDockWidget.setWidget(self.sliceletPanel)
    
    # Color scheme: #C7DDF5, #9ACEFF, #669ACC, #336799
    style = "QFrame {background-color: #336799; border-color: #9ACEFF;}"
    self.sliceletPanel.setStyleSheet(style)
       
    # Create GUI panels.

    self.calibrationCollapsibleButton = ctk.ctkCollapsibleButton()
    self.ultrasoundCollapsibleButton = ctk.ctkCollapsibleButton()
    self.navigationCollapsibleButton = ctk.ctkCollapsibleButton()
    self.advancedCollapsibleButton = ctk.ctkCollapsibleButton()

    self.setupCalibrationPanel()
    self.setupUltrasoundPanel()
    self.setupNavigationPanel()
    self.setupAdvancedPanel()

    # Adding collapsible buttons to a group, so only one is open at a time.

    self.collapsibleButtonGroup = qt.QButtonGroup()
    self.collapsibleButtonGroup.addButton(self.calibrationCollapsibleButton)
    self.collapsibleButtonGroup.addButton(self.ultrasoundCollapsibleButton)
    self.collapsibleButtonGroup.addButton(self.navigationCollapsibleButton)
    self.collapsibleButtonGroup.addButton(self.advancedCollapsibleButton)

    # Setting button open on startup.
    self.calibrationCollapsibleButton.setProperty('collapsed', False)

    self.addConnectorObservers()
    
    # Setting up callback functions for widgets.
    self.setupConnections()
    
    # Set needle and cautery transforms and models
    self.setupScene()

  def __del__(self):
    # Clean up commands
    self.cmdStartRecording.RemoveObservers(slicer.modulelogic.vtkSlicerOpenIGTLinkCommand.CommandCompletedEvent)
    self.cmdStopRecording.RemoveObservers(slicer.modulelogic.vtkSlicerOpenIGTLinkCommand.CommandCompletedEvent)
    
  def setButtonStyle(self, button, textScale = 1.0):
    style = """
    {0}         {{border-style: outset; border-width: 2px; border-radius: 10px; background-color: #C7DDF5; border-color: #9ACEFF; font-size: {1}pt; height: {2}px}}
    {0}:pressed  {{border-style: outset; border-width: 2px; border-radius: 10px; background-color: #9ACEFF; border-color: #9ACEFF; font-size: {1}pt; height: {2}px}}
    {0}:checked {{border-style: outset; border-width: 2px; border-radius: 10px; background-color: #669ACC; border-color: #9ACEFF; font-size: {1}pt; height: {2}px}}
    """.format(button.className(), 12*textScale, qt.QDesktopWidget().screenGeometry().height()*0.05)
    
    button.setStyleSheet(style)
    
  def showFullScreen(self):
  
    # We hide all toolbars, etc. which is inconvenient as a default startup setting,
    # therefore disable saving of window setup.
    settings = qt.QSettings()
    settings.setValue('MainWindow/RestoreGeometry', 'false')
    
    self.showToolbars(False)
    self.showModulePanel(False)
    self.showMenuBar(False)
    
    mainWindow=slicer.util.mainWindow()
    mainWindow.addDockWidget(qt.Qt.LeftDockWidgetArea, self.sliceletDockWidget)
    self.sliceletDockWidget.show()

    mainWindow.setWindowTitle('Navigation')
    mainWindow.windowIcon = qt.QIcon(self.moduleDirectoryPath + '/Resources/Icons/BaseNav.png')
    mainWindow.showFullScreen()
    
  def showToolbars(self, show):
    for toolbar in slicer.util.mainWindow().findChildren('QToolBar'):
      toolbar.setVisible(show)

  def showModulePanel(self, show):
    slicer.util.mainWindow().findChildren('QDockWidget','PanelDockWidget')[0].setVisible(show)
  
  def showMenuBar(self, show):
    for menubar in slicer.util.mainWindow().findChildren('QMenuBar'):
      menubar.setVisible(show)
    
  def setupConnections(self):
    logging.debug('setupConnections')

    self.calibrationCollapsibleButton.connect('toggled(bool)', self.onCalibrationPanelToggled)
    self.ultrasoundCollapsibleButton.connect('toggled(bool)', self.onUltrasoundPanelToggled)
    self.navigationCollapsibleButton.connect('toggled(bool)', self.onNavigationPanelToggled)

    self.startStopRecordingButton.connect('clicked(bool)', self.onStartStopRecordingClicked)
    self.freezeUltrasoundButton.connect('clicked()', self.onFreezeUltrasoundClicked)
    self.brigthnessContrastButtonNormal.connect('clicked()', self.onBrightnessContrastNormalClicked)
    self.brigthnessContrastButtonBright.connect('clicked()', self.onBrightnessContrastBrightClicked)
    self.brigthnessContrastButtonBrighter.connect('clicked()', self.onBrightnessContrastBrighterClicked)
    
    self.showFullSlicerInterfaceButton.connect('clicked()', self.onShowFullSlicerInterfaceClicked)
    self.saveSceneButton.connect('clicked()', self.onSaveSceneClicked)
    
    self.linkInputSelector.connect("nodeActivated(vtkMRMLNode*)", self.onConnectorNodeActivated)
    self.viewSelectorComboBox.connect('activated(int)', self.onViewSelect)

  def setupScene(self):
    logging.debug('setupScene')

    logging.debug('Create transforms')
      
    self.ReferenceToRas = slicer.util.getNode('ReferenceToRas')
    if not self.ReferenceToRas:
      self.ReferenceToRas=slicer.vtkMRMLLinearTransformNode()
      self.ReferenceToRas.SetName("ReferenceToRas")
      m = vtk.vtkMatrix4x4()
      m.SetElement( 0, 0, 0 )
      m.SetElement( 0, 2, -1 )
      m.SetElement( 1, 1, 0 )
      m.SetElement( 1, 1, -1 )
      m.SetElement( 2, 2, 0 )
      m.SetElement( 2, 0, -1 )
      self.ReferenceToRas.SetMatrixTransformToParent(m)
      slicer.mrmlScene.AddNode(self.ReferenceToRas)
      
    self.needleTipToNeedle = slicer.util.getNode('NeedleTipToNeedle')
    if not self.needleTipToNeedle:
      self.needleTipToNeedle=slicer.vtkMRMLLinearTransformNode()
      self.needleTipToNeedle.SetName("NeedleTipToNeedle")
      m = self.readTransformFromSettings('NeedleTipToNeedle')
      if m:
        self.needleTipToNeedle.SetMatrixTransformToParent(m)
      slicer.mrmlScene.AddNode(self.needleTipToNeedle)           

    self.needleModelToNeedleTip = slicer.util.getNode('NeedleModelToNeedleTip')
    if not self.needleModelToNeedleTip:
      self.needleModelToNeedleTip=slicer.vtkMRMLLinearTransformNode()
      self.needleModelToNeedleTip.SetName("NeedleModelToNeedleTip")
      m = vtk.vtkMatrix4x4()
      m.SetElement( 0, 0, 0 )
      m.SetElement( 1, 1, 0 )
      m.SetElement( 2, 2, 0 )
      m.SetElement( 0, 1, 1 )
      m.SetElement( 1, 2, 1 )
      m.SetElement( 2, 0, 1 )
      self.needleModelToNeedleTip.SetMatrixTransformToParent(m)
      slicer.mrmlScene.AddNode(self.needleModelToNeedleTip)      
      
    # Create transforms that will be updated through OpenIGTLink
      
    self.needleToReference = slicer.util.getNode('NeedleToReference')
    if not self.needleToReference:
      self.needleToReference=slicer.vtkMRMLLinearTransformNode()
      self.needleToReference.SetName("NeedleToReference")
      slicer.mrmlScene.AddNode(self.needleToReference)
  
    # Models
    logging.debug('Create models')

    self.needleModel_NeedleTip = slicer.util.getNode('NeedleModel')
    if not self.needleModel_NeedleTip:
      slicer.modules.createmodels.logic().CreateNeedle(80,1.0,2.5,0)
      self.needleModel_NeedleTip=slicer.util.getNode(pattern="NeedleModel")
      self.needleModel_NeedleTip.GetDisplayNode().SetColor(0.333333, 1.0, 1.0)
      self.needleModel_NeedleTip.SetName("NeedleModel")
      self.needleModel_NeedleTip.GetDisplayNode().SliceIntersectionVisibilityOn()

    liveUltrasoundNodeName = self.parameterNode.GetParameter('LiveUltrasoundNodeName')
    self.liveUltrasoundNode_Reference = slicer.util.getNode(liveUltrasoundNodeName)
    if not self.liveUltrasoundNode_Reference:
      imageSize=[800, 600, 1]
      imageSpacing=[0.2, 0.2, 0.2]
      # Create an empty image volume
      imageData=vtk.vtkImageData()
      imageData.SetDimensions(imageSize)
      imageData.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
      thresholder=vtk.vtkImageThreshold()
      thresholder.SetInputData(imageData)
      thresholder.SetInValue(0)
      thresholder.SetOutValue(0)
      # Create volume node
      self.liveUltrasoundNode_Reference=slicer.vtkMRMLScalarVolumeNode()
      self.liveUltrasoundNode_Reference.SetName(liveUltrasoundNodeName)
      self.liveUltrasoundNode_Reference.SetSpacing(imageSpacing)
      self.liveUltrasoundNode_Reference.SetImageDataConnection(thresholder.GetOutputPort())
      # Add volume to scene
      slicer.mrmlScene.AddNode(self.liveUltrasoundNode_Reference)
      displayNode=slicer.vtkMRMLScalarVolumeDisplayNode()
      slicer.mrmlScene.AddNode(displayNode)
      colorNode = slicer.util.getNode('Grey')
      displayNode.SetAndObserveColorNodeID(colorNode.GetID())
      self.liveUltrasoundNode_Reference.SetAndObserveDisplayNodeID(displayNode.GetID())
      #self.liveUltrasoundNode_Reference.CreateDefaultStorageNode()

    # Show ultrasound in red view.
    layoutManager = self.layoutManager
    redSlice = layoutManager.sliceWidget('Red')
    redSliceLogic = redSlice.sliceLogic()
    redSliceLogic.GetSliceCompositeNode().SetBackgroundVolumeID(self.liveUltrasoundNode_Reference.GetID())

    # Set up volume reslice driver.
    resliceLogic = slicer.modules.volumereslicedriver.logic()
    if resliceLogic:
      redNode = slicer.util.getNode('vtkMRMLSliceNodeRed')
      # Typically the image is zoomed in, therefore it is faster if the original resolution is used
      # on the 3D slice (and also we can show the full image and not the shape and size of the 2D view)
      redNode.SetSliceResolutionMode(slicer.vtkMRMLSliceNode.SliceResolutionMatchVolumes)
      resliceLogic.SetDriverForSlice(self.liveUltrasoundNode_Reference.GetID(), redNode)
      resliceLogic.SetModeForSlice(6, redNode) # Transverse mode, default for PLUS ultrasound.
      resliceLogic.SetFlipForSlice(False, redNode)
      resliceLogic.SetRotationForSlice(180, redNode)
      redSliceLogic.FitSliceToAll()
    else:
      logging.warning('Logic not found for Volume Reslice Driver') 
    
    # Build transform tree
    logging.debug('Set up transform tree')
    self.needleModel_NeedleTip.SetAndObserveTransformNodeID(self.needleModelToNeedleTip.GetID())    
    self.needleModelToNeedleTip.SetAndObserveTransformNodeID(self.needleTipToNeedle.GetID())
    self.needleTipToNeedle.SetAndObserveTransformNodeID(self.needleToReference.GetID())
    self.liveUltrasoundNode_Reference.SetAndObserveTransformNodeID(self.ReferenceToRas.GetID())
    
    # Hide slice view annotations (patient name, scale, color bar, etc.) as they
    # decrease reslicing performance by 20%-100%
    logging.debug('Hide slice view annotations')
    import DataProbe
    dataProbeUtil=DataProbe.DataProbeLib.DataProbeUtil()
    dataProbeParameterNode=dataProbeUtil.getParameterNode()
    dataProbeParameterNode.SetParameter('showSliceViewAnnotations', '0')

  def disconnect(self):
    logging.debug('disconnect')

    # Clean up observers to old connector.
    if self.connectorNode and self.connectorNodeObserverTagList:
      for tag in self.connectorNodeObserverTagList:
        self.connectorNode.RemoveObserver(tag)
      self.connectorNodeObserverTagList = []

    # Remove observer to old parameter node
    if self.parameterNode and self.parameterNodeObserver:
      self.parameterNode.RemoveObserver(self.parameterNodeObserver)
      self.parameterNodeObserver = None

    self.calibrationCollapsibleButton.disconnect('toggled(bool)', self.onCalibrationPanelToggled)
    self.ultrasoundCollapsibleButton.disconnect('toggled(bool)', self.onUltrasoundPanelToggled)
    self.navigationCollapsibleButton.disconnect('toggled(bool)', self.onNavigationPanelToggled)

    self.freezeUltrasoundButton.disconnect('clicked()', self.onFreezeUltrasoundClicked)
    self.brigthnessContrastButtonNormal.disconnect('clicked()', self.onBrightnessContrastNormalClicked)
    self.brigthnessContrastButtonBright.disconnect('clicked()', self.onBrightnessContrastBrightClicked)
    self.brigthnessContrastButtonBrighter.disconnect('clicked()', self.onBrightnessContrastBrighterClicked)
    self.showFullSlicerInterfaceButton.disconnect('clicked()', self.onShowFullSlicerInterfaceClicked)
    self.saveSceneButton.disconnect('clicked()', self.onSaveSceneClicked)
    self.linkInputSelector.disconnect("nodeActivated(vtkMRMLNode*)", self.onConnectorNodeActivated)
    self.viewSelectorComboBox.disconnect('activated(int)', self.onViewSelect)

    # logging.debug('BaseNavMainFrame.closeEvent')
    # self.slicelet.disconnect()
    # self.slicelet.setAndObserveParameterNode(None)
    # #self.disconnect('destroyed()', self.onSliceletClosed)
    # import gc
    # refs = gc.get_referrers(self.slicelet)
    # if len(refs) > 1:
      # logging.warning('Stuck slicelet references (' + repr(len(refs)) + '):\n' + repr(refs))

    # #slicer.baseNavSliceletInstance = None
    # self.slicelet.parent = None
    # self.slicelet = None
    # self.deleteLater()

  def onStartStopRecordingClicked(self):

    if self.startStopRecordingButton.isChecked():      
      self.startStopRecordingButton.setText("  Stop Recording")
      self.startStopRecordingButton.setIcon(self.stopIcon)
      self.startStopRecordingButton.setToolTip("Recording is being started...")
      
      # Important to save as .mhd because that does not require lengthy finalization (merging into a single file)
      recordingFileName = "BaseNavRecording-" + time.strftime("%Y%m%d-%H%M%S") +".mhd"

      logging.info("Starting recording to: {0}".format(recordingFileName))

      self.cmdStartRecording.SetCommandAttribute('CaptureDeviceId', self.captureDeviceName)
      self.cmdStartRecording.SetCommandAttribute('OutputFilename', recordingFileName)
      self.executeCommand(self.cmdStartRecording, self.recordingCommandCompleted)

    else:
      logging.info("Stopping recording")
      self.startStopRecordingButton.setText("  Start Recording")
      self.startStopRecordingButton.setIcon(self.recordIcon)
      self.startStopRecordingButton.setToolTip( "Recording is being stopped..." )
      self.cmdStopRecording.SetCommandAttribute('CaptureDeviceId', self.captureDeviceName)
      self.executeCommand(self.cmdStopRecording, self.recordingCommandCompleted)
    
  def onFreezeUltrasoundClicked(self):
    logging.debug('onFreezeUltrasoundClicked')
    self.usFrozen = not self.usFrozen
    if(self.usFrozen):
      self.connectorNode.Stop()
    else:
      self.connectorNode.Start()

  def setImageMinMaxLevel(self, minLevel, maxLevel):
    self.liveUltrasoundNode_Reference.GetDisplayNode().SetAutoWindowLevel(0)
    self.liveUltrasoundNode_Reference.GetDisplayNode().SetWindowLevelMinMax(minLevel,maxLevel)
    
  def onBrightnessContrastNormalClicked(self):
    logging.debug('onBrightnessContrastNormalClicked')
    self.setImageMinMaxLevel(0,200)

  def onBrightnessContrastBrightClicked(self):
    logging.debug('onBrightnessContrastBrightClicked')
    self.setImageMinMaxLevel(0,120)
    
  def onBrightnessContrastBrighterClicked(self):
    logging.debug('onBrightnessContrastBrighterClicked')
    self.setImageMinMaxLevel(0,60)
    
  def onShowFullSlicerInterfaceClicked(self):
    self.showToolbars(True)
    self.showModulePanel(True)
    self.showMenuBar(True)
    slicer.util.mainWindow().showMaximized()
    
    # Save current state
    settings = qt.QSettings()
    settings.setValue('MainWindow/RestoreGeometry', 'true')

  def onSaveSceneClicked(self):
    #
    # save the mrml scene to a temp directory, then zip it
    #
    applicationLogic = slicer.app.applicationLogic()
    sceneSaveDirectory = self.saveDirectoryLineEdit.text

    # Save the last used directory
    self.setSavedScenesDirectory(sceneSaveDirectory)
    
    sceneSaveDirectory = sceneSaveDirectory + "/BaseNav-" + time.strftime("%Y%m%d-%H%M%S")
    logging.info("Saving scene to: {0}".format(sceneSaveDirectory))
    if not os.access(sceneSaveDirectory, os.F_OK):
      os.makedirs(sceneSaveDirectory)
    if(applicationLogic.SaveSceneToSlicerDataBundleDirectory(sceneSaveDirectory, None)):
      logging.info("Scene saved to: {0}".format(sceneSaveDirectory)) 
    else:
      logging.error("Scene saving failed")

  def __del__(self):
    self.cleanUp()

  # Clean up when slicelet is closed
  def cleanUp(self):
    logging.debug('cleanUp')
    self.breachWarningNode.UnRegister(slicer.mrmlScene)
    self.setAndObserveTumorMarkupsNode(None)
    self.breachWarningLightLogic.stopLightFeedback()

  def setupCalibrationPanel(self):
    logging.debug('setupCalibrationPanel')

    self.calibrationCollapsibleButton.setProperty('collapsedHeight', 20)
    self.setButtonStyle(self.calibrationCollapsibleButton, 2.0)
    self.calibrationCollapsibleButton.text = 'Tool calibration'
    self.sliceletPanelLayout.addWidget(self.calibrationCollapsibleButton)

    self.calibrationLayout = qt.QFormLayout(self.calibrationCollapsibleButton)
    self.calibrationLayout.setContentsMargins(12, 4, 4, 4)
    self.calibrationLayout.setSpacing(4)

  def setupUltrasoundPanel(self):
    logging.debug('setupUltrasoundPanel')

    self.ultrasoundCollapsibleButton.setProperty('collapsedHeight', 20)
    self.setButtonStyle(self.ultrasoundCollapsibleButton, 2.0)
    self.ultrasoundCollapsibleButton.text = "Ultrasound imaging"
    self.sliceletPanelLayout.addWidget(self.ultrasoundCollapsibleButton)

    self.ultrasoundLayout = qt.QFormLayout(self.ultrasoundCollapsibleButton)
    self.ultrasoundLayout.setContentsMargins(12,4,4,4)
    self.ultrasoundLayout.setSpacing(4)

    self.startStopRecordingButton = qt.QPushButton("  Start Recording")
    self.startStopRecordingButton.setCheckable(True)
    self.startStopRecordingButton.setIcon(self.recordIcon)
    self.setButtonStyle(self.startStopRecordingButton)
    self.startStopRecordingButton.setToolTip("If clicked, start recording")
    
    self.freezeUltrasoundButton = qt.QPushButton('Freeze')
    self.setButtonStyle(self.freezeUltrasoundButton)

    hbox = qt.QHBoxLayout()
    hbox.addWidget(self.startStopRecordingButton)
    hbox.addWidget(self.freezeUltrasoundButton)
    self.ultrasoundLayout.addRow(hbox)
    
    self.brigthnessContrastButtonNormal = qt.QPushButton()
    self.brigthnessContrastButtonNormal.text = "Normal"
    self.setButtonStyle(self.brigthnessContrastButtonNormal)
    self.brigthnessContrastButtonNormal.setEnabled(True)

    self.brigthnessContrastButtonBright = qt.QPushButton()
    self.brigthnessContrastButtonBright.text = "Bright"
    self.setButtonStyle(self.brigthnessContrastButtonBright)
    self.brigthnessContrastButtonBright.setEnabled(True)

    self.brigthnessContrastButtonBrighter = qt.QPushButton()
    self.brigthnessContrastButtonBrighter.text = "Brighter"
    self.setButtonStyle(self.brigthnessContrastButtonBrighter)
    self.brigthnessContrastButtonBrighter.setEnabled(True)

    brightnessContrastBox = qt.QHBoxLayout()
    brightnessContrastBox.addWidget(self.brigthnessContrastButtonNormal)
    brightnessContrastBox.addWidget(self.brigthnessContrastButtonBright)
    brightnessContrastBox.addWidget(self.brigthnessContrastButtonBrighter)
    self.ultrasoundLayout.addRow(brightnessContrastBox)
    
  def setupNavigationPanel(self):
    logging.debug('setupNavigationPanel')

    self.navigationCollapsibleButton.setProperty('collapsedHeight', 20)
    self.setButtonStyle(self.navigationCollapsibleButton, 2.0)
    self.navigationCollapsibleButton.text = "Navigation"
    #self.navigationCollapsibleButton.setProperty('buttonTextAlignment', 0x0080)#0x0001
    self.sliceletPanelLayout.addWidget(self.navigationCollapsibleButton)

    self.navigationCollapsibleLayout = qt.QFormLayout(self.navigationCollapsibleButton)
    self.navigationCollapsibleLayout.setContentsMargins(12, 4, 4, 4)
    self.navigationCollapsibleLayout.setSpacing(4)

  def registerCustomLayouts(self, layoutManager):
    
    customLayout = ("<layout type=\"horizontal\" split=\"false\" >"
      " <item>"
      "  <view class=\"vtkMRMLViewNode\" singletontag=\"1\">"
      "    <property name=\"viewlabel\" action=\"default\">1</property>"
      "  </view>"
      " </item>"
      " <item>"
      "  <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">"
      "   <property name=\"viewlabel\" action=\"default\">2</property>"
      "  </view>"
      " </item>"
      "</layout>")
    self.dual3dCustomLayoutId=503
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(self.dual3dCustomLayoutId, customLayout)

    customLayout = ("<layout type=\"horizontal\" split=\"false\" >"
      " <item>"
      "  <view class=\"vtkMRMLViewNode\" singletontag=\"1\">"
      "    <property name=\"viewlabel\" action=\"default\">1</property>"
      "  </view>"
      " </item>"
      " <item>"
      "  <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">"
      "   <property name=\"orientation\" action=\"default\">Axial</property>"
      "   <property name=\"viewlabel\" action=\"default\">R</property>"
      "   <property name=\"viewcolor\" action=\"default\">#F34A33</property>"
      "  </view>"
      " </item>"
      "</layout>")
    self.red3dCustomLayoutId=504
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(self.red3dCustomLayoutId, customLayout)
    
    customLayout = ("<layout type=\"horizontal\" split=\"false\" >"
      " <item>"
      "  <view class=\"vtkMRMLViewNode\" singletontag=\"1\">"
      "    <property name=\"viewlabel\" action=\"default\">1</property>"
      "  </view>"
      " </item>"
      " <item>"
      "  <view class=\"vtkMRMLViewNode\" singletontag=\"2\" type=\"secondary\">"
      "   <property name=\"viewlabel\" action=\"default\">2</property>"
      "  </view>"
      " </item>"
      " <item>"
      "  <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">"
      "   <property name=\"orientation\" action=\"default\">Axial</property>"
      "   <property name=\"viewlabel\" action=\"default\">R</property>"
      "   <property name=\"viewcolor\" action=\"default\">#F34A33</property>"
      "  </view>"
      " </item>"
      "</layout>")
    self.redDual3dCustomLayoutId=505
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(self.redDual3dCustomLayoutId, customLayout)

  def setupAdvancedPanel(self):
    logging.debug('setupAdvancedPanel')

    self.advancedCollapsibleButton.setProperty('collapsedHeight', 20)
    #self.setButtonStyle(self.advancedCollapsibleButton, 2.0)
    self.advancedCollapsibleButton.text = "Settings"
    self.sliceletPanelLayout.addWidget(self.advancedCollapsibleButton)

    self.advancedLayout = qt.QFormLayout(self.advancedCollapsibleButton)
    self.advancedLayout.setContentsMargins(12, 4, 4, 4)
    self.advancedLayout.setSpacing(4)

    # Layout selection combo box
    self.viewSelectorComboBox = qt.QComboBox(self.advancedCollapsibleButton)
    self.viewSelectorComboBox.addItem("Ultrasound")
    self.viewSelectorComboBox.addItem("Ultrasound + 3D")
    self.viewSelectorComboBox.addItem("Ultrasound + Dual 3D")
    self.viewSelectorComboBox.addItem("3D")
    self.viewSelectorComboBox.addItem("Dual 3D")
    self.advancedLayout.addRow("Layout: ", self.viewSelectorComboBox)
    
    self.viewUltrasound = 0
    self.viewUltrasound3d = 1
    self.viewUltrasoundDual3d = 2
    self.view3d = 3
    self.viewDual3d = 4

    self.layoutManager = slicer.app.layoutManager()

    self.registerCustomLayouts(self.layoutManager)

    # Activate default view
    self.onViewSelect(self.viewUltrasound3d)

    # OpenIGTLink connector node selection
    self.linkInputSelector = slicer.qMRMLNodeComboBox()
    self.linkInputSelector.nodeTypes = (("vtkMRMLIGTLConnectorNode"), "")
    self.linkInputSelector.selectNodeUponCreation = True
    self.linkInputSelector.addEnabled = False
    self.linkInputSelector.removeEnabled = True
    self.linkInputSelector.noneEnabled = False
    self.linkInputSelector.showHidden = False
    self.linkInputSelector.showChildNodeTypes = False
    self.linkInputSelector.setMRMLScene( slicer.mrmlScene )
    self.linkInputSelector.setToolTip( "Select connector node" )
    self.advancedLayout.addRow("OpenIGTLink connector: ", self.linkInputSelector)

    self.showFullSlicerInterfaceButton = qt.QPushButton()
    self.showFullSlicerInterfaceButton.setText("Show full user interface")
    self.setButtonStyle(self.showFullSlicerInterfaceButton)
    #self.showFullSlicerInterfaceButton.setSizePolicy(self.sizePolicy)
    self.advancedLayout.addRow(self.showFullSlicerInterfaceButton)

    self.saveSceneButton = qt.QPushButton()
    self.saveSceneButton.setText("Save slicelet scene")
    self.setButtonStyle(self.saveSceneButton)
    self.advancedLayout.addRow(self.saveSceneButton)

    self.saveDirectoryLineEdit = qt.QLineEdit()
    settings = slicer.app.userSettings()
    self.saveDirectoryLineEdit.setText(self.getSavedScenesDirectory())
    saveLabel = qt.QLabel()
    saveLabel.setText("Save scene directory:")
    hbox = qt.QHBoxLayout()
    hbox.addWidget(saveLabel)
    hbox.addWidget(self.saveDirectoryLineEdit)
    self.advancedLayout.addRow(hbox)
  
  def fitUltrasoundImageToView(self):
    redWidget = self.layoutManager.sliceWidget('Red')
    redWidget.sliceController().fitSliceToBackground()

  def delayedFitUltrasoundImageToView(self, delayMsec=500):
    qt.QTimer.singleShot(delayMsec, self.fitUltrasoundImageToView) 

  def showUltrasoundIn3dView(self, show):
    redNode = slicer.util.getNode('vtkMRMLSliceNodeRed')
    if show:
      redNode.SetSliceVisible(1)
    else:
      redNode.SetSliceVisible(0)
    
  def onViewSelect(self, layoutIndex):
    logging.debug('onViewSelect: {0}'.format(layoutIndex))
    if layoutIndex == self.viewUltrasound:      
      self.layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
      self.delayedFitUltrasoundImageToView()
      self.showUltrasoundIn3dView(False)
    elif layoutIndex == self.viewUltrasound3d:
      self.layoutManager.setLayout(self.red3dCustomLayoutId)
      self.delayedFitUltrasoundImageToView()
      self.showUltrasoundIn3dView(True)
    elif layoutIndex == self.viewUltrasoundDual3d:
      self.layoutManager.setLayout(self.redDual3dCustomLayoutId)
      self.delayedFitUltrasoundImageToView()
      self.showUltrasoundIn3dView(True)
    elif layoutIndex == self.view3d:
      self.layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
      self.showUltrasoundIn3dView(True)
    elif layoutIndex == self.viewDual3d:
       self.layoutManager.setLayout(self.dual3dCustomLayoutId)
       self.showUltrasoundIn3dView(False)
    
  def onConnectorNodeActivated(self):
    logging.debug('onConnectorNodeActivated')
  
    self.removeConnectorObservers()

    # Start using new connector.
    self.connectorNode = self.linkInputSelector.currentNode()

    if not self.connectorNode:
      logging.warning('No connector node found!')
      return
      
    self.addConnectorObservers()

    #    if (self.parameterNode.GetParameter('EnableBreachWarningLight')!='True'):
    #      logging.debug("BreachWarningLight: shutdown 2")
    #      self.breachWarningLightLogic.shutdownLight(self.connectorNode)

  def removeConnectorObservers(self):
    # Clean up observers to old connector.
    if self.connectorNode and self.connectorNodeObserverTagList:
      for tag in self.connectorNodeObserverTagList:
        self.connectorNode.RemoveObserver(tag)
      self.connectorNodeObserverTagList = []

  def addConnectorObservers(self):

    # Force initial update
    if self.connectorNode.GetState() == slicer.vtkMRMLIGTLConnectorNode.STATE_CONNECTED:
      self.onConnectorNodeConnected(None, None, True)
    else:
      self.onConnectorNodeDisconnected(None, None, True)

    # Add observers for connect/disconnect events
    events = [[slicer.vtkMRMLIGTLConnectorNode.ConnectedEvent, self.onConnectorNodeConnected],
              [slicer.vtkMRMLIGTLConnectorNode.DisconnectedEvent, self.onConnectorNodeDisconnected]]
    for tagEventHandler in events:
      connectorNodeObserverTag = self.connectorNode.AddObserver(tagEventHandler[0], tagEventHandler[1])
      self.connectorNodeObserverTagList.append(connectorNodeObserverTag)

  def onConnectorNodeConnected(self, caller, event, force=False):
    logging.info("onConnectorNodeConnected")
    # Multiple notifications may be sent when connecting/disconnecting,
    # so we just if we know about the state change already
    if self.connectorNodeConnected and not force:
        return
    self.connectorNodeConnected = True
    self.freezeUltrasoundButton.setText('Freeze')   
    self.startStopRecordingButton.setEnabled(True)
    self.delayedFitUltrasoundImageToView(5000)
    
  def onConnectorNodeDisconnected(self, caller, event, force=False):
    logging.info("onConnectorNodeDisconnected")
    # Multiple notifications may be sent when connecting/disconnecting,
    # so we just if we know about the state change already
    if not self.connectorNodeConnected and not force:
        return
    self.connectorNodeConnected = False
    self.freezeUltrasoundButton.setText('Un-freeze')
    self.startStopRecordingButton.setEnabled(False)

  def onGenericCommandResponseReceived(self, commandId, responseNode):
    if responseNode:
      logging.debug("Response from PLUS: {0}".format(responseNode.GetText(0)))
    else:
      logging.debug("Timeout. Command Id: {0}".format(commandId))


  def onParameterNodeModified(self, observer, eventid):
    logging.debug('onParameterNodeModified')
    self.updateGUIFromParameterNode()

  def onCalibrationPanelToggled(self, toggled):
    if toggled == False:
      return

    logging.debug('onCalibrationPanelToggled: {0}'.format(toggled))
    
    self.onViewSelect(self.viewUltrasound3d) 

  def onUltrasoundPanelToggled(self, toggled):
    logging.debug('onUltrasoundPanelToggled: {0}'.format(toggled))

    self.onViewSelect(self.viewUltrasound) # Red only layout

  def onNavigationPanelToggled(self, toggled):
    if toggled == False:
      return

    logging.debug('onNavigationPanelToggled')
    self.onViewSelect(self.viewDual3d)
    self.tumorMarkups_Needle.SetDisplayVisibility(0)
    self.setupViewpoint()

    ## Stop live ultrasound.
    #if self.connectorNode != None:
    #  self.connectorNode.Stop()

  def setAndObserveParameterNode(self, parameterNode):
    if parameterNode == self.parameterNode and self.parameterNodeObserver:
      # no change and node is already observed
      return
    # Remove observer to old parameter node
    if self.parameterNode and self.parameterNodeObserver:
      self.parameterNode.RemoveObserver(self.parameterNodeObserver)
      self.parameterNodeObserver = None
    # Set and observe new parameter node
    self.parameterNode = parameterNode
    if self.parameterNode:
      self.parameterNodeObserver = self.parameterNode.AddObserver(vtk.vtkCommand.ModifiedEvent,
                                                                  self.onParameterNodeModified)
    # Update GUI
    self.updateGUIFromParameterNode()

  def executeCommand(self, command, commandResponseCallback):
    command.RemoveObservers(slicer.modulelogic.vtkSlicerOpenIGTLinkCommand.CommandCompletedEvent)
    command.AddObserver(slicer.modulelogic.vtkSlicerOpenIGTLinkCommand.CommandCompletedEvent, commandResponseCallback)
    slicer.modules.openigtlinkremote.logic().SendCommand(command, self.connectorNode.GetID())        

  def recordingCommandCompleted(self, command, q):
    statusText = "Command {0} [{1}]: {2}\n".format(command.GetCommandName(), command.GetID(), command.StatusToString(command.GetStatus()))
    statusTextUser = "{0} {1}\n".format(command.GetCommandName(), command.StatusToString(command.GetStatus()))
    if command.GetResponseMessage():
      statusText = statusText + command.GetResponseMessage()
      statusTextUser = command.GetResponseMessage()
    elif command.GetResponseText():
      statusText = statusText + command.GetResponseText()
      statusTextUser = command.GetResponseText()
    logging.info(statusText)
    self.startStopRecordingButton.setToolTip(statusTextUser)
      
  def updateGUIFromParameterNode(self):
    parameterNode = self.parameterNode
    if not parameterNode:
      return

  def setupConnectorNode(self):
    self.connectorNode = slicer.util.getNode('PlusConnector')
    if not self.connectorNode:
      self.connectorNode = slicer.vtkMRMLIGTLConnectorNode()
      slicer.mrmlScene.AddNode(self.connectorNode)
      self.connectorNode.SetName('PlusConnector')      
      hostNamePort = self.parameterNode.GetParameter('PlusServerHostNamePort') # example: "localhost:18944"
      [hostName, port] = hostNamePort.split(':')
      self.connectorNode.SetTypeClient(hostName, int(port))
      logging.debug("PlusConnector created")
    self.connectorNode.Start()
    
  def writeTransformToSettings(self, transformName, transformMatrix):
    transformMatrixArray = []
    for r in xrange(4):
      for c in xrange(4):
        transformMatrixArray.append(transformMatrix.GetElement(r,c))
    transformMatrixString = ' '.join(map(str, transformMatrixArray)) # string, numbers are separated by spaces
    settings = slicer.app.userSettings()
    settings.setValue('BaseNav/{0}'.format(transformName), transformMatrixString)

  def readTransformFromSettings(self, transformName):
    transformMatrix = vtk.vtkMatrix4x4()
    settings = slicer.app.userSettings()
    transformMatrixString = settings.value('BaseNav/{0}'.format(transformName))
    if not transformMatrixString:
      return None
    transformMatrixArray = map(float, transformMatrixString.split(' '))
    for r in xrange(4):
      for c in xrange(4):
        transformMatrix.SetElement(r,c, transformMatrixArray[r*4+c])
    return transformMatrix
 
  def getSavedScenesDirectory(self):
    settings = slicer.app.userSettings()
    sceneSaveDirectory = settings.value('BaseNav/SavedScenesDirectory')
    if not sceneSaveDirectory:
      sceneSaveDirectory = os.path.dirname(slicer.modules.basenav.path)+'/SavedScenes'
    return sceneSaveDirectory

  def setSavedScenesDirectory(self, sceneSaveDirectory):
    settings = slicer.app.userSettings()
    settings.setValue('BaseNav/SavedScenesDirectory', sceneSaveDirectory)
    
#
# BaseNav
#

class BaseNav(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "BaseNav"
    self.parent.categories = ["IGT"]
    self.parent.dependencies = []
    self.parent.contributors = ["Tamas Ungi (Perk Lab)"]
    self.parent.helpText = """
    This is an example of scripted loadable module bundled in an extension.
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
    and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

    self.parent = parent


#
# BaseNavWidget
#

class BaseNavWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent = None):
    ScriptedLoadableModuleWidget.__init__(self, parent)

    self.sliceletInstance = None
    self.logic = BaseNavLogic()

    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
    else:
      self.parent = parent

    self.layout = self.parent.layout()
    if not parent:
      self.setup()
      self.parent.show()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...

    try:
      slicer.modules.plusremote
    except:
      self.errorLabel = qt.QLabel("Error: Could not find Plus Remote module. Please install the SlicerIGT extension.")
      self.layout.addWidget(self.errorLabel)
      return

    # Launcher panel
    launcherCollapsibleButton = ctk.ctkCollapsibleButton()
    launcherCollapsibleButton.text = "Slicelet launcher"
    self.layout.addWidget(launcherCollapsibleButton)
    self.launcherFormLayout = qt.QFormLayout(launcherCollapsibleButton)

    lnNode=slicer.util.getNode("BaseNav")
    self.lineEdit = qt.QLineEdit()
    leLabel = qt.QLabel()
    leLabel.setText("Set the Plus Server Host and Name Port:")
    hbox = qt.QHBoxLayout()
    hbox.addWidget(leLabel)
    hbox.addWidget(self.lineEdit)
    self.launcherFormLayout.addRow(hbox)

    if(lnNode is not None and lnNode.GetParameter('PlusServerHostNamePort')):
        logging.debug("There is already a connector PlusServerHostNamePort parameter " + lnNode.GetParameter('PlusServerHostNamePort') )
        self.lineEdit.setDisabled(True)
        self.lineEdit.setText(lnNode.GetParameter('PlusServerHostNamePort'))
    else:
        self.lineEdit.setDisabled(False)
        settings = slicer.app.userSettings()
        plusServerHostNamePort = settings.value('BaseNav/PlusServerHostNamePort', 'localhost:18944')
        self.lineEdit.setText(plusServerHostNamePort)

    # Show slicelet button
    self.launchSliceletButton = qt.QPushButton("Start BaseNav")
    self.launchSliceletButton.toolTip = "Launch the navigation module in full screen mode"
    self.launcherFormLayout.addWidget(self.launchSliceletButton)
    self.launchSliceletButton.connect('clicked()', self.onShowSliceletButtonClicked)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    self.launchSliceletButton.disconnect('clicked()', self.onShowSliceletButtonClicked)
    #logging.debug(slicer.baseNavSliceletInstance)#Todo fix clean up!
    #if(slicer.baseNavSliceletInstance != None):
    #    slicer.baseNavSliceletInstance.setAndObserveParameterNode(None)
    #self.setAndObserveParameterNode(None)
    pass

  def onShowSliceletButtonClicked(self):
    logging.debug('onShowSliceletButtonClicked')
    
    parameterList = {}
    #Set editable connector server and host
    settings = slicer.app.userSettings()
    if(self.lineEdit.isEnabled() and self.lineEdit.text != ''):
        settings.setValue('BaseNav/PlusServerHostNamePort', self.lineEdit.text)        
        parameterList['PlusServerHostNamePort']= self.lineEdit.text

    if self.sliceletInstance:
      self.sliceletInstance.showFullScreen()
    else:
      if(parameterList!= None):
          self.sliceletInstance = BaseNavSlicelet(None,parameterList)
      else:
          self.sliceletInstance = BaseNavSlicelet(None)

  def onSliceletClosed(self):
    logging.debug('Slicelet closed')

#
# BaseNavLogic
#

class BaseNavLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent = None):
    ScriptedLoadableModuleLogic.__init__(self, parent)
    self.isSingletonParameterNode = True

  def createParameterNode(self):
    node = ScriptedLoadableModuleLogic.createParameterNode(self)
    parameterList = {'RecordingFilename': "BaseNav-Record.mha",
                     'LiveUltrasoundNodeName': 'Image_Reference',
                     'LiveUltrasoundNodeName_Needle': 'Image_Needle',
                     'PlusServerHostNamePort':'localhost:18944'
                     }

    for parameter in parameterList:
      if not node.GetParameter(parameter):
        node.SetParameter(parameter, str(parameterList[parameter]))

    return node

class BaseNavTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_BaseNav1()

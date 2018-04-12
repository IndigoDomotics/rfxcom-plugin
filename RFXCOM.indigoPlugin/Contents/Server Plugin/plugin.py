#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# RFXTRX Plugin
# Developed by Robert de Kok
# www.rjdekok.nl

import os
import sys
import re
import Queue
import serial
import threading
import time

from RFXTRX import RFXTRX

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        
		self.RFXTRX = RFXTRX(self)
		self.debug = pluginPrefs.get(u'showDebugInfo', False)

	def __del__(self):
		indigo.PluginBase.__del__(self)
    
	########################################	
	
	def startup(self):
		self.RFXTRX.startup()
		self.debugLog(u"startup called")
    
	def shutdown(self):
		self.debugLog(u"shutdown called")
    
	######################
	def deviceStartComm(self, dev):
		self.debugLog(u"<<-- entering deviceStartComm: %s (%d - %s)" % (dev.name, dev.id, dev.deviceTypeId))
		self.RFXTRX.deviceStart(dev)
    
	def deviceStopComm(self, dev):
		self.debugLog(u"<<-- entering deviceStopComm: %s (%d - %s)" % (dev.name, dev.id, dev.deviceTypeId))
		self.RFXTRX.deviceStop(dev)
    
	#def deviceUpdated(self, origDev, newDev):
	#	self.debugLog(u"<<-- entering deviceUpdated: %s" % origDev.name)	
	#	self.RFXTRX.deviceStop(origDev)
	#	self.RFXTRX.deviceStart(newDev)
    
	######################
	def triggerStartProcessing(self, trigger):
		self.debugLog(u"<<-- entering triggerStartProcessing: %s (%d)" % (trigger.name, trigger.id))
    #self.RFXTRX.triggerStart(trigger)
    
	def triggerStopProcessing(self, trigger):
		self.debugLog(u"<<-- entering triggerStopProcessing: %s (%d)" % (trigger.name, trigger.id))
    #self.RFXTRX.triggerStop(trigger)
    
	def triggerUpdated(self, origDev, newDev):
		self.debugLog(u"<<-- entering triggerUpdated: %s" % origDev.name)	
    #self.RFXTRX.triggerStop(origDev)
    #self.RFXTRX.triggerStart(newDev)
    
	def openRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnOff(pluginAction, dev) == True:
			sendSuccess = True

	def closeRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnOn(pluginAction, dev) == True:
			sendSuccess = True

	def stopRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnStop(pluginAction, dev) == True:
			sendSuccess = True

	def programRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnProgram(pluginAction, dev) == True:
			sendSuccess = True
			
	def limitRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnLimit(pluginAction, dev) == True:
			sendSuccess = True			

	def UpRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnUp(pluginAction, dev) == True:
			sendSuccess = True	
			
	def DownRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnDown(pluginAction, dev) == True:
			sendSuccess = True	
						
	def AnglePlusRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnAnglePlus(pluginAction, dev) == True:
			sendSuccess = True	
			
	def AngleMinRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnAngleMin(pluginAction, dev) == True:
			sendSuccess = True	
			
	def RunUpRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnRunUp(pluginAction, dev) == True:
			sendSuccess = True	
			
	def RunDownRelay(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.TurnRunDown(pluginAction, dev) == True:
			sendSuccess = True				

	def colorPlus(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.ColorPlus(pluginAction, dev) == True:
			sendSuccess = True			
			    
	def colorMin(self, pluginAction):
		dev = indigo.devices[pluginAction.deviceId]
		sendSuccess = False
		if self.RFXTRX.ColorMin(pluginAction, dev) == True:
			sendSuccess = True	

	def filterdevices(self, filter="", valuesDict=None, typeId="", devId=""):
		return self.RFXTRX.filterdevices()

	def buttonConfirmRESETCALLBACK(self,valuesDict=None, filter="", typeId="", devId=""):
		self.RFXTRX.ResetDevice(valuesDict["selectedDevice"])
		return valuesDict
			
	########################################
	# Relay / Dimmer Action callback
	######################
	def actionControlDimmerRelay(self, action, dev):
		self.debugLog(u"Actions...%s"% action.deviceAction)
		
		###### TURN ON ######
		if action.deviceAction == indigo.kDeviceAction.TurnOn:
			# Command hardware module (dev) to turn ON here:
			# self.debugLog(u"Variabelen: \"%s\" %s %s" % (self, action, dev.name))
			sendSuccess = False
			if self.RFXTRX.TurnOn(action, dev) == True:
				sendSuccess = True		# Set to False if it failed.
            
			if sendSuccess:			
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s" % (dev.name, "on"))
                
				# And then tell the Indigo Server to update the state.
				dev.updateStateOnServer("onOffState", True)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "on"), isError=True)
				
		###### TURN OFF ######
		elif action.deviceAction == indigo.kDeviceAction.TurnOff:
			# Command hardware module (dev) to turn OFF here:
			sendSuccess = False
			if self.RFXTRX.TurnOff(action, dev) == True:
				sendSuccess = True		# Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s" % (dev.name, "off"))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", False)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)
        
		###### TOGGLE ######
		elif action.deviceAction == indigo.kDeviceAction.Toggle:
			# Command hardware module (dev) to toggle here:
			# ** IMPLEMENT ME **
			if dev.onState:
				sendSuccess = self.RFXTRX.TurnOff(action, dev)
			else:	
				sendSuccess = self.RFXTRX.TurnOn(action, dev)
			
			if sendSuccess:
				newOnState = not dev.onState
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s" % (dev.name, "toggle"))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", newOnState)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "toggle"), isError=True)
        
		###### SET BRIGHTNESS ######
		elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
			if self.RFXTRX.SetBrightLevel(action, dev, action.actionValue) == True:
				sendSuccess = True		# Set to False if it failed.
			newBrightness = action.actionValue
			sendSuccess = True		# Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s to %d" % (dev.name, "set brightness", newBrightness))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				self.debugLog(u"send \"%s\" %s to %d failed" % (dev.name, "set brightness", newBrightness), isError=True)
        
		###### BRIGHTEN BY ######
		elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
			#if self.RFXTRX.TurnBright(action, dev, 0) == True:
			newBrightness = dev.brightness + action.actionValue
			if newBrightness > 100:
				newBrightness = 100
			sendSuccess = False   
			if self.RFXTRX.TurnBright(action, dev, newBrightness) == True:
				sendSuccess = True      # Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s to %d (%d)" % (dev.name, "brighten", newBrightness, action.actionValue))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				self.debugLog(u"send \"%s\" %s to %d failed" % (dev.name, "brighten", newBrightness), isError=True)
        
		###### DIM BY ######
		elif action.deviceAction == indigo.kDeviceAction.DimBy:
			#if self.RFXTRX.TurnDim(action, dev) == True:
			newBrightness = dev.brightness - action.actionValue
			if newBrightness < 0:
				newBrightness = 0
			sendSuccess = False   
			if self.RFXTRX.TurnDim(action, dev, newBrightness) == True:
				sendSuccess = True      # Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s to %d (%d)" % (dev.name, "brighten", newBrightness, action.actionValue))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s to %d failed" % (dev.name, "dim", newBrightness), isError=True)
		
		###### All Lights Off ######
		elif action.deviceAction == indigo.kDeviceAction.AllLightsOff:
			# Command hardware module (dev) to turn OFF here:
			sendSuccess = False
			if self.RFXTRX.TurnAllOff(action, dev) == True:
				sendSuccess = True		# Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s" % ("off"))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", False)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)
		
		###### All Lights On ######
		elif action.deviceAction == indigo.kDeviceAction.AllLightsOn:
			# Command hardware module (dev) to turn OFF here:
			sendSuccess = False
			if self.RFXTRX.TurnAllOn(action, dev) == True:
				sendSuccess = True		# Set to False if it failed.
            
			if sendSuccess:
				# If success then log that the command was successfully sent.
				self.debugLog(u"sent \"%s\" %s" % ("off"))
                
				# And then tell the Indigo Server to update the state:
				dev.updateStateOnServer("onOffState", False)
			else:
				# Else log failure but do NOT update state on Indigo Server.
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)
    
    
	########################################		
    
	def runConcurrentThread(self):
		self.debugLog(u"runConcurrentThread called")
		self.RFXTRX.startComm()
    
	def stopConcurrentThread(self):
		self.debugLog(u"stopConcurrentThread called")
		self.RFXTRX.stopComm()
    
	def reinitialize(self,onzin):
		self.debugLog(u"Reinitialize")
		self.RFXTRX.configRead = False	
    
	def inptest(self,onzin):
		self.RFXTRX.inptest()		
		
	########################################
	# Prefs UI methods (works with PluginConfig.xml):
	########################################
    
	# Validate the pluginConfig window after user hits OK
	# Returns False on failure, True on success
	#
    
	def validatePrefsConfigUi(self, valuesDict):	
		self.debugLog(u"validating Prefs called")
		
		if len(valuesDict[u'serialPort']) == 0:
			errorMsgDict = indigo.Dict()
			errorMsgDict[u'serialPort'] = u"Select a valid serial port."
			return (False, valuesDict, errorMsgDict)
        
		if len(valuesDict[u'baudRate']) == 0:
			errorMsgDict = indigo.Dict()
			errorMsgDict[u'baudRate'] = u"Select a valid baudrate."
			return (False, valuesDict, errorMsgDict)			
        
		# Tell RFXTRX module to reread it's config
		self.RFXTRX.configRead = False
		
		# User choices look good, so return True (client will then close the dialog window).
		return (True, valuesDict)
    
    
	def validateActionConfigUi(self, valuesDict, typeId, actionId):
		self.debugLog(u"validating Action Config called")
		if typeId == u'actionSendKeypress':
			keys = valuesDict[u'keys']
			cleanKeys = re.sub(r'[^a-e0-9LFAP<>=*#]+', '', keys)
			if len(keys) != len(cleanKeys):
				errorMsgDict = indigo.Dict()
				errorMsgDict[u'keys'] = u"There are invalid keys in your keystring."
				return (False, valuesDict, errorMsgDict)
		return (True, valuesDict)
		
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		self.debugLog(u"validateDeviceConfigUi called")
		errorsDict = indigo.Dict()

		if typeId in ["Temperature","Doorbell","BBQ","Barometer","Humidity","UVMeter","ELEC1CurrentSensor","ELEC2EnergyUsageSensor","RFXSensor","RFXMeter","Rainsensor","SecuritySensor","WindSensor"]:
			try:
				dummy = int(valuesDict["sensorNumber"])
				valuesDict["address"] = valuesDict["sensorNumber"]
				self.debugLog(u"wrote address for " + valuesDict["sensorNumber"])
			except (ValueError):
				errorsDict["sensorNumber"] = u"Must be an integer"
	
		if len(errorsDict) > 0:
			# Some UI fields are not valid, return corrected fields and error messages (client
			# will not let the dialog window close).
			return (False, valuesDict, errorsDict)
					
		# User choices look good, so return True (client will then close the dialog window).	
		return (True, valuesDict)
		
	def updateState(self, action):
		self.debugLog(u"updateState action called")
		if action.deviceId != 0:
			try:
				devtmp = indigo.devices[action.deviceId]
			except:
				self.errorLog(u"Invalid device specified in updateState action")
         
		if "onOffState" in action.props:
			# Update server on/off state
			stateValue = action.props.get(u"onOffState")
			if stateValue == "on": stateValue = True
			if stateValue == "off": stateValue = False
			if (stateValue == True or stateValue == False) and stateValue != "nochange":
				self.debugLog(u"    Update server On/Off state for device id %s with %s" % (str(action.deviceId), str(stateValue)))
				devtmp.updateStateOnServer("onOffState", stateValue)
			elif stateValue == "nochange":
				self.debugLog(u"   Update server On/Off state for device id %s - No Change" % str(action.deviceId))
			else:
				self.errorLog(u"Invalid On/Off state specified for updateState action")

		if "brightness" in action.props:
			# Update server brightness level
			brightnessLevel = action.props.get(u"brightness")
			try:
				self.debugLog(u"Update server state BrightnessLevel: --%s--" % str(brightnessLevel))
				if brightnessLevel == "":
					self.debugLog(u"   Update server brightness level for device id %s - No Change" % str(action.deviceId))
				else:
					brightnessLevel = int(brightnessLevel)
					self.debugLog(u"    Update server brightness level for device id %s with %s" % (str(action.deviceId), str(brightnessLevel)))
					devtmp.updateStateOnServer("brightnessLevel", brightnessLevel)
			except:
				self.errorLog(u"Invalid brightness level specified for updateState action")		

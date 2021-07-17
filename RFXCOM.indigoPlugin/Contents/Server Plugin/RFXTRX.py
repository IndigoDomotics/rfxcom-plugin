#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2012, Robert de Kok. All rights reserved.
# http://www.rjdekok.nl

import os
import serial
import sys
import time
import indigo
import re
import traceback
import datetime
import array
import copy

kBadSerialRetryInterval = 5
kSleepBetweenComm = 0.011
kSleepBetweenIdlePolls = 0.050

################################################################################
class RFXTRX(object):
	########################################
	def __init__(self, plugin):
		self.plugin = plugin
		self.shutdown = False
		self.configRead = False
		self.port = None
		self.devicesCopy = {}		
		self.batchStatesUpdate = {}
		self.sensorValues = {}
		self.pluginState = "init"

	def __del__(self):
		pass

	def startup(self):
		self.plugin.debugLog(u"RFXCOM startup called")

	########################################
	def _finalizeStatesChanges(self):
		if len(self.batchStatesUpdate) == 0:
			return
		for devId in self.batchStatesUpdate:
			dev = indigo.devices[devId]
			
			## added 4/14/2018 : ## this is for devtype = sensor, display does not work, need to copy display into sensorValue ##
			if "sensorValue" in dev.states: 
				for item in self.batchStatesUpdate[devId]:
					if item["key"] == "display":
						ap = copy.copy(item)
						ap["key"] = "sensorValue"
						self.batchStatesUpdate[devId].append(ap)
						break 

			self.plugin.debugLog("finalizeStatesChanges:" +dev.name+" :" + unicode(self.batchStatesUpdate[devId]) )
			try:
				dev.updateStatesOnServer(self.batchStatesUpdate[devId])
			except Exception, e:
				indigo.server.log("_finalizeStatesChanges in Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e)+", dev: "+ dev.name+"  "+ unicode(self.batchStatesUpdate[devId]))
 
			self.deviceStart(dev, force=True)
		self.batchStatesUpdate = {}
		return

	def _addToBatchStatesChange(self, dev, key="", value="", decimalPlaces="", uiValue=""):
		devID = dev.id

		if key not in dev.states:  
			self.plugin.debugLog("addToBatchStatesChange:" +dev.name+"; key >>"+ key+"<< not in states" )
			return
			
		if devID not in self.batchStatesUpdate:
			self.batchStatesUpdate[devID] = []
		nn      = 0
		useKey  = -1
		ap      = {}
		for kk in self.batchStatesUpdate[devID]:
			if key in kk:
				useKey= nn
				ap = kk
				break
			nn +=1
			
		ap["key"]   = key
		ap["value"] = value
		if decimalPlaces != "":
			if decimalPlaces ==0:
			    ap["value"] = int(float(value)) # make it integer  eg "10" not "10."
			else:
				ap["decimalPlaces"] = int(decimalPlaces)
		if uiValue != "":
			ap["uiValue"] = uiValue 
			
		if useKey !=-1:
			self.batchStatesUpdate[devID][useKey] = ap
		else:
			self.batchStatesUpdate[devID].append(ap)

		if devID not in self.sensorValues:
			self.sensorValues[devID] = {}
		self.sensorValues[devID][key] = value
		return

	def _getCurrentSensorValue(self, dev, key):
		devID = dev.id
		if devID not in self.sensorValues:
			self.sensorValues[devID] = {}
		if key not in self.sensorValues[devID]:
			self.sensorValues[devID][key] = dev.states[key]
		return self.sensorValues[devID][key]

	########################################

	########################################
	# Configuration
	#
	# Reads the indigo plugin Dict into our own variables.
	# Returns True on success
	#
	def getConfiguration(self,valuesDict):
		self.plugin.debug = valuesDict.get(u'showDebugInfo', False)
		self.plugin.debugLog(u"getConfiguration start")
		
		# Check the serial port name.
		serialPort = valuesDict.get(u'serialPort', "")
		if len(serialPort) == 0:
			return False	# no chance of it working without a serial port specified


		self.plugin.unitsTemperature = valuesDict.get(u'unitsTemperature', u"C")
		self.plugin.unitsRain        = valuesDict.get(u'unitsRain', u"mm")
		self.plugin.unitsWind        = valuesDict.get(u'unitsWind', u"mps")

		try:    self.plugin.digitsTemperature = int(valuesDict.get(u'digitsTemperature', 1))
		except: self.plugin.digitsTemperature = 1
		try:    self.plugin.digitsRain        = int(valuesDict.get(u'digitsRain', 1))
		except: self.plugin.digitsRain        = 1
		try:    self.plugin.digitsWind        = int(valuesDict.get(u'digitsWind', 1))
		except: self.plugin.digitsWind        = 1


		self.plugin.unknownAsError       = valuesDict.get(u'unknownAsError', False)
		self.plugin.showUndecodedPackets = valuesDict.get(u'showUndecodedPackets', False)
		return True

	########################################			
	def reinitialize(self):
		self.plugin.debugLog(u"reinitialize called")		

	########################################
	def SendResetAndInit(self):
		packdata = chr(0x00)+chr(0x00)+chr(0x00)+chr(0x00)
		self.sendPacket("send reset cmd", packdata, 0x0D)
		time.sleep(1)
		self.port.flushInput()

		self.port.write(chr(0xC1))
		replyData = self.readPacket()
		self.logdata(replyData, "PIC INIT IS")

		packdata = chr(0x00)+chr(0x00)+chr(0x01)+chr(0x02)
		self.sendPacket("send init cmd", packdata, 0x0D)
		replyData = self.readPacket()
		self.logdata(replyData, "rcvd init reply")

		if replyData is None or len(replyData) < 13:
			return False	# didn't get expected response

		if ord(replyData[1]) != 0x01 or ord(replyData[2]) != 0x00:
			return False	# response packet type should be 0x01
		if ord(replyData[4]) != 0x02:
			return False	# expecting a reply to our init (0x02) command

		rfxType = ord(replyData[5])
		rfxTypeStr = u"unknown"
		rfxFrequency = 0
		rfxTransmits = True
		if rfxType >= 0x50 and rfxType <= 0x5B:
			rfxTypeStr = u"RFXtrx"
			if rfxType == 0x52:
				rfxTypeStr = u"RFXrec"
				rfxTransmits = False
			rfxTypeStr += u" "
			rfxTypeStr += [u"310 MHz", u"315 MHz", u"433.92 MHz", u"433.92 MHz", u"868.00 MHz", u"868.00 MHz FSK", u"868.30 MHz", u"868.30 MHz FSK", u"868.35 MHz", u"868.35 MHz FSK", u"868.95 MHz"][rfxType - 0x50]
			rfxFrequency = [310, 315, 433.92, 433.92, 868.00, 868.00, 868.30, 868.30, 868.35, 868.35, 868.95][rfxType - 0x50]

		rfxFirmwareVers = ord(replyData[6])
		rfxEnableUndecoded = (ord(replyData[7]) & 0x80)

		currentProtocolList = []
		enabledProtocolList = []
		disabledProtocolList = []

		curProtoFlags = [ord(replyData[7]), ord(replyData[8]), ord(replyData[9])]
		newProtoFlags = [curProtoFlags[0], curProtoFlags[1], curProtoFlags[2]]

		protoTable = [
			# preference key					log name				frequencies			byte index		bit flag index		disable cmd		can receive
			[u"enableProtocolUndecoded",		u"Undecoded",			[433.92],			0,				7,					None,			True],
			[u"enableProtocolRFU",				u"RFU",					[433.92],			0,				6,					None,			True],
			[u"enableProtocolByron",			u"Byron",				[433.92],			0,				5,					None,			True],
			[u"enableProtocolRSL",				u"RSL",					[433.92],			0,				4,					0x1C,			True],
			[u"enableProtocolLightning4",		u"Lightning4",			[433.92],			0,				3,					0x1B,			True],
			[u"enableProtocolViking",			u"Viking",				[433.92],			0,				2,					0x1A,			True],
			[u"enableProtocolRubicson",			u"Rubicson",			[433.92],			0,				1,					0x18,			True],
			[u"enableProtocolAEBlyss",			u"AE Blyss",			[433.92],			0,				0,					None,			True],
			[u"enableProtocolBlindsT1234",		u"Blinds T1234",		[433.92],			1,				7,					None,			True],
			[u"enableProtocolBlindsT0",			u"Blinds T0",			[433.92],			1,				6,					None,			True],
			[u"enableProtocolProGuard",			u"ProGuard",			[868.35],			1,				5,					None,			True],
			[u"enableProtocolFS20",				u"FS20",				[868.35],			1,				4,					0x1C,			True],
			[u"enableProtocolLaCrosse",			u"La Crosse",			[433.92, 868.30],	1,				3,					0x1B,			True],
			[u"enableProtocolHideki",			u"Hideki",				[433.92],			1,				2,					0x1A,			True],
			[u"enableProtocolLightwaveRF",		u"LightwaveRF",			[433.92],			1,				1,					None,			True],
			[u"enableProtocolMertik",			u"Mertik",				[433.92],			1,				0,					0x18,			True],
			[u"enableProtocolVisonic",			u"Visonic",				[315, 868.95],		2,				7,					0x17,			True],
			[u"enableProtocolATI",				u"ATI",					[433.92],			2,				6,					0x16,			True],
			[u"enableProtocolOregonScientific",	u"Oregon Scientific",	[433.92],			2,				5,					0x15,			True],
			[u"enableProtocolIkeaKoppla",		u"Ikea-Koppla",			[433.92],			2,				4,					0x14,			False],
			[u"enableProtocolHomeEasyEU",		u"HomeEasy EU",			[433.92],			2,				3,					0x13,			True],
			[u"enableProtocolAC",				u"AC",					[433.92],			2,				2,					0x12,			True],
			[u"enableProtocolARC",				u"ARC",					[433.92],			2,				1,					0x11,			True],
			[u"enableProtocolX10",				u"X10",					[310, 433.92],		2,				0,					0x10,			True]
		]

		for protoInfo in protoTable:
			userPrefEnabled = self.plugin.pluginPrefs.get(protoInfo[0], True)
			protoLogName = protoInfo[1]
			protoFrequencies = protoInfo[2]
			protoByteIndex = protoInfo[3]
			protoBitFlag = (1 << protoInfo[4])
			protoDisableCmd = protoInfo[5]
			protoCanReceive = protoInfo[6]
			if not protoCanReceive:
				continue	# protocol enable/disable states only apply for receiving
			if curProtoFlags[protoByteIndex] & protoBitFlag:
				currentProtocolList.append(protoLogName)
				if not userPrefEnabled and rfxFrequency in protoFrequencies:
					# User wants it disabled but it currently is enabled (and
					# the frequency of the protocol is supported by hardware),
					# add to our disable list and clear the flag.
					disabledProtocolList.append(protoLogName)
					newProtoFlags[protoByteIndex] &= ~protoBitFlag
			else:
				if userPrefEnabled and rfxFrequency in protoFrequencies:
					# User wants it enabled but it currently is disabled (and
					# the frequency of the protocol is supported by hardware),
					# add to our enable list and set the flag.
					enabledProtocolList.append(protoLogName)
					newProtoFlags[protoByteIndex] |= protoBitFlag

		indigo.server.log(u"connected to %s, firmware version %d" % (rfxTypeStr, rfxFirmwareVers))
		if rfxEnableUndecoded:
			indigo.server.log(u"undecoded packet displaying is currently enabled")
		if len(currentProtocolList) > 0:
			indigo.server.log(u"currently enabled receiver protocols: %s" % (u", ".join(currentProtocolList)))

		if newProtoFlags != curProtoFlags:
			# The user defined (UI) settings don't match the currently enabled protocols,
			# so we modify to match what the user wants.
			if self.plugin.showUndecodedPackets != rfxEnableUndecoded:
				if self.plugin.showUndecodedPackets:
					indigo.server.log(u"enabling undecoded packet displaying")
				else:
					indigo.server.log(u"disabling undecoded packet displaying")

			if len(enabledProtocolList) > 0:
				indigo.server.log(u"enabling receiver protocols: %s" % (u", ".join(enabledProtocolList)))
			if len(disabledProtocolList) > 0:
				indigo.server.log(u"disabling receiver protocols: %s" % (u", ".join(disabledProtocolList)))

			if rfxFirmwareVers < 39 and rfxType == 0x52:
				# Older firmware will fail on set mode commmand (nothing returned) if we try
				# to set the type to RFXrec433, even when that is the firmware version being
				# used. Override to RFXtrx433 in this case to avoid the problem.
				rfxType = 0x53

			# Send the set mode command.
			packdata = chr(0x00)+chr(0x00)+chr(0x02)+chr(0x03)+chr(rfxType)+chr(0x00)+chr(newProtoFlags[0])+chr(newProtoFlags[1])+chr(newProtoFlags[2])+chr(0x00)+chr(0x00)+chr(0x00)+chr(0x00)
			self.sendPacket("send set mode cmd", packdata, 0x0D)

			# Wait for a good reply.
			rcvdSetModeReply = False
			while not rcvdSetModeReply:
				replyData = self.readPacket()
				if replyData is None:
					return False	# didn't get expected response, time to fail and bail.

				if len(replyData) >= 13 and ord(replyData[1]) == 0x01 and ord(replyData[2]) == 0x00 and ord(replyData[4]) == 0x03:
					# got expected reply, break out and continue processing
					self.logdata(replyData, "rcvd set mode reply")
					rcvdSetModeReply = True
				else:
					# else log, ignore (probably incoming RF data), and wait for expected packet
					self.logdata(replyData, "ignoring cmd")
			
			# And finally commit changes to flash memory. Note we only do this when there is a successful
			# reply since flash writes have a 10K write cycle life. We also only do this for proto flag
			# changes because the opModeFlag changes appear to NOT be stored in flash memory.
			if newProtoFlags != curProtoFlags:
				packdata = chr(0x00)+chr(0x00)+chr(0x03)+chr(0x06)
				self.sendPacket("send save to flash cmd", packdata, 0x0D)
				indigo.server.log(u"stored changed settings into non-volatile memory")

				replyData = self.readPacket()
				self.logdata(replyData, "rcvd save to flash reply")

		return True

################ reset rain sensor device
	def filterdevices(self):
		list = []
		for sensor in self.devicesCopy:
			dev =  indigo.devices[self.devicesCopy[sensor]]
			if not dev.deviceTypeId == u'Rainsensor':   continue
			list.append([ str(dev.id)+"-"+str(sensor),dev.name ])
		return sorted(list, key=lambda x: x[1])
		
	def ResetDevice(self,devId):
		sensor = int(devId.split("-")[1])
		if sensor in self.devicesCopy:
			dev = indigo.devices[int(self.devicesCopy[sensor].id)]
			# set states to 0
			self._addToBatchStatesChange(dev, key=u"rainrate", value=0, decimalPlaces=self.plugin.digitsRain)
			self._addToBatchStatesChange(dev, key=u"raintotal", value=0, decimalPlaces=self.plugin.digitsRain)
			self._addToBatchStatesChange(dev, key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			self._addToBatchStatesChange(dev, key=u"currentDayTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"previousDayTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"currentWeekTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"previousWeekTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"currentMonthTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"previousMonthTotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			self._addToBatchStatesChange(dev, key=u"raintotal", value=0, decimalPlaces=self.plugin.digitsRain)			
			#self._finalizeStatesChanges()()
			# refresh
			dev = indigo.devices[dev.id]
			localProps = dev.pluginProps
			localProps["last7Days"] = "0,0,0,0,0,0,0"
			localProps["currentMonthNumber"] = 0
			localProps["currentWeekNumber"] = 0
			dev.replacePluginPropsOnServer(localProps)			
			self.devicesCopy[sensor] = indigo.devices[self.devicesCopy[sensor].id]
		return 
################ reset rain sensor device  END


	def ReturnLightType(self, action, dev):
		if dev.deviceTypeId == 'X10Appliance':
			return 0x00
		elif dev.deviceTypeId == 'X10Dimmer':
			return 0x00			
		elif dev.deviceTypeId == 'ACAppliance':
			return 0x00
		elif dev.deviceTypeId == 'ACDimmer':
			return 0x00			
		elif dev.deviceTypeId == 'HEAppliance':
			return 0x01
		elif dev.deviceTypeId == 'HEDimmer':
			return 0x01			
		elif dev.deviceTypeId == 'ARCAppliance':
			return 0x01
		elif dev.deviceTypeId == 'ELROAppliance':
			return 0x02			
		elif dev.deviceTypeId == 'ELROAppliance':
			return 0x02
		elif dev.deviceTypeId == 'BlyssAppliance':
			return 0x00
		elif dev.deviceTypeId == 'EMWAppliance':
			return 0x04
		elif dev.deviceTypeId == 'LWAppliance':
			return 0x00
		elif dev.deviceTypeId == 'RollerTrol':
			return 0x00		
		elif dev.deviceTypeId == 'A-OK_RF01':
			return 0x02	
		elif dev.deviceTypeId == 'A-OK_AC114':
			return 0x03
		elif dev.deviceTypeId == 'BlindsT1234':
			return 0x06
		elif dev.deviceTypeId == 'Brel':
			return 0x06					
		elif dev.deviceTypeId == 'Somfy':
			return 0x00		
		elif dev.deviceTypeId == 'Mertik':
			return 0x00				
		elif dev.deviceTypeId == 'Harrison':
			return 0x00					
		elif dev.deviceTypeId == 'LWDimmer':
			return 0x00
		elif dev.deviceTypeId == 'MDRemote':
			return 0x03			
		elif dev.deviceTypeId == 'LivoloDimmer':
			return 0x05
		elif dev.deviceTypeId == 'RGBDimmer':
			return 0x06
		elif dev.deviceTypeId == 'EMW100Appliance':
			return 0x01
		elif dev.deviceTypeId == 'EMW100Dimmer':
			return 0x01
		else:
			return 0x10

	def RecalcAddress(self, adres):
		self.plugin.debugLog(u"Adres: %s " % adres)
		return chr(int(adres))

	def TurnDevice(self, action, dev, command, BrightLevel):
		if self.configRead == False:
			indigo.server.log(u"serial port not initialized... command skipped.", isError=True)
			return False

		try: 
			if self.configRead == True:
				if command=='Off':
					commcode=chr(0x00)
				if command=='On':
					commcode=chr(0x01)
				if command=='Dimm':
					commcode=chr(0x02)
				if command=='Stop':
					commcode=chr(0x02)
				if command=='Bright':
					commcode=chr(0x03)
				if command=='Program':
					commcode=chr(0x03)		
				if command=='Limit':
					commcode=chr(0x04)				
				if command=='ColorPlus':
					commcode=chr(0x04)				
				if command=='AllOff':
					commcode=chr(0x05)
				if command=='ColorMin':
					commcode=chr(0x05)
				if command=='AllOn':
					commcode=chr(0x06)
				if command=='Brightness':
					commcode=chr(0x10)					

				self.plugin.debugLog(u"Turn %s Appliance/Dimmer %s (level %d)." % (dev.deviceTypeId,command,BrightLevel))
				if (dev.deviceTypeId=="ACAppliance") or (dev.deviceTypeId=="ACDimmer") or (dev.deviceTypeId=="HEAppliance") or (dev.deviceTypeId=="HEDimmer"):
					if command=='Brightness':
						commcode=chr(0x02)
					if command=='Bright':
						commcode=chr(0x02)
					if command=='Dimm':
						commcode=chr(0x02)						
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)
					adres4 = int(dev.pluginProps['address'][6:8],16)

					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog("housecode:%s" % dev.pluginProps['unit'])
					housecode = chr(int(dev.pluginProps['unit']))
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device type:%s" % self.ReturnLightType(action, dev))			
					devtype = chr(self.ReturnLightType(action, dev))
					level=int(round(BrightLevel/6.66))
					self.plugin.debugLog("device level:%s" % (level))
					packdata = chr(0x11)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+chr(adres4)+housecode+commcode+chr(level)+chr(0x00)
				elif (dev.deviceTypeId=="LWAppliance") or (dev.deviceTypeId=="LWDimmer") or (dev.deviceTypeId=="EMW100Appliance") or (dev.deviceTypeId=="EMW100Dimmer") or (dev.deviceTypeId=="LivoloDimmer") or (dev.deviceTypeId=="RGBDimmer") or (dev.deviceTypeId=="MDRemote"):
					
					if (command=='Bright'):
						commcode=chr(0x02)
					if (command=='Dimm'):
						commcode=chr(0x03)

					if (dev.deviceTypeId=="LivoloDimmer"):
						if (command=='Off'):
							commcode=chr(0x01)							
						if (command=='On'):
							commcode=chr(0x01)
							
					if (dev.deviceTypeId=="LWDimmer"):	
						if (command=='Bright'):
							commcode=chr(0x10)
						if (command=='Dimm'):
							commcode=chr(0x10)	
					else:
						if (command=='Brightness'):
							if action.actionValue > dev.brightness:
								commcode=chr(0x02)
							else:	
								commcode=chr(0x03)			
							
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)

					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					
					if (dev.deviceTypeId=="MDRemote"):
						housecode = chr(0x00)
					else:	
						housecode = chr(int(dev.pluginProps['unit']))
						self.plugin.debugLog("housecode:%s" % dev.pluginProps['unit'])		
										
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device subtype:%s / Command:%s" % (self.ReturnLightType(action, dev),command))			
					devtype = chr(self.ReturnLightType(action, dev))
					level=int(round(BrightLevel/3.23))
					self.plugin.debugLog("device level:%s" % (level))
					packdata = chr(0x14)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+housecode+commcode+chr(level)+chr(0x70)
				elif (dev.deviceTypeId=="RollerTrol")  or (dev.deviceTypeId=="Brel")  or (dev.deviceTypeId=="A-OK_RF01")  or (dev.deviceTypeId=="A-OK_AC114"):
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)

					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog("housecode:%s" % dev.pluginProps['unit'])
					self.plugin.debugLog(u"address1 and 2 and 3 = %s , %s , %s " % (adres1, adres2, adres3))
					housecode = chr(int(dev.pluginProps['unit']))
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device subtype:%s / Command:%s" % (self.ReturnLightType(action, dev),command))			
					devtype = chr(self.ReturnLightType(action, dev))
					level=int(round(BrightLevel/3.23))
					self.plugin.debugLog("device level:%s" % (level))
					packdata = chr(0x19)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+housecode+commcode+chr(0x00)
					self.logdata(packdata,"PackData:=")
				elif (dev.deviceTypeId=="BlindsT1234"):
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)
					subtype = chr(int(dev.pluginProps['subtype']))
					ignoreDimmer = bool(dev.pluginProps['ignoreDimmer'])
					if ignoreDimmer:
						self.plugin.debugLog(u"ignoreDimmer set within Device.  Turning On/Off with Brightness")
						if BrightLevel>0:
							command = "On"
						elif BrightLevel==0:
							command = "Off"
					## use subtype in device Device will enable wider support
					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog(u"Unit:%s" % dev.pluginProps['unit'])
					self.plugin.debugLog(u"Address1 and 2 and 3 = %s , %s , %s " % (adres1, adres2, adres3))
					self.plugin.debugLog(u"Ignore Dimmer:"+unicode(ignoreDimmer))
					housecode = chr(int(dev.pluginProps['unit']))
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device subtype:%s / Command:%s" % (subtype,command))
					#devtype = chr(self.ReturnLightType(action, dev))
					level=int(round(BrightLevel/3.23))
					self.plugin.debugLog("device level:%s" % (level))
					## update indigo device state - otherwise when action called no state changes
					## presume successful state
					if command == "Off":
						self._addToBatchStatesChange(dev, key=u"onOffState", value=True)
						self._addToBatchStatesChange(dev, key="blindState", value="Open")
					elif command == "On":
						self._addToBatchStatesChange(dev, key=u"onOffState", value=False)
						self._addToBatchStatesChange(dev, key="blindState", value="Closed")
					elif command == "Stop":
						self._addToBatchStatesChange(dev, key=u"onOffState", value=False)
						self._addToBatchStatesChange(dev, key="blindState", value="Partial")
					#self._addToBatchStatesChange(dev, key=u"type", value=subtype)
					self._addToBatchStatesChange(dev, key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
					self._addToBatchStatesChange(dev, key=u"command", value=command)
					packdata = chr(0x19)+subtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+housecode+commcode+chr(0x00)
					self.logdata(packdata,"PackData:=")
				elif (dev.deviceTypeId=="Somfy"):
					if command=='Off':
						commcode=chr(0x0F)
					if command=='On':
						commcode=chr(0x10)
					if command=='Stop':
						commcode=chr(0x00)
					if command=='Program':
						commcode=chr(0x07)	
					if command=='Up':
						commcode=chr(0x01)
					if command=='Down':
						commcode=chr(0x03)							
					if command=='AnglePlus':
						commcode=chr(0x11)
					if command=='AngleMin':
						commcode=chr(0x12)	
						
					if dev.pluginProps['isUS'] == True:
						if command=='Off':
							commcode=chr(0x11)
						if command=='On':
							commcode=chr(0x12)
						if command=='AnglePlus':
							commcode=chr(0x0F)
						if command=='AngleMin':
							commcode=chr(0x10)	
																													
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)
					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog("housecode:%s" % dev.pluginProps['unit'])
					housecode = chr(int(dev.pluginProps['unit']))
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device type:%s" % self.ReturnLightType(action, dev))			
					devtype = chr(self.ReturnLightType(action, dev))
					level=int(round(BrightLevel/3.23))
					self.plugin.debugLog("device level:%s" % (level))
					packdata = chr(0x1A)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+housecode+commcode+chr(0x00)+chr(0x00)+chr(0x00)+chr(0x00)		
				elif (dev.deviceTypeId=="Mertik"):
					if command=='Off':
						commcode=chr(0x00)
					if command=='On':
						commcode=chr(0x01)
					if command=='Up':
						commcode=chr(0x02)
					if command=='Down':
						commcode=chr(0x03)							
					if command=='RunUp':
						commcode=chr(0x04)
					if command=='RunDown':
						commcode=chr(0x05)	
					if command=='Stop':
						commcode=chr(0x06)	

					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)
					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog(u"Commcode %s" % command)
					devtype = chr(0x00)
					if dev.pluginProps['isUS'] == True:
						devtype=chr(0x01)	
					packdata = chr(0x42)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+commcode+chr(0x00)		
				elif (dev.deviceTypeId=="Harrison"):
					if command=='Off':
						commcode=chr(0x00)
					if command=='On':
						commcode=chr(0x01)
					if command=='Stop':
						commcode=chr(0x02)
					if command=='Program':
						commcode=chr(0x03)	
					fulladres = dev.pluginProps['address']+'  '
					housecode = fulladres[0]
					adres = self.RecalcAddress(fulladres[1:3])
					self.plugin.debugLog("housecode:%s" % housecode)
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device type:%s" % self.ReturnLightType(action, dev))			
					devtype = chr(self.ReturnLightType(action, dev))
					packdata = chr(0x18)+devtype+chr(0x07)+housecode+adres+commcode+chr(0x00)	
				elif (dev.deviceTypeId=="BlyssAppliance"):
					if command=='Off':
						commcode=chr(0x01)
					if command=='On':
						commcode=chr(0x00)
					adres1 = int(dev.pluginProps['address'][0:2],16)
					adres2 = int(dev.pluginProps['address'][2:4],16)
					adres3 = int(dev.pluginProps['address'][4:6],16)
					self.plugin.debugLog(u"Address %s" % dev.pluginProps['address'])
					self.plugin.debugLog("unitcode:%s" % dev.pluginProps['unit'])
					housecode = chr(int(dev.pluginProps['unit']))
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device type:%s" % self.ReturnLightType(action, dev))			
					devtype = chr(self.ReturnLightType(action, dev))
					packdata = chr(0x15)+devtype+chr(0x00)+chr(adres1)+chr(adres2)+chr(adres3)+housecode+commcode+chr(0x00)+chr(0x00)+chr(0x00)							
				else:
					if (command=='Brightness'):
						if action.actionValue > dev.brightness:
							commcode=chr(0x03)
						else:	
							commcode=chr(0x02)						
						
					fulladres = dev.pluginProps['address']+'  '
					housecode = fulladres[0]
					adres = self.RecalcAddress(fulladres[1:3])
					self.plugin.debugLog("housecode:%s" % housecode)
					self.plugin.debugLog("device type:%s" % dev.deviceTypeId)
					self.plugin.debugLog("device type:%s" % self.ReturnLightType(action, dev))			
					devtype = chr(self.ReturnLightType(action, dev))
					packdata = chr(0x10)+devtype+chr(0x07)+housecode+adres+commcode+chr(0x00)

				self.sendPacket("send x10 cmd", packdata)
				self.plugin.sleep(1)
				return True
		except Exception, exc:
			self.plugin.errorLog(str(exc))
			return False
	
	def TurnOn(self, action, dev):
		return self.TurnDevice(action, dev, 'On', 0)

	def TurnOff(self, action, dev):
		return self.TurnDevice(action, dev, 'Off', 0)

	def SetBrightLevel(self, action, dev, BrightLevel):
		return self.TurnDevice(action, dev, 'Brightness', BrightLevel)

	def TurnBright(self, action, dev, BrightLevel):
		return self.TurnDevice(action, dev, 'Bright', BrightLevel)

	def TurnStop(self, action, dev):
		return self.TurnDevice(action, dev, 'Stop', 0)
		
	def TurnProgram(self, action, dev):
		return self.TurnDevice(action, dev, 'Program', 0)	
		
	def TurnLimit(self, action, dev):
		return self.TurnDevice(action, dev, 'Limit', 0)		
		
	def TurnUp(self, action, dev):
		return self.TurnDevice(action, dev, 'Up', 0)
		
	def TurnDown(self, action, dev):
		return self.TurnDevice(action, dev, 'Down', 0)		

	def TurnRunUp(self, action, dev):
		return self.TurnDevice(action, dev, 'RunUp', 0)
		
	def TurnRunDown(self, action, dev):
		return self.TurnDevice(action, dev, 'RunDown', 0)		

	def TurnAnglePlus(self, action, dev):
		return self.TurnDevice(action, dev, 'AnglePlus', 0)		
		
	def TurnAngleMin(self, action, dev):
		return self.TurnDevice(action, dev, 'AngleMin', 0)					
		
	def TurnDim(self, action, dev, BrightLevel):
		return self.TurnDevice(action, dev, 'Dimm', BrightLevel)
	
	def TurnAllOn(self, action, dev):
		return self.TurnDevice(action, dev, 'AllOn', 0)

	def TurnAllOff(self, action, dev):
		return self.TurnDevice(action, dev, 'AllOff', 0)

	def ColorPlus(self, action, dev):
		return self.TurnDevice(action, dev, 'ColorPlus', 0)

	def ColorMin(self, action, dev):
		return self.TurnDevice(action, dev, 'ColorMin', 0)

	def readPacket(self):
		try:
			datastr = ''
			if self.port != None:
				data = self.port.read()
				if data is None or len(data) == 0:
					return None

				datalen = ord(data)
				datastr += data 
				rcvdlen = 0
				while rcvdlen < datalen:
					data = self.port.read()
					if data is None or len(data) == 0:
						self.logdata(datastr, "incomplete packet")
						indigo.server.log("incomplete packet received", isError=True)
						self.port = None
						self.configRead = False
						return None		# never return partial packets
					datastr += data 
					rcvdlen += 1
				return datastr
		except:
			indigo.server.log(u"communication error occured", isError=True)
			exc_type, exc_value, exc_traceback = sys.exc_info()		
			self.plugin.debugLog("%s" % traceback.format_exc())
			self.port = None
			self.configRead = False

		return None

	def sendPacket(self, logprefix, packetdata, padtolen=0):
		# Prepend the length byte, and optionally pad with zeros.
		curlen = len(packetdata)
		if padtolen > 0:
			while curlen < padtolen:
				packetdata += chr(0x00)
				curlen += 1
		packdata = chr(curlen) + packetdata
		self.logdata(packdata, logprefix)
		self.port.write(packdata)

	def processPacket(self, data):
		self.logdata(data,"processing")

		if len(data)>1:
			if ord(data[1])==22:
				self.showDoorbell(data)		
			elif ord(data[1])==78:
				self.showBBQ(data)		
			elif ord(data[1])==80:
				self.showTemp(data)
			elif ord(data[1])==81:
				self.showHumidity(data)
			elif ord(data[1])==82:
				self.showTemp(data)
			elif ord(data[1])==84:
				self.showBaro(data)				
			elif ord(data[1])==85:
				self.showRain(data)
			elif ord(data[1])==16:
				self.triggerSwitch(data)
			elif ord(data[1])==17:
				self.triggerACSwitch(data)
			elif ord(data[1])==20:
				self.triggerLWSwitch(data)
			elif ord(data[1])==24:
				self.triggerRollerTrolRemote(data)	
			elif ord(data[1])==25:
				#self.triggerRollerTrolRemote(data)
				self.triggerBlindsRemote(data)
			elif ord(data[1])==32:
				self.handleSecurity(data)
			elif ord(data[1])==48:
				self.triggerPCRemote(data)
			elif ord(data[1])==87:
				self.handleUV(data)		
			elif ord(data[1])==89:
				self.handleCurrent(data)	
			elif ord(data[1])==90:
				self.handleEnergyUsage(data)												
			elif ord(data[1])==112:
				self.handleRFXSensor(data)
			elif ord(data[1])==113:
				self.handleRFXMeter(data)
			elif ord(data[1])==86:
				self.handleWind(data)
			elif ord(data[1])==2:
				self.handleChecksum(data)
			elif ord(data[1])==3:
				self.handleUndecoded(data)
			else:
				self.handleUnknownDeviceType(ord(data[1]))

			self.plugin.debugLog(u"++++++++++++++")	

			self._finalizeStatesChanges()

	def handleUndecoded(self, data):
		if not self.plugin.showUndecodedPackets:
			return

		# subtype=ord(data[2])	
		hexres = ''.join(["%02X " % ord(char) for char in data]).strip()
		self.plugin.errorLog(u"undecoded packet received: %s" % (hexres))

	def handleChecksum(self, data):
		subtype=ord(data[2])	
		chktype=ord(data[4])
		
		if subtype==0:
			errmsg = "error, receiver did not lock msg not used"
		if chktype==0:
			errmsg = "ACK, transmit OK"
		if chktype==1:
			errmsg = "ACK, but transmit started after 3 seconds delay anyway with RF receive data msg"
		if chktype==2:
			errmsg = "NAK, transmitter did not lock on the requested transmit frequency"
		if chktype==3:
			errmsg = "NAK, AC address zero in id1-id4 not allowed"
		self.plugin.debugLog(u"ACK Message %s" % errmsg)

	def handleSecurity(self, data):
		devicetype=ord(data[1])
		subtype=ord(data[2])
		device=""
		status=ord(data[7])
		stattext=""
		if subtype<3:
			sensor = (ord(data[6])*256)+ord(data[4])
		elif subtype==3:
			sensor = (ord(data[5])*256)+ord(data[4])
		else:
			sensor = (ord(data[6])*256*256)+(ord(data[5])*256)+ord(data[4])

		if subtype==0:
			device="X10 security door/window sensor"
		elif subtype==1:
			device="X10 security motion sensor"
		elif subtype==2:
			device="X10 security remote (no alive packets)" 
		elif subtype==3:
			device="KD101 (no alive packets)"
		elif subtype==4:
			device="Visonic PowerCode door/window sensor – primary contact (with alive packets)"
		elif subtype==5:
			device="Visonic PowerCode motion sensor (with alive packets)"
		elif subtype==6:
			device="Visonic CodeSecure (no alive packets)"
		elif subtype==7:
			device="Visonic PowerCode door/window sensor – auxiliary contact (no alive packets)"
		else: 
			device="Undefined"

		if status==0:
			stattext = "X10 normal"
		elif status==1:
			stattext = "X10 normal delayed"
		elif status==2:
			stattext = "X10 alarm"
		elif status==3:
			stattext = "X10 alarm delayed"
		elif status==4:
			stattext = "X10 motion"
		elif status==5:
			stattext = "X10 no motion"
		elif status==6:
			stattext = "X10/KD101 panic"
		elif status==7:
			stattext = "X10 end panic"
		elif status==8:
			stattext = "X10 tamper"
		elif status==9:
			stattext = "X10 arm away"
		elif status==10:
			stattext = "X10 arm away delayed"
		elif status==11:
			stattext = "X10 arm home"
		elif status==12:
			stattext = "X10 arm home delayed"
		elif status==13:
			stattext = "X10 disarm"
		elif status==14:
			stattext = "X10 light 1 off"
		elif status==15:
			stattext = "X10 light 1 on"
		elif status==16:
			stattext = "X10 light 2 off"
		elif status==17:
			stattext = "X10 light 1 on"
		elif status==21:
			stattext = "KD101 pair"
		elif status==80:
			stattext = "X10 normal (tamper)"
		elif status==81:
			stattext = "X10 normal delayed (tamper)"
		elif status==82:
			stattext = "X10 alarm (tamper)"
		elif status==83:
			stattext = "X10 alarm delayed (tamper)"
		elif status==84:
			stattext = "X10 motion (tamper)"
		elif status==85:
			stattext = "X10 no motion (tamper)"
		else:
			stattext = "Undefined"
		
		self.plugin.debugLog(u"Security sensor %d of type %s (%s) has status %s (%s)" % (sensor, subtype, device, status, stattext))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Security sensor %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=int(subtype))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"status", value=int(status))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))		
			if int(status)==2 or int(status)==4 or int(status)==84:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastAlarm", value=time.strftime('%Y/%m/%d %H:%M:%S'))	
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)

 	def triggerACSwitch(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
 		s1=(hex(ord(data[4]))+'0')[2:4]
 		s2=(hex(ord(data[5]))+'0')[2:4]
 		s3=(hex(ord(data[6]))+'0')[2:4]
 		s4=(hex(ord(data[7]))+'0')[2:4]
 		s5=str(100+ord(data[8]))[1:3] 
		commcode=ord(data[9])		
 		self.plugin.debugLog(u"AC Switch with housecode %s%s%s%s and unitcode %s command %d received" % (s1,s2,s3,s4,s5, commcode))		
		if commcode==0:
			commando = "Off"
		elif commcode==1:
			commando = "On"	
		elif commcode==2:
			commando = "Dimm"	
		elif commcode==3:
			commando = "Bright"	
		elif commcode==7:
			commando = "Pressed"		 			
		else:
			commando = "None" 		
		sensor = s1+s2+s3+s4+s5
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s%s%s%s-%s in list, command=%s" % (s1,s2,s3,s4,s5,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s%s%s%s-%s" % (s1,s2,s3,s4,s5))

 	def triggerLWSwitch(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
 		s1=(hex(ord(data[4]))+'0')[2:4]
 		s2=(hex(ord(data[5]))+'0')[2:4]
 		s3=(hex(ord(data[6]))+'0')[2:4]
 		s5=str(100+ord(data[7]))[1:3] 
		commcode=ord(data[8])
		level=ord(data[9])
 		self.plugin.debugLog(u"LW Switch with housecode %s%s%s and unitcode %s command %d received (level:%d)" % (s1,s2,s3,s5, commcode, level))		
		if commcode==0:
			commando = "Off"
		elif commcode==1:
			commando = "On"	
		elif commcode==2:
			commando = "Group off"	
		elif commcode==3:
			commando = "Mood 1"	
		elif commcode==4:
			commando = "Mood 2"
		elif commcode==5:
			commando = "Mood 3"	
		elif commcode==6:
			commando = "Mood 4"	
		elif commcode==7:
			commando = "Mood 5"		 			
		elif commcode==8:
			commando = "Reserved"		
		elif commcode==9:
			commando = "Reserved"		
		elif commcode==10:
			commando = "Unlock"		
		elif commcode==11:
			commando = "Lock"			
		elif commcode==12:
			commando = "All lock"		
		elif commcode==13:
			commando = "Close"
		elif commcode==14:
			commando = "Stop"
		elif commcode==15:
			commando = "Open"
		elif commcode==16:
			commando = "Set level"
		else:
			commando = "None" 		
		sensor = s1+s2+s3+s5
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s%s%s-%s in list, command=%s" % (s1,s2,s3,s5,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s%s%s-%s" % (s1,s2,s3,s5))
			self.plugin.errorLog(u"probably a LW Remote?")
			self.triggerLWRemote(data)


 	def triggerLWRemote(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
 		s1=(hex(ord(data[4]))+'0')[2:4]
 		s2=(hex(ord(data[5]))+'0')[2:4]
 		s3=(hex(ord(data[6]))+'0')[2:4]
 		unit=str(100+ord(data[7]))[1:3] 
		commcode=ord(data[8])
		level=ord(data[9])
 		self.plugin.debugLog(u"LW Remote with housecode %s%s%s command %d received (level:%d)" % (s1,s2,s3, commcode, level))		
		if commcode==0:
			commando = "Off"
		elif commcode==1:
			commando = "On"	
		elif commcode==2:
			commando = "Group off"	
		elif commcode==3:
			commando = "Mood 1"	
		elif commcode==4:
			commando = "Mood 2"
		elif commcode==5:
			commando = "Mood 3"	
		elif commcode==6:
			commando = "Mood 4"	
		elif commcode==7:
			commando = "Mood 5"		 			
		elif commcode==8:
			commando = "Reserved"		
		elif commcode==9:
			commando = "Reserved"		
		elif commcode==10:
			commando = "Unlock"		
		elif commcode==11:
			commando = "Lock"			
		elif commcode==12:
			commando = "All lock"		
		elif commcode==13:
			commando = "Close"
		elif commcode==14:
			commando = "Stop"
		elif commcode==15:
			commando = "Open"
		elif commcode==16:
			commando = "Set level"
		else:
			commando = "None" 		
		sensor = s1+s2+s3
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s%s%s in list, unit=%s, command=%s" % (s1,s2,s3,unit,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"unit", value=unit)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s%s%s" % (s1,s2,s3))

 	def triggerPCRemote(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
 		sensor=(hex(ord(data[4]))+'0')[2:4]
		commcode=ord(data[5])
		toggle=self.getToggleLevel(data[6])
		cmdType = self.getcmdTypeLevel(data[6])
		signalStrength = self.getSignalStrength(data[6])			
		
 		self.plugin.debugLog(u"PCRemote %s with subtype %d command %d received" % (sensor, subtype, commcode))		
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"PCRemote %s in list, command=%d" % (sensor,commcode))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commcode)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"commandtype", value=cmdType)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"subtype", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"toggle", value=toggle)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s" % (sensor))

 	def triggerSwitch(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
		housecode=chr(ord(data[4]))
		adres=ord(data[5])
		sensor = (ord(data[4])*100)+ord(data[5])
		commcode=ord(data[6])
		self.plugin.debugLog(u"Switch Command %s%d command %d received" % (housecode, adres, commcode))
		if commcode==0:
			commando = "Off"
		elif commcode==1:
			commando = "On"	
		elif commcode==2:
			commando = "Dimm"	
		elif commcode==3:
			commando = "Bright"	
		elif commcode==7:
			commando = "Pressed"	 			
		else:
			commando = "None"
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s%d in list, command=%s" % (housecode,adres,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s%d" % (housecode,adres))

 	def triggerRollerTrolRemote(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
		housecode=chr(ord(data[4]))
		adres=ord(data[5])
		sensor = (ord(data[4])*100)+ord(data[5])
		commcode=ord(data[6])	
 		self.plugin.debugLog(u"RollerTrol Remote with housecode %s and unitcode %s command %s received" % (housecode, adres, commcode))		
		if commcode==0:
			commando = "Open"
		elif commcode==1:
			commando = "Close"	
		elif commcode==2:
			commando = "Stop"	
		elif commcode==3:
			commando = "Program"	
		else:
			commando = "None" 		
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s%s in list, command=%s" % (housecode,adres,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s%d" % (housecode,adres))

 	def triggerBlindsRemote(self, data):
		devicetype=ord(data[1])
 		subtype=ord(data[2])
		housecode=(ord(data[4])*10000)+(ord(data[5])*100)+ord(data[6])
		adres=ord(data[7])
		sensor = int((ord(data[4])*1000000)+(ord(data[5])*10000)+(ord(data[6])*100)+ord(data[7]))
		#sensor = int((adres1 * 1000000) + (adres2 * 10000) + (adres3 * 100) + housecode)
		commcode=ord(data[8])
 		self.plugin.debugLog(u"Blinds Remote with id1-3 %s and unitcode %s command %s received" % (housecode, adres, commcode))
		self.plugin.debugLog(u"Blinds Remote with subtype %s and sensor %s received" % (subtype, sensor))
		hexhouse = ''.join(["%02X" % ord(char) for char in data[4:7]]).strip()
		subtype = int(subtype)
		self.plugin.debugLog(u"Enter the below into Device Details:  HouseCode (hex):"+unicode(hexhouse) + u', Subtype (int):'+unicode(subtype)+ u'& UnitCode (int):'+unicode(int(adres)))
		if commcode==0:
			commando = "Open"
		elif commcode==1:
			commando = "Close"
		elif commcode==2:
			commando = "Stop"	
		elif commcode==3:
			commando = "Confirm/Pair"	
		elif commcode==6:
			commando = "Change direction"				
		else:
			commando = "None" 		
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Switch Command %s in list, command=%s" % (sensor,commando))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"command", value=commando)
			if commcode== 0:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"onOffState", value=True)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"blindState", value="Open")
			elif commcode == 1 :
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"onOffState", value=False)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"blindState", value="Closed")
			elif commcode == 2:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"onOffState", value=False)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"blindState", value="Partial")
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,"%s" % (data))

	def showRain(self, data):
		devicetype=ord(data[1])
		subtype=ord(data[2])
		
		rainrate = (ord(data[6]) << 8 ) + ord(data[7])	
		#RAIN1 rate is mm/hr
		#RAIN2 rate is mm * 100 / hr
		#RAIN3 rate is N/A
		if (subtype == 2):
			rainrate = rainrate / 100

		raintotal = (ord(data[8]) << 16 ) + (ord(data[9]) << 8) + ord(data[10])
		rainrate = self.convertRainfallToUnits(rainrate)
		raintotal = self.convertRainfallToUnits(raintotal/10)
		sensor = (ord(data[5]) << 8) + ord(data[4])
		self.plugin.debugLog(u"Rainsensor %d values updated rate:%f total:%f "% (sensor, rainrate, raintotal))
		
		batteryAndSignalData = data[11]
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Rainsensor %d in list" % sensor)
			
			# get existing Rain Total 
			existingRainTotal = self._getCurrentSensorValue(self.devicesCopy[sensor],"raintotal")
			
			# get month & week for current month & week totals
			localProps = self.devicesCopy[sensor].pluginProps
			currentMonthNumber = self.mk_int(localProps.get("currentMonthNumber", 0))
			currentWeekNumber  = self.mk_int(localProps.get("currentWeekNumber", 0))
			#self.plugin.debugLog("current month number = %d, current week number = %d" % (currentMonthNumber, currentWeekNumber))
						
			# get current totals
			currentMonthTotal = self._getCurrentSensorValue(self.devicesCopy[sensor],"currentMonthTotal")
			currentWeekTotal  = self._getCurrentSensorValue(self.devicesCopy[sensor],"currentWeekTotal")
			currentDayTotal   = self._getCurrentSensorValue(self.devicesCopy[sensor],"currentDayTotal")

			last7Day = localProps.get("last7Days", "")
			if (len(last7Day) == 0):
				last7DayArray = array.array('f',[0.0,0.0,0.0,0.0,0.0,0.0,0.0])
			else:
				last7DayArray = last7Day.split(',')
			#self.plugin.debugLog("current month total = %f, current week total = %f, current day total = %f" % (currentMonthTotal, currentWeekTotal, currentDayTotal))
			
			# if first run, set oldRainTotal to current rain total
			if (currentMonthNumber == 0):
				oldRainTotal = raintotal
			else:
				oldRainTotal = existingRainTotal
			
			changeInRainTotal = round(abs(raintotal - oldRainTotal),2)	
			#self.plugin.debugLog("incoming rainTotal = %f, existing rainTotal = %f, outgoing rainTotal = %f" % (raintotal, existingRainTotal, oldRainTotal))
			#self.plugin.debugLog("change in rain total = %f" % (changeInRainTotal))
			
			# calculate new month & week numbers
			now = datetime.datetime.now()
			newMonthNumber = now.month
			newWeekNumber  = now.isocalendar()[1]

			# if in a different month
			needToSavePlugInProps = False

			# is first packet of the day?
			if (self.checkIfNewDay(sensor)):
				self.plugin.debugLog("Entering new day")
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"previousDayTotal", value=currentDayTotal, decimalPlaces = self.plugin.digitsRain)	# copy current to previous
				currentDayTotal = 0 # reset current
				
				#remove oldest total & append 0
				last7DayArray.pop(0)
				last7DayArray.append(0)
			
			# is first packet of the month?
			if (currentMonthNumber != newMonthNumber):
				self.plugin.debugLog("Entering new month = %i" % (newMonthNumber))
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"previousMonthTotal", value=currentMonthTotal, decimalPlaces = self.plugin.digitsRain) # copy current to previous
				currentMonthTotal = 0 # reset current
				localProps["currentMonthNumber"] = newMonthNumber # update current month week number
				needToSavePlugInProps = True
				
			# is first packet of the week?
			if (currentWeekNumber != newWeekNumber):
				self.plugin.debugLog("Entering new week = %i" % (newWeekNumber))
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"previousWeekTotal", value=currentWeekTotal, decimalPlaces = self.plugin.digitsRain)	# copy current to previous
				currentWeekTotal = 0 # reset current
				localProps["currentWeekNumber"] = newWeekNumber	# update current month week number
				needToSavePlugInProps = True

			# add new rain amount
			currentDayTotal += changeInRainTotal
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"currentDayTotal", value=currentDayTotal, decimalPlaces = self.plugin.digitsRain)
			
			#remove most recent total & append new day total
			last7DayArray.pop(-1)
			last7DayArray.append(currentDayTotal)		
			
			# add new rain amount
			currentWeekTotal += changeInRainTotal
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"currentWeekTotal", value=currentWeekTotal, decimalPlaces = self.plugin.digitsRain)
			
			# add new rain amount	
			currentMonthTotal += changeInRainTotal
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"currentMonthTotal", value=currentMonthTotal)			

			#self.plugin.debugLog("new month total = %f, new week total = %f, new day total = %f" % (currentMonthTotal, currentWeekTotal, currentDayTotal))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"rainrate", value=rainrate, decimalPlaces = self.plugin.digitsRain)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"raintotal", value=raintotal, decimalPlaces = self.plugin.digitsRain)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			localProps["last7Days"] = ','.join(map(str,last7DayArray))
			needToSavePlugInProps = True
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "Total":
				display = "%s" % (self.rainToString(raintotal))
			elif displayMode == "RainRate":
				display = "%s" % (self.rainToString(rainrate))
			elif displayMode == "CurrentStatus":
				if (rainrate > 0):
					isRaining = "Yes"
				else:
					isRaining = "No"				
				display = "%s" % (isRaining)
			elif displayMode == "Daily":
				display = "%s" % (self.rainToString(currentDayTotal))
			elif displayMode == "Last7":
				# calculate last7dayTotal
				last7DayTotal = 0
				for eachDay in last7DayArray:
					last7DayTotal += float(eachDay)
				display = "%s" % (self.rainToString(last7DayTotal))
			elif displayMode == "Weekly":
				display = "%s" % (self.rainToString(currentWeekTotal))
			elif displayMode == "Monthly":
				display = "%s" % (self.rainToString(currentMonthTotal))
			elif displayMode == "DailyCurrentPrevious":
				#self._finalizeStatesChanges()
				display = "%s / %s" % (self.rainToString(currentDayTotal), self.rainToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"previousDayTotal")))
			elif displayMode == "WeeklyCurrentPrevious":
				#self._finalizeStatesChanges()
				display = "%s / %s" % (self.rainToString(currentWeekTotal), self.rainToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"previousWeekTotal")))
			elif displayMode == "MonthlyCurrentPrevious":
				#self._finalizeStatesChanges()
				display = "%s / %s" % (self.rainToString(currentMonthTotal), self.rainToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"previousMonthTotal")))
				
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
			if (needToSavePlugInProps or (currentMonthNumber == 0)):
				self.plugin.debugLog("saving plugin props")
				self.devicesCopy[sensor].replacePluginPropsOnServer(localProps)			
				self.devicesCopy[sensor] = indigo.devices[self.devicesCopy[sensor].id]
		else:
			self.handleUnknownDevice(devicetype,sensor)			

	def handleRFXSensor(self,data):
		devicetype = ord(data[1])
		subtype    = ord(data[2])
		sensor     = ord(data[4])
		svalue     = (ord(data[5])*256)+ord(data[6])
		humid      = 0
		temp       = 0

		self.plugin.debugLog(u"RFXSensor %d with subtype %d and value %d" % (sensor,subtype,svalue))
		self.plugin.debugLog(u"Data1: %s %s %s %s %s %s %s %s"% (ord(data[0]),ord(data[1]),ord(data[2]),ord(data[3]),ord(data[4]),ord(data[5]),ord(data[6]),ord(data[7 ])))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"RFXSensor %d in list" % sensor)
			dev = self.devicesCopy[sensor]
			if subtype == 0:
				temp = ord(data[6])
				vFactor = 1
				temp2 = ord(data[5])
				if ord(data[5])>127:
					temp2 = ord(data[5])-128
					vFactor = -1
				temp+=(temp2*256) 
				temp = temp*vFactor*0.01
				
				temp = self.convertTemperatureToUnit(temp)
				self._addToBatchStatesChange(dev, key=u"temperature", value= temp, decimalPlaces= self.plugin.digitsTemperature)
				self._addToBatchStatesChange(dev, key=u"message", value="")

				self.calcMinMax(sensor,"temperature", decimalPlaces=self.plugin.digitsTemperature)

				self._addToBatchStatesChange(dev, key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))

				if (self._getCurrentSensorValue(dev,"temperature")==self._getCurrentSensorValue(dev,"mintemperature")) and (self._getCurrentSensorValue(dev,"temperature")==self._getCurrentSensorValue(dev,"maxtemperature")):
					self._addToBatchStatesChange(dev, key=u"resetDayValue", value=1)
				
			if subtype == 1:
				svalue = (ord(data[5])*256)+ord(data[6])
				temp = float(self.convertTemperatureToC(self._getCurrentSensorValue(dev,"temperature")))
				### do not update indigo; KW april 7. self._addToBatchStatesChange(dev, key=u"temperature", value= temp, decimalPlaces= self.plugin.digitsTemperature)
				self.plugin.debugLog(u"RFXSensor read values: value=%d temperature=%.1f (C)" % (svalue,temp))	
				#svalue = (((svalue / 4.750) - 0.16) / 0.0062) / (1.0546 - 0.00216 * temp)
				svalue = ((svalue/4.75*1) / (1.0305 + (5.5E-6 * temp) - (1.375E-7 * temp * temp)))
				humid  = svalue
				self._addToBatchStatesChange(dev, key=u"humidity", value=round(svalue,2), decimalPlaces= 0)
				self._addToBatchStatesChange(dev, key=u"message", value="")

				self.calcMinMax(sensor,"temperature", decimalPlaces=self.plugin.digitsTemperature)
				self.calcMinMax(sensor,"humidity", decimalPlaces=0)
				
				if self._getCurrentSensorValue(dev,"resetDayValue")==1:
					 # this is doen in calcMinMax
					#self._addToBatchStatesChange(dev, key=u"minhumidity", value=round(svalue,2), decimalPlaces= 0)
					#self._addToBatchStatesChange(dev, key=u"maxhumidity", value=round(svalue,2), decimalPlaces= 0)
					self._addToBatchStatesChange(dev, key=u"resetDayValue", value=0)
				self._addToBatchStatesChange(dev, key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))


			if subtype == 2:
				svalue = (ord(data[5])*256)+ord(data[6])
				self._addToBatchStatesChange(dev, key=u"voltage", value=svalue)
				self._addToBatchStatesChange(dev, key=u"message", value="")

			if subtype == 3:
				svalue = (ord(data[5])*256)+ord(data[6])
				if svalue == 1:
					str = "sensor addresses incremented"
				elif svalue == 2:
					str = "battery low detected"
				elif svalue == 129:
					str = "no 1-wire device connected"
				elif svalue == 130:
					str = "1-Wire ROM CRC error"
				elif svalue == 131:
					str = "1-Wire device connected is not a DS18B20 or DS2438"
				elif svalue == 132:
					str = "no end of read signal received from 1-Wire device"
				elif svalue == 133:
					str = "1-Wire scratchpad CRC error"
				else:
					str = "Message unknown"
				self._addToBatchStatesChange(dev, key=u"message", value=str)
				#self._finalizeStatesChanges()

			if (subtype==0) or (subtype==1):
				self.plugin.debugLog(u"Setting display value to %s, temp=%s" % (dev.pluginProps["displayField"],self._getCurrentSensorValue(dev,"temperature")))	
				display = "--"
				displayMode = dev.pluginProps["displayField"]
				if displayMode == "TempHumid":
					display = u"%s °%s / %d%%" % (self.temperatureToString(temp), self.plugin.unitsTemperature, humid)
				elif displayMode == "Temp":
					display = u"%s °%s" % (self.temperatureToString(temp), self.plugin.unitsTemperature)
				elif displayMode == "TempMinMaxHumid":
					display = u"%s °%s (%s-%s) %d%%" % ( self.temperatureToString(temp), self.plugin.unitsTemperature,  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")),  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")), humid)
				elif displayMode == "TempMinMax":
					display = u"%s °%s (%s-%s)" % ( self.temperatureToString(temp), self.plugin.unitsTemperature, self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")),  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")))

				if "sensorValueType" in self.devicesCopy[sensor].pluginProps:
					if "sensorValueType" in self.devicesCopy[sensor].pluginProps and self.devicesCopy[sensor].pluginProps["sensorValueType"] == "Humid":
						self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=humid, decimalPlaces= 0, uiValue=display)
					else: #Temperature
						self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=temp,  decimalPlaces= self.plugin.digitsTemperature, uiValue=display)
				else: #Temperature
					self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=temp,  decimalPlaces= self.plugin.digitsTemperature, uiValue=display)

			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)

	def handleRFXMeter(self,data):
		devicetype = ord(data[1])
		subtype=ord(data[2])
		sensor = (ord(data[4])*256)+ord(data[5])
		self.plugin.debugLog(u"RFXMeter %d with subtype %d" % (sensor,subtype))
		self.plugin.debugLog(u"Data: %s %s %s %s"% (ord(data[6]),ord(data[7]),ord(data[8]),ord(data[9])))
		
		try:
			cpu = int(self.devicesCopy[sensor].pluginProps['countsPerUnit'])
		except:
			cpu = 1
			self.plugin.errorLog(u"please set the counts per unit (type = %d)" % (devicetype))

		try:
			uDesc = self.devicesCopy[sensor].pluginProps['unitDescription']
		except:
			uDesc = u"None"
			self.plugin.errorLog(u"please set the unit description (type = %d)" % (devicetype))
					
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"RFXMeter %d in list" % sensor)
			if subtype == 0:
				thisValue = (ord(data[6])*256*256*256)+(ord(data[7])*256*256)+(ord(data[8])*256)+ord(data[9])
				if self.checkIfNewDay(sensor):
					self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"startofdaycounter", value=thisValue)

				lastValue = self._getCurrentSensorValue(self.devicesCopy[sensor],"startofdaycounter")
				try:
					dayvalue = float(thisValue-lastValue)/float(cpu)
				except:
					dayvalue = -1

				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"counter", value=thisValue)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"daycounter", value= '%.2f %s' % (dayvalue,uDesc))
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
				#self._finalizeStatesChanges()

			if subtype == 99: #Moet gewoon type 0 zijn, gedisabled door RdK ivm problemen met update van de daycounter, bovenstaande subtype 0 is de oude versie. John testen!
				thisValue = (ord(data[6])*256*256*256)+(ord(data[7])*256*256)+(ord(data[8])*256)+ord(data[9])
				if self.checkIfNewDay(sensor):
					self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"startofdaycounter", value=thisValue)
					#self._finalizeStatesChanges()

				lastValue = self._getCurrentSensorValue(self.devicesCopy[sensor],"startofdaycounter")

				try:
					dayvalue = float(thisValue-lastValue)/float(cpu)
				except:
					dayvalue = -1

				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"counter", value=thisValue)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"daycounter", value= '%.2f %s' % (dayvalue,uDesc))
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
				#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)

	def showTemp(self, data):
		devicetype = ord(data[1])
		subtype=ord(data[2])
		temp = ord(data[7])
		vFactor = 1
		temp2 = ord(data[6])
		if ord(data[6])>127:
			temp2 = ord(data[6])-128
			vFactor = -1

		temp+=(temp2*256) 
		temp = temp*vFactor*0.1
		
		temp  = self.convertTemperatureToUnit(temp)
		humid = 0
		humidityStatus = ""
		batteryAndSignalData = 0
		
		if devicetype==80:
			batteryAndSignalData = data[8]
		elif devicetype==82:
			humid = ord(data[8])
			humidityStatus = self.getHumidityStatus(data[9])
			batteryAndSignalData = data[10]

		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		
		sensor = (ord(data[5])*256)+ord(data[4])
		self.plugin.debugLog(u"Temp sensor %d now %.2f degrees and %d humidity." % (sensor,temp,humid))
				
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Temp sensor %d in list" % sensor)
			
			if 'MultiplyBatteryLevel' in self.devicesCopy[sensor].pluginProps and self.devicesCopy[sensor].pluginProps['MultiplyBatteryLevel']:
				batteryLevel *= 10
				if batteryLevel > 100:
					batteryLevel = 100	

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature",    value = temp,       decimalPlaces= self.plugin.digitsTemperature) 
			if "humidity" in self.devicesCopy[sensor].states:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"humidity",       value=humid,        decimalPlaces= 0)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"humidityStatus", value=humidityStatus)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type",           value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel",   value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			#self._finalizeStatesChanges()

			self.calcMinMax(sensor,"temperature", decimalPlaces=self.plugin.digitsTemperature)
			if "humidity" in self.devicesCopy[sensor].states:
				self.calcMinMax(sensor,"humidity",   decimalPlaces=0)

			#self._finalizeStatesChanges()
			
			display         = "--"
			displayMode     = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "TempHumid":
				display = u"%s °%s / %d%%" % (self.temperatureToString(temp), self.plugin.unitsTemperature, humid)
			elif displayMode == "Temp":
				display = u"%s °%s" % (self.temperatureToString(temp), self.plugin.unitsTemperature)
			elif displayMode == "TempMinMaxHumid":
					display = u"%s °%s (%s-%s) %d%%" % ( self.temperatureToString(temp), self.plugin.unitsTemperature,  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")),  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")), humid)
			elif displayMode == "TempMinMax":
				display = u"%s °%s (%s-%s)" % ( self.temperatureToString(temp), self.plugin.unitsTemperature, self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")),  self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")))

			if "sensorValueType" in self.devicesCopy[sensor].pluginProps["sensorValueType"]:
				if self.devicesCopy[sensor].pluginProps["sensorValueType"] == "Humid":
					self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=humid, decimalPlaces= 0, uiValue=display)
				else: #Temperature
					self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=temp,  decimalPlaces= self.plugin.digitsTemperature, uiValue=display)
			else: #Temperature
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=temp,  decimalPlaces= self.plugin.digitsTemperature, uiValue=display)
				
				
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)
			
	def showDoorbell(self, data):
		devicetype = ord(data[1])
		subtype=ord(data[2])
		sound = ord(data[6])

		batteryAndSignalData = 0
		
		batteryAndSignalData = data[7]

		sensor = (ord(data[4])*256)+ord(data[5])
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)			
		
		self.plugin.debugLog(u"Doorbell %d sound is %.2f." % (sensor,sound))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Doorbell %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"Sound", value=sound)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value="Sound is %.1d" % (sound))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()	
		else:
			self.handleUnknownDevice(devicetype,sensor)

	def showBBQ(self, data):
		devicetype = ord(data[1])
		subtype=ord(data[2])
		temp1 = ord(data[7])
		vFactor = 1
		temp3 = ord(data[6])
		if ord(data[6])>127:
			temp3 = ord(data[6])-128
			vFactor = -1

		temp1+=(temp3*256) 
		temp1 = temp1*vFactor
		temp1 = self.convertTemperatureToUnit(temp1)	
			
		temp2 = ord(data[9])
		vFactor = 1
		temp3 = ord(data[8])
		if ord(data[8])>127:
			temp3 = ord(data[8])-128
			vFactor = -1

		temp2+=(temp3*256) 
		temp2 = temp2*vFactor		
		temp2 = self.convertTemperatureToUnit(temp2)

		batteryAndSignalData = 0
		
		batteryAndSignalData = data[10]

		sensor = (ord(data[4])*256)+ord(data[5])
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)			
		
		self.plugin.debugLog(u"BBQ sensor %d temp1 now %.2f and temp2 now %.2f." % (sensor,temp1,temp2))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"BBQ sensor %d in list" % sensor)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature1", value=temp1, decimalPlaces= self.plugin.digitsTemperature)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature2", value=temp2, decimalPlaces= self.plugin.digitsTemperature)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature1", value=temp1, decimalPlaces= self.plugin.digitsTemperature)

			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "Temp1":
				display = "%s %s" % (self.temperatureToString(temp1), self.plugin.unitsTemperature)
			elif displayMode == "Temp2":
				display = "%s %s" % (self.temperatureToString(temp2), self.plugin.unitsTemperature)
			elif displayMode == "Temp12":
				display = "%s/%s %s" % (self.temperatureToString(temp1),self.temperatureToString(temp2), self.plugin.unitsTemperature)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)

			self.calcMinMax(sensor,"temperature1", decimalPlaces= self.plugin.digitsTemperature)
			self.calcMinMax(sensor,"temperature2", decimalPlaces= self.plugin.digitsTemperature)
			
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()	
		else:
			self.handleUnknownDevice(devicetype,sensor)

	def showBaro(self, data):
		devicetype = ord(data[1])
		subtype=ord(data[2])
		temp = ord(data[7])
		vFactor = 1
		temp2 = ord(data[6])
		if ord(data[6])>127:
			temp2 = ord(data[6])-128
			vFactor = -1

		temp+=(temp2*256) 
		temp = temp*vFactor*0.1
		
		temp = self.convertTemperatureToUnit(temp)
		humid = 0
		humidityStatus = ""
		forecast = ""
		batteryAndSignalData = 0
		
		humid = ord(data[8])
		humidityStatus = self.getHumidityStatus(data[9])

		batteryAndSignalData = data[13]
		
		baro = (ord(data[10])*256)+ord(data[11])
		forecast = self.getForecast(data[12])
		
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)			
		
		sensor = (ord(data[5])*256)+ord(data[4])
		self.plugin.debugLog(u"Temp sensor %d now %.2f degrees and %d humidity." % (sensor,temp,humid))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Temp sensor %d in list" % sensor)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature", value=temp, decimalPlaces= self.plugin.digitsTemperature) 
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"humidity", value=humid)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"barometer", value=baro)			
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"humidityStatus", value=humidityStatus)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"forecast", value=forecast)			

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			#self._finalizeStatesChanges()

			self.calcMinMax(sensor,"temperature", decimalPlaces=self.plugin.digitsTemperature)
			self.calcMinMax(sensor,"humidity", decimalPlaces=0)

			#self._finalizeStatesChanges()
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "TempHumidBaro":
				display = "%s %s / %d%% / %d hPa" % (self.temperatureToString(temp), self.plugin.unitsTemperature, humid, baro)
			elif displayMode == "Temp":
				display = "%s %s" % (self.temperatureToString(temp), self.plugin.unitsTemperature)
			elif displayMode == "Barometer":
				display = "%d hPa" % (baro)		
			elif displayMode == "Forecast":
				display = "%s" % (forecast)							
			elif displayMode == "TempMinMaxHumidBaro":
				display = "%s %s (%s-%s) %d%% / %d hPa" % ( self.temperatureToString(temp), self.plugin.unitsTemperature, self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")), humid, baro )
			elif displayMode == "TempMinMax":
				display = "%s %s (%s-%s)" % ( self.temperatureToString(temp), self.plugin.unitsTemperature, self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")) )

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)


	def handleWind(self, data):
		devicetype = ord(data[1])
		subtype = ord(data[2])
		sensor = (ord(data[5]) << 8) + ord(data[4])

		direction = (ord(data[6]) << 8) + ord(data[7])
		avgSpeed = float(((ord(data[8]) << 8) + ord(data[9]))) / 10
		gust = float(((ord(data[10]) << 8) + ord(data[11]))) / 10
		
		batteryAndSignalData = data[16]
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		
		temp = 0
		chill = 0
		
		#WIND 1-3 Temperature & wind chill not supported
		#WIND 4 Temperature & wind chill are supported
		if (subtype == 4):
			temp = ord(data[13])
			vFactor = 1
			temp2 = ord(data[12])
			if ord(data[12])>127:
				temp2 = ord(data[12])-128
				vFactor = -1

			temp+=(temp2*256) 
			temp = temp*vFactor*0.1
			
			chill = ord(data[15])
			vFactor = 1
			chill2 = ord(data[14])
			if ord(data[14])>127:
				chill2 = ord(data[14])-128
				vFactor = -1

			chill+=(chill2*256) 
			chill = chill*vFactor*0.1

		self.plugin.debugLog(u"Wind sensor %d direction %d avgSpeed %.2f gust %.2f." % (sensor, direction, avgSpeed, gust))
		avgSpeed = self.convertWindspeedToUnits(avgSpeed)
		gust = self.convertWindspeedToUnits(gust)
		self.plugin.debugLog(u"Wind sensor %d direction %d avgSpeed %.2f gust %.2f." % (sensor, direction, avgSpeed, gust))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Wind sensor %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"avgSpeed", value=avgSpeed, decimalPlaces = self.plugin.digitsWind)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"gust", value=gust, decimalPlaces = self.plugin.digitsWind)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"directionDegrees", value=direction)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"directionText", value=self.convertDirectionDegreesToText(direction))
			if (subtype == 4):
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature", value=self.convertTemperatureToUnit(temp), decimalPlaces= self.plugin.digitsTemperature)
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"windChill", value=self.convertTemperatureToUnit(chill), decimalPlaces= self.plugin.digitsTemperature)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "Speed":
				display = "%s %s" % (self.windToString(avgSpeed), self.plugin.unitsWind)
			elif displayMode == "SpeedDirection":
				display = "%s at %s %s" % (self.convertDirectionDegreesToText(direction), self.windToString(avgSpeed), self.plugin.unitsWind)
			elif displayMode == "SpeedCompass":
				display = "%s %s %s" % (self.windToString(avgSpeed), self.plugin.unitsWind, direction)
			elif displayMode == "SpeedGust":
				display = "%s %s (%s %s)" % (self.windToString(avgSpeed), self.plugin.unitsWind, self.windToString(gust), self.plugin.unitsWind)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)			

	def showHumidity(self, data):
		sensorType = ord(data[1])
		subtype=ord(data[2])
		
		humid = 0
		batteryAndSignalData = 0
		
		batteryAndSignalData = data[8]
		humid = ord(data[6])

		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)

		sensor = (ord(data[5])*256)+ord(data[4])+ord(data[1])
		self.plugin.debugLog(u"Humidity sensor %d now %d humidity." % (sensor,humid))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Humidity sensor %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"humidity", value=humid)		
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)
			#self._finalizeStatesChanges()

			self.calcMinMax(sensor,"humidity", decimalPlaces=0)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=u"%d%%" % humid)
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(sensorType,sensor)

	def handleUV(self, data):
		devicetype=ord(data[1])
		subtype=ord(data[2])
		temp = 0
		if subtype==3:
			temp = ord(data[8])
			vFactor = 1
			temp2 = ord(data[7])
			if ord(data[7])>127:
				temp2 = ord(data[7])-128
				vFactor = -1			
			temp+=(temp2*256) 
			temp = temp*vFactor*0.1			
		
		UVLevel = float(ord(data[6])) / 10
		batteryAndSignalData = data[9]
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		
		sensor = (ord(data[5])*256)+ord(data[4])
		temp = self.convertTemperatureToUnit(temp)
		
		self.plugin.debugLog(u"UV sensor %d now %.1f UV and %d degrees." % (sensor,UVLevel,temp))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Temp sensor %d in list" % sensor)
			if subtype==3:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature", value=temp, decimalPlaces= self.plugin.digitsTemperature)
				#self._finalizeStatesChanges()

				self.calcMinMax(sensor,"temperature", decimalPlaces=self.plugin.digitsTemperature)
			else:
				self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"temperature", value="")
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"UVLevel", value=UVLevel, decimalPlaces= 1)		
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)			
			#self._finalizeStatesChanges()

			self.calcMinMax(sensor,"UVLevel", decimalPlaces=1)

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			#self._finalizeStatesChanges()
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "Uv":
				display = "%.1f" % (UVLevel)
			elif displayMode == "UvMax":
				display = "%.1f (%.1f)" % (UVLevel, float(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxUVLevel")))
			if displayMode == "UvTemp":
				display = "%.1f / %d" % (UVLevel, temp)				
			elif displayMode == "UvMaxTemp":
				display = "%.1f (%.1f) / %d" % (UVLevel, float(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxUVLevel")), temp)
			elif displayMode == "UvTempMinMax":
				display = "%.1f / %s (%d - %d)" % (UVLevel, self.temperatureToString(temp), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")))
			elif displayMode == "UvMinMaxTempMinMax":
				display = "%.1f (%s) / %s (%s - %s)" % ( UVLevel, float(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxUVLevel")), self.temperatureToString(temp), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"mintemperature")), self.temperatureToString(self._getCurrentSensorValue(self.devicesCopy[sensor],"maxtemperature")) )
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)

	def handleCurrent(self, data):
		devicetype=ord(data[1])
		subtype=ord(data[2])
		Current1 = float((ord(data[7])*256)+ord(data[8]))/10
		Current2 = float((ord(data[9])*256)+ord(data[10]))/10
		Current3 = float((ord(data[11])*256)+ord(data[12]))/10			
		batteryAndSignalData = data[12]
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		sensor = (ord(data[5])*256)+ord(data[4])
			
		self.plugin.debugLog(u"Current sensor %d now %.1f/%.1f/%.1f" % (sensor,Current1,Current2,Current3))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Current sensor %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"AmpCh1", value= Current1, decimalPlaces= 1)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"AmpCh2", value= Current2, decimalPlaces= 1)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"AmpCh3", value= Current3, decimalPlaces= 1)	

			#self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"type", value=subtype)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel", value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)			
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated", value=time.strftime('%Y/%m/%d %H:%M:%S'))
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "AmpCh1":
				display = "%.1f" % (Current1)
			elif displayMode == "AmpCh2":
				display = "%.1f" % (Current2)
			elif displayMode == "AmpCh3":
				display = "%.1f" % (Current3)				
			elif displayMode == "AllAmps":
				display = "%.1f / %.1f / %.1f " % (Current1,Current2,Current3)				
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)
			
	def handleEnergyUsage(self, data):
		devicetype=ord(data[1])
		subtype=ord(data[2])
		CurrentUsage = float((ord(data[7])*256*256*256)+(ord(data[8])*256*256)+(ord(data[9])*256)+ord(data[10]))
		TotalkWh = float((ord(data[11])*256*256*256*256*256)+(ord(data[12])*256*256*256*256)+(ord(data[13])*256*256*256)+(ord(data[14])*256*256)+(ord(data[15])*256)+ord(data[16]))/223.666
		batteryAndSignalData = data[17]
		batteryLevel = self.getBatteryLevel(batteryAndSignalData)
		signalStrength = self.getSignalStrength(batteryAndSignalData)
		sensor = (ord(data[4])*256)+ord(data[5])
			
		self.plugin.debugLog(u"Energy Usage sensor %d now %.1f(W)/Total %.1f (kWh)/" % (sensor,CurrentUsage,TotalkWh))
		if sensor in self.devicesCopy.keys():
			self.plugin.debugLog(u"Energy Usage sensor %d in list" % sensor)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"Watts",          value=CurrentUsage, decimalPlaces= 1)	
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"kWh",            value=TotalkWh, decimalPlaces= 1)	

			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"batteryLevel",   value=batteryLevel)
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"signalStrength", value=signalStrength)			
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"lastUpdated",    value=time.strftime('%Y/%m/%d %H:%M:%S'))
			
			display = "--"
			displayMode = self.devicesCopy[sensor].pluginProps["displayField"]
			if displayMode == "Watts":
				display = "%.1f" % (CurrentUsage)
			elif displayMode == "kWh":
				display = "%.1f" % (TotalkWh)
			elif displayMode == "CurrentTotal":
				display = "Actual (W) %.1f /Total (kWh) %.1f" % (CurrentUsage,TotalkWh)				
			self._addToBatchStatesChange(self.devicesCopy[sensor], key=u"display", value=display)			
			#self._finalizeStatesChanges()
		else:
			self.handleUnknownDevice(devicetype,sensor)			
			
	########################################
	# helper functions
	#
	
	def mk_int(self, s):
		return int(s) if s else 0

	def handleUnknownDeviceType(self, devicetype):
		if self.plugin.unknownAsError == True:
			self.plugin.errorLog(u"unknown device type detected (type = %d)" % (devicetype))

	def handleUnknownDevice(self, devicetype, sensorid):
		if self.plugin.unknownAsError == True:
			sensorasdata = False   ## change some of unknown devices to sending whole packet to easier show the correct device entry
			if devicetype==22:
				devicetext="Doorbell"			
			elif devicetype==78:		
				devicetext="BBQ sensor"		
			elif devicetype==80:		
				devicetext="Temperature sensor"
			elif devicetype==81: 	
				devicetext="Humidity sensor"
			elif devicetype==82: 	
				devicetext="Temperature sensor (with humidity)"
			elif devicetype==84: 	
				devicetext="Barometer sensor"
			elif devicetype==87: 	
				devicetext="UVMeter"
			elif devicetype==112: 	
				devicetext="RFX Sensor"
			elif devicetype==113: 	
				devicetext="RFX Meter"
			elif devicetype==85: 	
				devicetext="Rain sensor"
			elif devicetype==16: 	
				devicetext="ARC/X10 Switch"
			elif devicetype==17: 	
				devicetext="AC Switch"
			elif devicetype==20: 	
				devicetext="LightWave Switch"
			elif devicetype==24: 	
				devicetext="RollerTrol Remote"			
			elif devicetype==25: 	
				devicetext="BlindsT1234 Device"
				sensorasdata = True
			elif devicetype==32: 	
				devicetext="X10 Security sensor"
			elif devicetype==48: 	
				devicetext="ATI, Medion, PC Remote"				
			elif devicetype==86: 	
				devicetext="Wind meter"
			elif devicetype==89: 	
				devicetext="ELEC1 Current sensor"
			elif devicetype==90: 	
				devicetext="ELEC2 Energy Usage Sensor"									
			if sensorasdata==False:  ## send the whole data packet here for Blinds
				self.plugin.errorLog(u"unknown device detected (id = %s, type = %d). Select a %s from the list of devices" % (sensorid,devicetype,devicetext))
			else:
				subtype = int(ord(sensorid[2]))
				adres = ord(sensorid[7])
				hexhouse = ''.join(["%02X" % ord(char) for char in sensorid[4:7]]).strip()
				self.plugin.errorLog(u"Unknown device detected (type = %d). Select a %s from the list of devices" % (devicetype,devicetext))
				self.plugin.errorLog(u"HouseCode (hex)=" + unicode(hexhouse)+ u' ,subtype (int)=' + unicode(subtype) + u' ,unitCode (int)=' + unicode(int(adres)))
				if subtype == 3:
					self.plugin.errorLog(u"For SubType 3 Blinds, the multichannel remotes and the unitcode may not be correctly received.")
					self.plugin.errorLog(u"Commands can still be transmitted, by entering the correct unit code. ")
					self.plugin.errorLog(u"Created devices may not be correctly updated as distinguishing units is not possible")
	def logdata(self,packdata,debugstr):
		if packdata is None:
			self.plugin.debugLog(u"%s: none" % (debugstr))	
			return

		res = ''.join(["%d " % ord(char) for char in packdata]).strip()
		hexres = ''.join(["%02X " % ord(char) for char in packdata]).strip()
		self.plugin.debugLog(u"%s: %s (%s)" % (debugstr, res, hexres))	

	def inptest(self):
		# sys.argv = "Some Text"
		# import Tkinter, tkFileDialog
		# file = tkFileDialog.askopenfile(title='Choose a file') 
		# self.plugin.debugLog("Gekozen bestand:%s" % file)
		testValue = self.plugin.pluginPrefs.get(u'tstValue', None)
		if testValue is None:
			return
		self.plugin.debugLog(u"Teststring=%s" % testValue)	
		self.processPacket(self.hextranslate(testValue))

	def hextranslate(self,s):
		res = ""
		for i in range(len(s)/2):
			realIdx = i*2
			res = res + chr(int(s[realIdx:realIdx+2],16))
		return res
	
	def calcMinMax(self,sensor,stateName, decimalPlaces=""):
		try:
			minstateName = u"min"+stateName
			maxstateName = u"max"+stateName
			dev = self.devicesCopy[sensor]
			if u"min"+stateName not in dev.states: return 
			lastValue = float(self._getCurrentSensorValue(dev,stateName))
			#lastValue = dev.states[stateName] 
			self.plugin.debugLog(u"UpdateMinMax state %s value %s" % (stateName,lastValue))
			if self.checkIfNewDay(sensor):
				if u"minYesterday"+stateName in dev.states:
					#indigo.server.log(dev.name+" updating  min "+  stateName +"  "+str(self._getCurrentSensorValue(dev,minstateName)) )
					#indigo.server.log(dev.name+" updating  max "+  stateName +"  "+str(self._getCurrentSensorValue(dev,maxstateName)) )
					self._addToBatchStatesChange(dev, key=u"minYesterday"+stateName, value=float(self._getCurrentSensorValue(dev,minstateName)), decimalPlaces=decimalPlaces)
					self._addToBatchStatesChange(dev, key=u"maxYesterday"+stateName, value=float(self._getCurrentSensorValue(dev,maxstateName)), decimalPlaces=decimalPlaces)
				self._addToBatchStatesChange(dev, key=minstateName, value=lastValue, decimalPlaces=decimalPlaces)
				self._addToBatchStatesChange(dev, key=maxstateName, value=lastValue, decimalPlaces=decimalPlaces)
			else:
				if lastValue < float(self._getCurrentSensorValue(dev,minstateName)):
					self._addToBatchStatesChange(dev, key=minstateName, value=lastValue, decimalPlaces=decimalPlaces)
				if lastValue > float(self._getCurrentSensorValue(dev,maxstateName)):
					self._addToBatchStatesChange(dev, key=maxstateName, value=lastValue, decimalPlaces=decimalPlaces)
		except:
			self.plugin.debugLog(u"An error occured while setting the min/max values")
			exc_type, exc_value, exc_traceback = sys.exc_info()		
			self.plugin.debugLog("%s" % traceback.format_exc())

	def checkIfNewDay(self,sensor):
		try:
			lastDateTime = self._getCurrentSensorValue(self.devicesCopy[sensor],u"lastUpdated")
			newdates = time.strftime('%Y/%m/%d %H:%M:%S')
			compTime = 10
			#012345678901234567890
			#2018/03/14 08:14:22

			if (lastDateTime != ""): 
				self.plugin.debugLog(u"check if new day: last date %s, new date %s" % (lastDateTime[0:compTime], newdates[0:compTime]))
				#indigo.server.log(u"check if new day: last date %s, new date %s" % (lastDateTime[0:compTime], newdates[0:compTime])+" !=: "+unicode(lastDateTime[0:compTime]!=newdates[0:compTime]))
				if lastDateTime[0:compTime] != newdates[0:compTime]:
					return True
				else:
					return False
			else:
				#indigo.server.log("lastUpdated empty so must be new day.")
				self.plugin.debugLog("lastUpdated empty so must be new day.")
				return True
		except:
			self.plugin.debugLog(u"An error occured... assumed this is a new day ")	
			exc_type, exc_value, exc_traceback = sys.exc_info()		
			self.plugin.debugLog("%s" % traceback.format_exc())
			#indigo.server.log(u"check if new day:   error %s" % traceback.format_exc() )
			return True

	def getBatteryLevel(self, data):
		return (ord(data) & 15) + 1
		
	def getToggleLevel(self, data):
		return (ord(data) & 1)		

	def getcmdTypeLevel(self, data):
		return ((ord(data) & 14)>>1)		
	
	def getSignalStrength(self, data):
		return (ord(data) >> 4)

	def getHumidityStatus(self, data):
		if ord(data) == 0:
			return "dry"
		elif ord(data) == 1:
			return "comfort"
		elif ord(data) == 2:
			return "normal"
		elif ord(data) == 3:
			return "wet"

	def getForecast(self, data):
		if ord(data) == 0:
			return "no forecast available"
		elif ord(data) == 1:
			return "sunny"
		elif ord(data) == 2:
			return "partly cloudy"
		elif ord(data) == 3:
			return "cloudy"
		elif ord(data) == 4:
			return "rain"			

	def temperatureToString(self, xx):
		if self.plugin.digitsTemperature == "0":
			cstring =  u"%d"
		else:
			cstring = u"%."+str(self.plugin.digitsTemperature)+"f" 
		return cstring % (xx)
			
	def rainToString(self, xx):
		if str(self.plugin.digitsRain) == "0":
			cstring =  u"%d"
		else:
			cstring = u"%."+str(self.plugin.digitsRain)+"f" 
		return cstring % (xx)

	def windToString(self, xx):
		if str(self.plugin.digitsWind) == "0":
			cstring =  u"%d"
		else:
			cstring = u"%."+str(self.plugin.digitsWind)+"f" 
		return cstring % (xx)

	def convertTemperatureToUnit(self, data):
		# Assumes data parameter supplied in Celsius
		
		if self.plugin.unitsTemperature == "F":
			return round((float(data)*1.8) + 32,self.plugin.digitsTemperature)
		else: # unitsTemperature == "C"
			return round(data,self.plugin.digitsTemperature)

	def convertTemperatureToC(self, data):
		if self.plugin.unitsTemperature == "F":
			return round((float(data)-32)/1.8,self.plugin.digitsTemperature)
		else: # unitsTemperature == "C"
			return round(data,self.plugin.digitsTemperature)

	def convertRainfallToUnits(self, data):
		# Assumes data parameter supplied in millimeters
		
		if self.plugin.unitsRain == "in":
			return round(float(data) / 25.4,self.plugin.digitsRain)
		else: #unitsRainfall = "mm"
			return round(data,self.plugin.digitsRain)

	def convertRainfallRateToUnits(self, data):
		# Assumes data parameter supplied in millimeters / hour
		if self.plugin.unitsRain == "in":
			return round(float(data) / 25.4,self.plugin.digitsRain)
		else: #unitsRainfall = "mm"
			return round(data,self.plugin.digitsRain)	

	def convertWindspeedToUnits(self, data):
		# Assumes data parameter supplied in meters / second
		
		# mps
		# mph
		# kmph
		if self.plugin.unitsWind == "kmph":
			return round(float(data) * 3.6,self.plugin.digitsWind)
		elif self.plugin.unitsWind == "mph":
			return round(float(data) * 2.2369,self.plugin.digitsWind)
		elif self.plugin.unitsWind == "knots":
			return round(float(data) * 1.9438,self.plugin.digitsWind)
		else: #unitsWind == "mps"
			return round(data,self.plugin.digitsWind)

	def convertDirectionDegreesToText(self, data):
		#N	348.76	11.25
		#NNE	11.26	33.75
		#NE	33.76	56.25
		#ENE	56.26	78.75
		#E	78.76	101.25
		#ESE	101.26	123.75
		#SE	123.76	146.25
		#SSE	146.26	168.75
		#S	168.76	191.25
		#SSW	191.26	213.75
		#SW	213.76	236.25
		#WSW	236.26	258.75
		#W	258.76	281.25
		#WNW	281.26	303.75
		#NW	303.76	326.25
		#NNW	326.26	348.75

		if ((data >= 348.76) or (data <= 11.25)):
			return "N"
		elif ((data >= 11.26) and (data <= 33.75)):
			return "NNE"
		elif ((data >= 33.76) and (data <= 56.25)):
			return "NE"
		elif ((data >= 56.26) and (data <= 78.75)):
			return "ENE"
		elif ((data >= 78.76) and (data <= 101.25)):
			return "E"
		elif ((data >= 101.26) and (data <= 123.75)):
			return "ESE"
		elif ((data >= 123.76) and (data <= 146.25)):
			return "SE"
		elif ((data >= 146.26) and (data <= 168.75)):
			return "SSE"
		elif ((data >= 168.76) and (data <= 191.25)):
			return "S"	
		elif ((data >= 191.26) and (data <= 213.75)):
			return "SSW"
		elif ((data >= 213.76) and (data <= 236.25)):
			return "SW"
		elif ((data >= 236.26) and (data <= 258.75)):
			return "WSW"
		elif ((data >= 258.76) and (data <= 281.25)):
			return "W"
		elif ((data >= 281.26) and (data <= 303.75)):
			return "WNW"
		elif ((data >= 303.76) and (data <= 326.25)):
			return "NW"
		elif ((data >= 326.26) and (data <= 348.75)):
			return "NNW"					
		return "not yet implemented"

	########################################
	# Concurrent Thread Start / Stop
	#
	def startComm(self):
		self.plugin.debugLog(u"startComm called")
		oldTime = time.time()
		lastlen = 0
		lasttype = 0
		self.pluginState = False
		
		# While Indigo hasn't told us to shutdown
		while self.shutdown == False:
			# Read indigo pluginPrefs into our own variables
			# Keep trying to read until it works. On the very first startup of the plugin the
			# pluginPrefs Dict is not valid right away, we must poll till it is.
			if self.configRead == False:
				if self.getConfiguration(self.plugin.pluginPrefs) == True:
					if self.port != None:
						self.port.close()
						self.port = None

					serialPort = self.plugin.pluginPrefs.get(u'serialPort', '')
					baudRate = int(self.plugin.pluginPrefs.get(u'baudRate', 38400))

					self.port = self.plugin.openSerial(u"RFXCOM serial port", serialPort, baudRate,8,u"N",1,timeout=1, writeTimeout=1)
					if self.port is None:
						indigo.server.log(u"serial port could not be opened", isError=True)
						self.configRead = False
						self.plugin.sleep(10)

					if self.port:
						self.port.flushInput()
						indigo.server.log(u"initializing communication on port %s at speed %d" % (serialPort, baudRate)) 
						self.plugin.debugLog(u"serial port opened")
						self.configRead = self.SendResetAndInit()
						if not self.configRead:
							indigo.server.log(u"initialization failed (retrying in 10 seconds)", isError=True)
							self.port.close()
							self.port = None
							self.plugin.sleep(10)
				else:
					self.plugin.sleep(2.0)
			else:
				self.plugin.sleep(0.5)
				datastr = self.readPacket()
				if datastr:
					self.processPacket(datastr)

		if self.port != None:
			self.port.close()

		self.plugin.debugLog(u"startComm Exit")

	def stopComm(self):
		self.plugin.debugLog(u"stopConcurrentThread called")
		self.shutdown = True

	########################################
	# Device Start / Stop Subs
	def deviceStart(self, dev, force = True):
		if not force: self.plugin.debugLog(u"deviceStart called. Adding device %s, type: %s" % (dev.name,dev.deviceTypeId))

		if self.pluginState == "init":
			dev.stateListOrDisplayStateIdChanged()  # update  from device.xml info if changed

		## always update sensor 
		force = True
		
		needToSavePlugInProps = False
		localProps = dev.pluginProps

		if dev.deviceTypeId == u'Doorbell':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'BBQ':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'Temperature':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
			# Below could be better implemented to avoid the risk of infinite loops (replacePluginPropsOnServer calls deviceStartComm). Believe however that it loops only once as all values are set and defaulted.
			if "MultiplyBatteryLevel" not in localProps:
				self.plugin.debugLog(u'Adding MultiplyBatteryLevel to plugin props')
				localProps['MultiplyBatteryLevel'] = False
				needToSavePlugInProps = True
			if "sensorValueType" not in localProps:
				self.plugin.debugLog(u'Adding sensorValueType to plugin props')
				localProps['sensorValueType'] = 'Temp'
				needToSavePlugInProps = True
			if 'SupportsStatusRequest' not in localProps:
				self.plugin.debugLog(u'Adding SupportsStatusRequest to plugin props')
				localProps['SupportsStatusRequest'] = False
				needToSavePlugInProps = True
			else:
				if localProps['SupportsStatusRequest'] == True:
					localProps['SupportsStatusRequest'] = False
					needToSavePlugInProps = True
			if 'SupportsSensorValue' not in localProps:
				self.plugin.debugLog(u'Adding SupportsSensorValue to plugin props')
				localProps['SupportsSensorValue'] = True
				needToSavePlugInProps = True
			else:
				if localProps['SupportsSensorValue'] == False:
					localProps['SupportsSensorValue'] = True
					needToSavePlugInProps = True
			if 'SupportsOnState' not in localProps:
				self.plugin.debugLog(u'Adding SupportsOnState to plugin props')
				localProps['SupportsOnState'] = False
				needToSavePlugInProps = True
			else:
				if localProps['SupportsOnState'] == False:
					localProps['SupportsOnState'] = False
					needToSavePlugInProps = True
			if 'subModel' not in localProps:
				self.plugin.debugLog(u'Adding subModel to plugin props')
				localProps['subModel'] = 'Temperature'
				needToSavePlugInProps = True
			else:
				if localProps['subModel'] != 'Temperature':
					localProps['subModel'] = 'Temperature'
					needToSavePlugInProps = True
			dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensorOn)
		elif dev.deviceTypeId == u'Humidity':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'Barometer':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'Rainsensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'ARCSwitch':
			adres = dev.pluginProps['address']
			sensor = (ord(adres[0])*100)+int(adres[1:3])
			if not force:
				self.plugin.debugLog(u"Adding ARC Switch (KaKu with wheels) %s (%s)." % (adres,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'RollerTrolRemote':
			adres = dev.pluginProps['address']
			sensor = (ord(adres[0])*100)+int(adres[1:3])
			if not force:
				self.plugin.debugLog(u"Adding RollerTrol Remote %s (%s)." % (adres,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'BlindsRemote':
			adres = dev.pluginProps['address']
			sensor = (ord(adres[0])*100)+int(adres[1:3])
			if not force:
				self.plugin.debugLog(u"Adding Blinds Remote %s (%s)." % (adres,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'BlindsT1234':

			adres = dev.pluginProps['address']
			subtype = chr(int(dev.pluginProps['subtype']))
			unit = dev.pluginProps['unit']
			adres1 = int(dev.pluginProps['address'][0:2], 16)
			adres2 = int(dev.pluginProps['address'][2:4], 16)
			adres3 = int(dev.pluginProps['address'][4:6], 16)
			housecode = int(dev.pluginProps['unit'])
			self.plugin.debugLog(u'address1,2,3,unitcode = %s , %s , %s , %s ' % (adres1, adres2,adres3,housecode))

			sensor = int( (adres1 * 1000000) + (adres2 * 10000) + (adres3 * 100) + housecode )
			#sensor = (ord(adres[0])*100)+int(adres[1:3])
			if not force:
				self.plugin.debugLog(u"Adding Blinds Remote %s (%s)." % (adres,sensor))
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev

		elif dev.deviceTypeId == u'X10Switch':
			adres = dev.pluginProps['address']
			sensor = (ord(adres[0])*100)+int(adres[1:3])
			if not force:
				self.plugin.debugLog(u"Adding X10 Switch %s (%s)." % (adres,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'ACSwitch':
			adres = dev.pluginProps['address']
			unitcode =str(100+int(dev.pluginProps['unit']))[1:3]
			sensor = adres+unitcode
			if not force:
				self.plugin.debugLog(u"Adding AC Switch housecode %s and unitcode %s (%s)." % (adres,unitcode,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'LWSwitch':
			adres = dev.pluginProps['address']
			unitcode =str(100+int(dev.pluginProps['unit']))[1:3]
			sensor = adres+unitcode
			if not force:
				self.plugin.debugLog(u"Adding LightWave Switch housecode %s and unitcode %s (%s)." % (adres,unitcode,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'LWRemote':
			adres = dev.pluginProps['address']
			sensor = adres
			if not force:
				self.plugin.debugLog(u"Adding LightWave Remote housecode %s (%s)." % (adres,sensor))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'PCRemote':
			adres = dev.pluginProps['address']
			sensor = adres
			if not force:
				self.plugin.debugLog(u"Adding PCRemote %s." % (adres))			
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'SecuritySensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'RFXSensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding RFXSensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'RFXMeter':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding RFXMeter %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'UVMeter':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding UV Meter %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'ELEC1CurrentSensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding ELEC1 Current Sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'ELEC2EnergyUsageSensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding ELEC2 Energy Usage Sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev
		elif dev.deviceTypeId == u'WindSensor':
			sensor = int(dev.pluginProps['sensorNumber'])
			if not force:
				self.plugin.debugLog(u"Adding Wind Sensor %s." % sensor)
			else:
				if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
				dev = indigo.devices[dev.id]
			if sensor not in self.devicesCopy.keys():
				self.devicesCopy[sensor] = dev	
				
		if needToSavePlugInProps:
			self.plugin.debugLog(u'Updating plugin props, Sensor %s' % sensor)
			dev.replacePluginPropsOnServer(localProps)		
			self.devicesCopy[sensor] = indigo.devices[dev.id]

	def deviceStop(self, dev):
		try:
			sensor = int(dev.pluginProps['sensorNumber'])
			if sensor in self.devicesCopy:	del self.devicesCopy[sensor]
			if dev.deviceTypeId == u'Temperature':
				dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
			self.plugin.debugLog(u"deviceStop called. Removed device %s." % dev.name)	
		except:
			self.plugin.debugLog(u"deviceStop called. Device %s not found in list." % dev.name)	

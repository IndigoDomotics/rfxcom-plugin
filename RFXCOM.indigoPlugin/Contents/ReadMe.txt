At this moment the following devices are more or less supported:

	<Device type="relay" id="X10Appliance">		&&RFX TX type 0x10, subtype 0x00
		<Name>X10 Appliance
		<Setting>Address
		
	<Device type="relay" id="ARCAppliance">		&&RFX TX type 0x10, subtype 0x01
		<Name>ARC Appliance (KaKu with wheels)
		<Setting>Address
		
	<Device type="dimmer" id="X10Dimmer">		&&RFX TX type 0x10, subtype 0x00
		<Name>X10 Dimmer
		<Setting>Address		

	<Device type="relay" id="ACAppliance">		&&RFX TX type 0x11, subtype 0x00
		<Name>AC Appliance (new KaKu)
		<Setting>Housecode
		<Setting>Unitcode
		
	<Device type="dimmer" id="ACDimmer">		&&RFX TX type 0x11, subtype 0x00
		<Name>AC Dimmer (new KaKu)
		<Setting>Housecode		
		<Setting>Unitcode

	<Device type="relay" id="LWAppliance">		&&RFX TX type 0x11, subtype 0x00
		<Name>Lightwave Appliance
		<Setting>Housecode
		<Setting>Unitcode
		
	<Device type="dimmer" id="LWDimmer">		&&RFX TX type 0x11, subtype 0x00
		<Name>Lightwave Dimmer
		<Setting>Housecode		
		<Setting>Unitcode
		
	<Device type="relay" id="HEAppliance">		&&RFX TX type 0x11, subtype 0x00
		<Name>HomeEasy Appliance
		<Setting>Housecode
		<Setting>Unitcode
		
	<Device type="dimmer" id="HEDimmer">		&&RFX TX type 0x11, subtype 0x00
		<Name>HomeEasy Dimmer
		<Setting>Housecode		
		<Setting>Unitcode		
		
	<Device type="relay" id="EMW100Appliance">		&&RFX TX type 0x11, subtype 0x00
		<Name>EMW100 Appliance
		<Setting>Housecode
		<Setting>Unitcode
		
	<Device type="dimmer" id="EMW100Dimmer">		&&RFX TX type 0x11, subtype 0x00
		<Name>EMW100 Dimmer
		<Setting>Housecode		
		<Setting>Unitcode		

	<Device type="custom" id="Temperature">		&&RFX RX type 0x50 and 0x52
		<Name>Temperature Sensor
		<Setting>Sensor
		<Return value>temperature (DisplayValue)
		<Return value>mintemperature (DisplayValue)
		<Return value>maxtemperature (DisplayValue)
		<Return value>humidity (only type 82 receivers)
		<Return value>minhumidity (only type 82 receivers)
		<Return value>maxhumidity (only type 82 receivers)
		<Return value>type
		<Return value>lastupdated
		<Return value>batterylevel
		<Return value>signalstrength
		
		Subtypes are ignored!
		Type 50 subtypes:
			1 = TEMP1 is THR128/138, THC138
			2 = TEMP2 is THC238/268,THN132,THWR288,THRN122,THN122,AW129/131 0x03 = TEMP3 is THWR800
			4 = TEMP4 is RTHN318	
			5 = TEMP5 is La Crosse TX3, TX4, TX17
		
		Type 52 subtypes:
			1 = TH1 is THGN122/123, THGN132, THGR122/228/238/268 0x02 = TH2 is THGR810
			3 = TH3 is RTGR328
			4 = TH4 is THGR328
			5 = TH5 is WTGR800
			6 = TH6 is THGR918, THGRN228, THGN500 0x07 = TH7 is TFA TS34C

	<Device type="custom" id="Humidity">		&&RFX RX type 0x51
		<Name>Humidity Sensor
		<Setting>Sensor		
		<Return value>humidity (only type 82 receivers)
		<Return value>minhumidity (only type 82 receivers)
		<Return value>maxhumidity (only type 82 receivers)
		<Return value>type
		<Return value>lastupdated
		<Return value>batterylevel
		<Return value>signalstrength

	<Device type="custom" id="UVMeter">		&&RFX RX type 0x57
		<Name>UV Meter
		<Setting>Sensor
		<Return value>UVLevel 
		<Return value>minUVLevel 
		<Return value>maxUVLevel 
		<Return value>temperature (only type xx receivers)
		<Return value>mintemperature (only type xx receivers)
		<Return value>maxtemperature (only type xx receivers)
		<Return value>type
		<Return value>lastupdated
		<Return value>batterylevel
		<Return value>signalstrength

	<Device type="custom" id="RFXSensor">		&&RFX RX type 0x70
		<Name>RFX Sensor
		<Setting>Sensor
		<Return value>temperature (DisplayValue)
		<Return value>mintemperature
		<Return value>maxtemperature
		<Return value>humidity
		<Return value>minhumidity
		<Return value>maxhumidity
		<Return value>voltage
		<Return value>message
		<Return value>lastupdated
		
	<Device type="custom" id="RFXMeter">		&&RFX RX type 0x71
		<Name>RFX Meter
		<Setting>Sensor
		<Setting>countsPerUnit
		<Setting>unitDescription
		<Return value>daycounter (DisplayValue)
		<Return value>counter
		<Return value>startofdaycounter
		<Return value>count1
		<Return value>count2
		<Return value>count3
		<Return value>count4

	<Device type="custom" id="Rainsensor">		&&RFX RX type 0x55
		<Name>Rainsensor
		<setting>Sensor
		<Return value>rainrate (DisplayValue)
		<Return value>raintotal
		<Return value>type
		<Return value>lastupdated
		<Return value>batterylevel
		<Return value>signalstrength
		Subtypes are ignored!
		subtype:
			1 = RAIN1 is RGR126/682/918 
			2 = RAIN2 is PCR800
			3 = RAIN3 is TFA
	
	<Device type="custom" id="Windsensor">		&&RFX RX type 0x56
		<Name>Windsensor
		<setting>Sensor
		<Return value>type
		<Return value>avgSpeed
		<Return value>gust
		<Return value>directionDegrees
		<Return value>directionText
		<Return value>temperature
		<Return value>windChill
		<Return value>lastUpdated
		<Return value>batteryLevel
		<Return value>signalStrength
	
	<Device type="custom" id="AXSwitch">	&&RFX RX type 0x10
		<Name>ARC/X10 Switch
		<setting>Address
		<return value>command (On/Off/Dimm/Bright)
		<return value>type

	<Device type="custom" id="ACSwitch">	&&RFX RX type 0x10
		<Name>AC Switch
		<Setting>Housecode		
		<Setting>Unitcode
		<return value>command (On/Off/Dimm/Bright)
		<return value>type
		
	<Device type="custom" id="SecuritySensor">	&&RFX RX type 0x20
		<Name>Security Sensor
		<setting>Sensor
		<Return value>Type
			0 = "X10 security door/window sensor"
			1 = "X10 security motion sensor"
			2 = "X10 security remote (no alive packets)" 
			3 = "KD101 (no alive packets)"
			4 = "Visonic PowerCode door/window sensor – primary contact (with alive packets)"
			5 = "Visonic PowerCode motion sensor (with alive packets)"
			6 = "Visonic CodeSecure (no alive packets)"
			7 = "Visonic PowerCode door/window sensor – auxiliary contact (no alive packets)"
		<Return value>Status (DisplayValue)	
			0 = "X10 normal"
			1 = "X10 normal delayed"
			2 = "X10 alarm"
			3 = "X10 alarm delayed"
			4 = "X10 motion"
			5 = "X10 no motion"
			6 = "X10/KD101 panic"
			7 = "X10 end panic"
			8 = "X10 tamper"
			9 = "X10 arm away"
			10 = "X10 arm away delayed"
			11 = "X10 arm home"
			12 = "X10 arm home delayed"
			13 = "X10 disarm"
			14 = "X10 light 1 off"
			15 = "X10 light 1 on"
			16 = "X10 light 2 off"
			17 = "X10 light 1 on"
			21 = "KD101 pair"		
		


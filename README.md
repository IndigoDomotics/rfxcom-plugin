RFXCOM Plugin
=============

This plugin interfaces the RFXtrx433 and RFXrec433\* from
[RFXCOM](http://www.rfxcom.com) in Indigo as an transmitter and receiver for a
large number of protocols. See also
[http://rfxcom.com/transceivers.htm](http://rfxcom.com/transceivers.htm ).

#### Changelog

Some updates to Plugin by GlennNZ

#### 2.2.3
Add blindState to BlindsT1234 device - Open/Closed/or Partial 
![](https://github.com/Ghawken/rfxcom-plugin/blob/master/Images/DeviceStatesUpdate.png?raw=true)


Update lastcommand and lastUpdate to include both remote commands, but also Sent commands
Below for Subtype=3 Motorlux Blinds ONLY:
- Add warning message for Blinds subtype=3 may not receive unitcode and will need to be entered for control manually
- Because all unitcodes are sent as 1, any same physical remote devices with different unitcodes/channels will be updated together incorrectly)
- Ideally in this scenario should use a different physical remote for groups of blinds wish to control/be correctly updated in Indigo



#### 2.2.2
Add action Groups Open/Close/Stop/Program/Limit for all BlindsT1234 devices
(obviously all may not work correctly on all devices - but option exists)


#### 2.2.1
August 2020

Add new device type BlindsT1234 for all type=25 Blinds

(should replace A-OK AC114, Brel, and others, these others left alone so can update as wanted)

Adds Support for Dooya Blinds and Remotes  (Receive Remote commands and send commands)
Adds Support for SilentGliss Blinds  (Receive Remote commands and send commands)
Adds Support for Motorlux Subtype=3 Blinds - NB: no unitcodes received, see details in Commit 2.2.3

Correctly shows Housecode, unitcode and subtype for ALL these Blinds Remotes

Correctly updates On/Off state of device if command sent via Indigo, OR if Remote button pressed

Add subtype to device Def (should allow other blinds to be controlled)

Add last Command received to device State, lastupdated and type

### **Preferred Usage:**

1. Install, setup Physical Blind, setup working Remote for Blind.
2. Update RFXCOM Plugin (this Plugin) to latest version on github
3. Turn on support for Blinds T1234 in Config
4. Turn on log unknown sensors as error in Plugin Config

5. Press Remote Button on your Blind Remote

Log Should show an Unknown Device Error Msg: (like below)

`RFXCOM Error unknown device detected (type = 25). Select a BlindsT1234 Device from the list of devices
 RFXCOM Error HouseCode (hex)=293301 ,subtype (int)=6 ,unitCode (int)=145`


![](https://github.com/Ghawken/rfxcom-plugin/blob/master/Images/LogUnknownDevice.png?raw=true)


Create a RFXCOM BlindsT1234 Device Adding these Details  (demo image = not the same details!)

![](https://github.com/Ghawken/rfxcom-plugin/blob/master/Images/blindsT1234Device.png?raw=true)


####Functions:

Turn On and Turn Off - will open or close Blinds (and update Device State)

Blind Remote will likewise open/close blind and the State will be updated in Indigo

Also will show last command/last time remote command received in device states:
(eg. can trigger one blind to control others etc)

![](https://github.com/Ghawken/rfxcom-plugin/blob/master/Images/DeviceStatesUpdate.png?raw=true)




------------------------------------------------------------------

Downloading for use
-------------------

Click the releases link above and download the release you’re interested in.
Once downloaded to your Indigo Server Mac, double-click the .indigoPlugin file
to install.

How to use
----------

Mac OS X Mavericks and above include the required FTDI driver, but previous
versions will require you to install the driver which can be [downloaded from
their website](http://www.indigodomo.com/ftdiurl).

Once you have the driver installed, enable the debug log in the configuration
and open the event log to see which devices are received. Add the devices as
instructed in the event log.

Getting Help
------------

If you have questions, the best place to start is on the [RFXCOM
forum](http://forums.indigodomo.com/viewforum.php?f=28) on our forums.

Plugin ID
---------

Here's the plugin ID in case you need to programmatically restart the plugin:

**Plugin ID**: nl.rjdekok.indigoplugin.RFXCOM

Contributing
------------

If you want to contribute, just clone the repository in your account, make your
changes, and issue a pull request. Make sure that you describe the change you're
making thoroughly - this will help the repository managers accept your request
more quickly.

Terms
-----

Perceptive Automation is hosting this repository and will do minimal management.
Unless a pull request has no description or upon cursory observation has some
obvious issue, pull requests will be accepted without any testing by us. We may
choose to delegate commit privledges to other users at some point in the future.

We (Perceptive Automation) don't guarantee anything about this plugin - that
this plugin works or does what the description above states, so use at your own
risk. Support will continue to be provided by RFXCOM through the [RFXCOM forum]
mentioned above.

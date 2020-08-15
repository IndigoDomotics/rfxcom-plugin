RFXCOM Plugin
=============

This plugin interfaces the RFXtrx433 and RFXrec433\* from
[RFXCOM](http://www.rfxcom.com) in Indigo as an transmitter and receiver for a
large number of protocols. See also
[http://rfxcom.com/transceivers.htm](http://rfxcom.com/transceivers.htm ).

#### Changelog

Some updates to Plugin by GlennNZ

2.2.1

Add new device type BlindsT1234 for all type=25 Blinds

(replacing A-OK AC114, Brel, and others, these others left alone so can update as wanted)

Adds Support for Dooya Blinds and Remotes

Correctly shows Housecode, unitcode and subtype for ALL these Blinds Remotes

Correctly updates On/Off state of device if command sent via Indigo, OR if Remote button pressed

Add subtype to device Def (should allow other blinds to be controlled)

Add last Command received to device State, lastupdated and type

##### **Preferred Usage:**

1. Install, setup Physical Blind, setup working Remote for Blind.
2. Update RFXCOM Plugin (this Plugin) to latest version on github
3. Turn on support for Blinds T1234 in Config
4. Turn on log unknown sensors as error in Plugin Config

5. Press Remote Button on your Blind Remote

Log Should an Unknown Device Error Msg: (like below)
 RFXCOM Error                    unknown device detected (type = 25). Select a BlindsT1234 Device from the list of devices
 RFXCOM Error                    HouseCode (hex)=293301 ,subtype (int)=6 ,unitCode (int)=145

![](https://github.com/Ghawken/rfxcom-plugin/blob/master/RFXCOM-Plugin-Glenn.indigoPlugin/Contents/Resources/AlarmSensors.png?raw=true)



Create a RFXCOM BlindsT1234 Device Adding these Details



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

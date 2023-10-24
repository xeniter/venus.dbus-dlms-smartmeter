# dbus-dlms-smartmeter Service

### Purpose

This service is meant to be run on a raspberry Pi with Venus OS from Victron.

The Python script cyclically reads data from a DLMS SmartMeter and publishes information on the dbus, using the service name com.victronenergy.grid. This makes the Venus OS work as if you had a physical Victron Grid Meter installed.

### Credit

Special thanks goes to the following for the basis of this modified code:

- [https://github.com/RalfZim/venus.dbus-fronius-smartmeter](https://github.com/RalfZim/venus.dbus-fronius-smartmeter)
- [https://github.com/victronenergy/velib_python](https://github.com/victronenergy/velib_python)
- [https://github.com/SirUli/FroniusSmartmeter] (https://github.com/SirUli/FroniusSmartmeter)
- [https://github.com/ayasystems/dbus-fronius-smart-meter/tree/main] (https://github.com/ayasystems/dbus-fronius-smart-meter/tree/main)
- [https://github.com/xeniter/eww_ewerk_wels_smartmeter_readout] (https://github.com/xeniter/eww_ewerk_wels_smartmeter_readout)

### Configuration

In the Python file, you should put the IP of your DLMS/ESP8266 device that hosts the DLMS readout. In my setup, it is the IP of the ESP8266, which gets the data from the Siemens IM250 Smart Meter via the DLMS connection between them. (see https://github.com/xeniter/eww_ewerk_wels_smartmeter_readout)

### Installation

0. Install required python packages

   - `opkg update`
   - `opkg install python3-pip`
   - `pip3 install gurux-dlms`

1. Copy the files to the /data folder on your venus:

   - /data/dbus-dlms-smartmeter/dbus-dlms-smartmeter.py
   - /data/dbus-dlms-smartmeter/kill_me.sh
   - /data/dbus-dlms-smartmeter/service/run

2. Set permissions for files:

   `chmod 755 /data/dbus-dlms-smartmeter/service/run`

   `chmod 744 /data/dbus-dlms-smartmeter/kill_me.sh`

3. Get two files from the [velib_python](https://github.com/victronenergy/velib_python) and install them on your venus:

   - /data/dbus-dlms-smartmeter/vedbus.py
   - /data/dbus-dlms-smartmeter/ve_utils.py

4. Add a symlink to the file /data/rc.local:

   `ln -s /data/dbus-dlms-smartmeter/service /service/dbus-dlms-smartmeter`

   Or if that file does not exist yet, store the file rc.local from this service on your Raspberry Pi as /data/rc.local .
   You can then create the symlink by just running rc.local:
  
   `rc.local`

   The daemon-tools should automatically start this service within seconds.

### Debugging

You can check the status of the service with svstat:

`svstat /service/dbus-dlms-smartmeter`

It will show something like this:

`/service/dbus-dlms-smartmeter: up (pid 10078) 325 seconds`

If the number of seconds is always 0 or 1 or any other small number, it means that the service crashes and gets restarted all the time.

When you think that the script crashes, start it directly from the command line:

`python /data/dbus-dlms-smartmeter/dbus-dlms-smartmeter.py`

and see if it throws any error messages.

If the script stops with the message

`dbus.exceptions.NameExistsException: Bus name already exists: com.victronenergy.grid"`

it means that the service is still running or another service is using that bus name.

Stop service

`svc -d /service/dbus-dlms-smart-meter`

Start service

`svc -u /service/dbus-dlms-smart-meter`

Reload data

`/data/dbus-dlms-smart-meter/restart.sh`

View log file

`cat /data/dbus-dlms-smart-meter/current.log`

#### Restart the script

If you want to restart the script, for example after changing it, just run the following command:

`/data/dbus-dlms-smartmeter/kill_me.sh`

The daemon-tools will restart the scriptwithin a few seconds.

### Hardware

In my installation at home, I am using the following Hardware:

- Siemens IM350 Smartemter with DLMS from EWW (https://www.eww.at), data gets readout from ESP, see https://github.com/xeniter/eww_ewerk_wels_smartmeter_readout


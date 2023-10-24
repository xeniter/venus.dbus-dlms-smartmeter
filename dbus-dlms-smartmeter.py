#!/usr/bin/env python

"""
Created by Ralf Zimmermann (mail@ralfzimmermann.de) in 2020.
Adjusted and modified for DLMS readout by Manuel Dipolt (manuel@linux-home.at) in 2023
Original code and its documentation can be found on: https://github.com/RalfZim/venus.dbus-fronius-smartmeter
New DLMS code and its documentation can be found on: https://github.com/xeniter/venus.dbus-dlms-smartmeter
Used https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py as basis for this service.
Using a esp8266 to get DLMS data from a Siemens IM360 smartmeter provided by EWW (https://www.eww.at) https://github.com/xeniter/eww_ewerk_wels_smartmeter_readout
Reading information from a DLMS Smart Meter puts the info on dbus.
"""
from gi.repository import GLib as gobject # Python 3.x
import platform
import logging
import sys
import os
import socket
import configparser # for config/ini file
import binascii
import re
import xml.etree.ElementTree as ET

import _thread as thread   # for daemon = True  / Python 3.x

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))
from vedbus import VeDbusService

# smartmeter
# https://pypi.org/project/gurux-dlms/
# opkg update
# opkg install python3-pip
# pip3 install gurux-dlms
from gurux_dlms import *


path_UpdateIndex = '/UpdateIndex'

class DbusDummyService:
  def __init__(self, servicename, deviceinstance, paths, productname='DLMS Smart Meter', connection='DLMS Smart Meter service'):
    self._dbusservice = VeDbusService(servicename)
    self._paths = paths

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

    # CONFIG readout
    self._config = configparser.ConfigParser()
    self._config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

    logging.info(f"DLMS config:")
    logging.info(f"IP: {self._config['DLMS']['IP']}")
    logging.info(f"Port: {self._config['DLMS']['PORT']}")
    logging.info(f"AES KEY: {self._config['DLMS']['AES_KEY']}")
    logging.info(f"intervalMs: {self._config['DLMS']['intervalMs']}")    

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 16) # value used in ac_sensor_bridge.cpp of dbus-cgwacs
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)

    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

    gobject.timeout_add(int(self._config['DLMS']['intervalMs']), self._update)

  def _update(self):
    try:      
      
      logging.debug("_update called")

      readout=b''
      data=b''

      # Create a TCP/IP socket
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server_address = (self._config['DLMS']['IP'], int(self._config['DLMS']['PORT']))
      sock.connect(server_address)

      while True:
          readout = sock.recv(1024)                                
          data += readout
          if readout == b'':
              break

      sock.close()     

      logging.debug(len(data))
      data = binascii.hexlify(data)
      data = data.decode('utf-8')
      logging.debug(data)


      xml = ""           
      decrypt = GXDLMSTranslator(TranslatorOutputType.SIMPLE_XML)
      decrypt.comments = True
      decrypt.security = enums.Security.ENCRYPTION
      decrypt.blockCipherKey = GXByteBuffer.hexToBytes(self._config['DLMS']['AES_KEY'])

      xml = decrypt.messageToXml(GXByteBuffer.hexToBytes(data))
      # remove comments in lines to be able to extract multi lines comment next
      xml = re.sub("<!--.*?-->", "", xml)


      # (?s) interpret whole string as one line for regex
      # https://www.regular-expressions.info/refmodifiers.html
      commented_xml = re.findall("(?s)<!--.*?-->", xml)

      # get rid of first and last line
      decrypted_xml = '\n'.join(commented_xml[1].split('\n')[1:-1])            

      tree = ET.ElementTree(ET.fromstring(decrypted_xml))
          
      values = []
      for elem in tree.iter('UInt32'):
          values.append(int(elem.attrib['Value'], 16))
      
      SMARTMETER_WIRK_IMPORT=values[0]
      SMARTMETER_WIRK_EXPORT=values[1]
      SMARTMETER_BLIND_IMPORT=values[2]
      SMARTMETER_BLIND_EXPORT=values[3]
      SMARTMETER_CURRENT_WIRK_IMPORT=values[4]
      SMARTMETER_CURRENT_WIRK_EXPORT=values[5]

      meter_consumption = 0
      
      if SMARTMETER_CURRENT_WIRK_IMPORT > 0:
        meter_consumption = SMARTMETER_CURRENT_WIRK_IMPORT
      
      if SMARTMETER_CURRENT_WIRK_EXPORT > 0:
        meter_consumption = -SMARTMETER_CURRENT_WIRK_EXPORT
        
        
      self._dbusservice['/Ac/Power'] = meter_consumption # positive: consumption, negative: feed into grid
      self._dbusservice['/Ac/L1/Voltage'] = 0
      self._dbusservice['/Ac/L2/Voltage'] = 0
      self._dbusservice['/Ac/L3/Voltage'] = 0
      self._dbusservice['/Ac/L1/Current'] = 0
      self._dbusservice['/Ac/L2/Current'] = 0
      self._dbusservice['/Ac/L3/Current'] = 0
      self._dbusservice['/Ac/L1/Power'] = 0
      self._dbusservice['/Ac/L2/Power'] =  0
      self._dbusservice['/Ac/L3/Power'] = 0
      self._dbusservice['/Ac/Energy/Forward'] = 0 # TODO
      self._dbusservice['/Ac/Energy/Reverse'] = 0 # TODO
      
      logging.info("House Consumption: {:.0f}".format(meter_consumption))
    except Exception as e:
      logging.error(e)
      logging.warning("Could not read from DLMS data from the esp8266!")
      self._dbusservice['/Ac/Power'] = 0  # TODO: any better idea to signal an issue?
      
    # increment UpdateIndex - to show that new data is available
    index = self._dbusservice[path_UpdateIndex] + 1  # increment index
    if index > 255:   # maximum value of the index
      index = 0       # overflow from 255 to 0
    self._dbusservice[path_UpdateIndex] = index

    logging.debug("_update done")

    return True

  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change

def main():
  #configure logging
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.DEBUG,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])

  thread.daemon = True # allow the program to quit

  logging.info("started...")

  from dbus.mainloop.glib import DBusGMainLoop
  # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
  DBusGMainLoop(set_as_default=True)

  pvac_output = DbusDummyService(
    servicename='com.victronenergy.grid.mymeter',
    deviceinstance=0,
    paths={
      '/Ac/Power': {'initial': 0},
      '/Ac/L1/Voltage': {'initial': 0},
      '/Ac/L2/Voltage': {'initial': 0},
      '/Ac/L3/Voltage': {'initial': 0},
      '/Ac/L1/Current': {'initial': 0},
      '/Ac/L2/Current': {'initial': 0},
      '/Ac/L3/Current': {'initial': 0},
      '/Ac/L1/Power': {'initial': 0},
      '/Ac/L2/Power': {'initial': 0},
      '/Ac/L3/Power': {'initial': 0},
      '/Ac/Energy/Forward': {'initial': 0}, # energy bought from the grid
      '/Ac/Energy/Reverse': {'initial': 0}, # energy sold to the grid
      path_UpdateIndex: {'initial': 0},
    })

  logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
  mainloop = gobject.MainLoop()
  mainloop.run()

if __name__ == "__main__":
  main()

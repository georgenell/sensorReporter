"""
   Copyright 2018 George Nell

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

 Script: MCP9804Sensor.py
 Author: George Nell
 Date:   June 27, 2021
 Purpose: Checks the state of the i2c sensor and publishes any changes to temperature


"""

from smbus import SMBus
import time
import ConfigParser

class MCP9804Sensor(object):
    """Represents an MCP9820 i2c sensor connected to a GPIO pin"""

    def __init__(self, connections, logger, params, sensors, actuators):
        """Sets the sensor pin to pud and publishes its current value"""

        self.lastpoll = time.time()

        #Initialise to some time ago (make sure it publishes)
        self.lastPublish = time.time() - 1000

        self.logger = logger
        self.sensorMode = params("Mode")

        # Note the int(xx, 16) here as this is Hex (base 16) in the Config
        self.addr = int(params("Address"), 16)  # 0x1f
        self.bus  = SMBus(int(params("Bus")))   # 1

        self.precisionTemp = int(params("PrecisionTemp"))
        self.useF = False

        try:
            if (params("Scale") == 'F'):
                self.useF = True
        except ConfigParser.NoOptionError:
            pass

        #Use 1 reading as default
        self.ARRAY_SIZE = 1

        if (self.sensorMode == "Advanced"):
            #Array size of last readings
            self.ARRAY_SIZE = 5

        #Initialize Array
        self.arrTemperature = [None] * self.ARRAY_SIZE

        self.temperature = None

        self.forcePublishInterval = 60

        self.destination = params("Destination")
        self.poll = float(params("Poll"))

        self.publish = connections

        self.logger.info("----------Configuring MCP9804 Sensor: bus='{0}' address='{1}' poll='{2}' destination='{3}' Initial values: Temp='{4}'".format(self.bus, self.addr, self.poll, self.destination, self.temperature))

        self.publishState()

    def wakeup(self):
		try:
			self.bus.write_word_data(self.addr, 1, 0x0000)
		except:
			self.logger.warn("Wakeup failed..")
	
    def shutdown(self):
		try:
			self.bus.write_word_data(self.addr, 1, 0x0001)
		except:
			self.logger.warn("Shutdown failed..")
	
    def convertTemp(self, value):
        return value if self.useF == False else value * 9 / 5.0 + 32


    def checkState(self):
        """Detects and publishes any state change"""

        hasChanged = False
        valueTemp = self.readSensor(True)

        if (valueTemp is None):
            self.logger.warn("Last reading isn't valid. preserving old reading T='{0}'".format(self.temperature))
            return

        #Verify reading of temperature
        if(valueTemp != self.temperature):
            self.temperature = valueTemp
            hasChanged = True

        if (hasChanged or (time.time() - self.lastPublish)>self.forcePublishInterval):
            self.publishState()


    def publishStateImpl(self, data, destination):
        for conn in self.publish:
            conn.publish(data, destination)


    def publishState(self):
        """Publishes the current state"""
        didPublish = False

        if (self.temperature is not None):
            didPublish = True
            strTemp = str(round(self.temperature, self.precisionTemp))
            self.logger.debug("Publish temperature '{0}' to '{1}'".format(strTemp, self.destination + "/temperature"))
            self.publishStateImpl(strTemp, self.destination + "/temperature")

        if (didPublish):
            self.lastPublish = time.time()


    def isReadingValid(self, value, acceptableMin, acceptableMax):
        if (value is None):
            return False

        if ((value >= acceptableMin) and (value <= acceptableMax)):
            return True

        return False


    def readSensor(self, shutdown=True):

        resultTemp = None
        valueTemp = float(-99)
        try:
            if shutdown:
                self.wakeup()
                time.sleep(0.36)

            msb, lsb =  self.bus.read_i2c_block_data(self.addr, 5, 2)

            if shutdown:
                self.shutdown()
            
            tcrit = msb>>7&1
            tupper = msb>>6&1
            tlower = msb>>5&1
            
            temperature = (msb&0xf)*16+lsb/16.0
            
            if msb>>4&1:
                temperature = 256 - temperature
            
            valueTemp = float(temperature)
        
        except IOError as ex:
            self.logger.debug("ERROR - {0} - {1}".format(ex.errno, ex.strerror))
        finally:
            if shutdown:
                try:
                    self.shutdown()
                except Exception as e:
                    self.logger.debug("ERROR - {0} {1}".format(e.errno, e.strerror))

        #print("Raw reading T:{0}".format(valueTemp ))

        # Is temperature reading valid?
        if (self.isReadingValid(valueTemp, -40.0, 125.0)):
            valueTemp = self.convertTemp(valueTemp);
            self.arrTemperature.append(round(valueTemp, 2))
        else:
            #Reading out of bounds
            return resultTemp

        if (len(self.arrTemperature)>self.ARRAY_SIZE):
            del self.arrTemperature[0]

        if (self.sensorMode == "Advanced"):
            sumTemp = sum(filter(None, self.arrTemperature))
            noTempReadings = len(filter(None, self.arrTemperature))

            if (noTempReadings > 0):
                resultTemp = float(str(round(sumTemp/noTempReadings, self.precisionTemp)))

            #print("readValueAdvanced: Result - Temp:'{0}'".format(resultTemp))
            self.logger.info("readValue: Temp:'{0}'".format(resultTemp))

        #Simple mode -> Just return last reading
        else:
            resultTemp = float(str(round(valueTemp, self.precissionTemp)))

            self.logger.info("readValue: Temp:'{0}'".format(resultTemp))

            #print("readValueSimple: Result - Temp:'{0}'".format(resultTemp))

        return resultTemp

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

 Script: DS18B20Sensor.py
 Author: George Nell
 Date:   October 11, 2018
 Purpose: Checks the state of the 1-wire sensor and publishes any changes to temperature


"""

import sys
import time
import ConfigParser

class DS18B20Sensor(object):
    """Represents a DS18B20 1-wire sensor connected to a GPIO pin"""

    def __init__(self, connections, logger, params, sensors, actuators):
        """Sets the sensor pin to pud and publishes its current value"""

        self.lastpoll = time.time()

        #Initialise to some time ago (make sure it publishes)
        self.lastPublish = time.time() - 1000

        self.logger = logger
        self.sensorMode = params("Mode")

        self.addr = params("Address")

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
            self.ARRAY_SIZE = 7

        #Initialize Array
        self.arrTemperature = [None] * self.ARRAY_SIZE

        self.temperature = None

        self.forcePublishInterval = 60

        self.destination = params("Destination")
        self.poll = float(params("Poll"))
        
        self.preserveDestination = True if params("PreserveDestination").lower() == 'true' else False
        if not self.preserveDestination:
            self.destination = self.destination + "/temperature"

        self.publish = connections

        self.logger.info("----------Configuring DS18B20 Sensor: address='{0}' poll='{1}' destination='{2}' Initial values: Temp='{3}'".format(self.addr, self.poll, self.destination, self.temperature))

        self.publishState()


    def convertTemp(self, value):
        return value if self.useF == False else value * 9 / 5.0 + 32

    # Calculates the Median from a list of numbers.
    # If the list length is odd, return the middle value
    # Or for even length lists, it returns the average of the two middle values
    def getMedian(self, l):
        half = len(l) // 2
	l.sort()
        if not len(l) % 2:
            return (l[half - 1] + l[half]) / 2.0
        return l[half]


    def checkState(self):
        """Detects and publishes any state change"""

        hasChanged = False
        valueTemp = self.readSensor()

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
            self.logger.debug("Publish temperature '{0}' to '{1}'".format(strTemp, self.destination))
            self.publishStateImpl(strTemp, self.destination)

        if (didPublish):
            self.lastPublish = time.time()


    def isReadingValid(self, value, acceptableMin, acceptableMax):
        if (value is None):
            return False

        if ((value >= acceptableMin) and (value <= acceptableMax)):
            return True

        return False


    def readSensor(self):

        resultTemp = None

        valueTemp = float(-99)
	try:
            mytemp = ''
            f = open('/sys/bus/w1/devices/' + self.addr + '/w1_slave', 'r')
            line = f.readline() # read 1st line
            lineOne = line
            crc = line.rsplit(' ',1)
            crc = crc[1].replace('\n', '')
            if crc=='YES':
                line = f.readline() # read 2nd line
                lineTwo = line
                mytemp = line.rsplit('t=',1)
            else:
                mytemp = -99000
            f.close()
            valueTemp = float(mytemp[1])
            valueTemp = valueTemp/1000

	except IOError, ex:
            self.logger.debug("ERROR - {0} - {1}".format(ex.errno, ex.strerror))

        #self.logger.debug("Raw reading T:{0}".format(valueTemp ))

        # Is temperature reading valid? 85c indicates a failure
        if (self.isReadingValid(valueTemp, -40.0, 84.0)):
            valueTemp = self.convertTemp(valueTemp);
            self.arrTemperature.append(round(valueTemp, self.precisionTemp))
        else:
            #Reading out of bounds
            return resultTemp

        if (len(self.arrTemperature)>self.ARRAY_SIZE):
            del self.arrTemperature[0]

        if (self.sensorMode == "Advanced"):
            #sumTemp = sum(filter(None, self.arrTemperature))
            noTempReadings = len(filter(None, self.arrTemperature))
            if (noTempReadings > 0):
                #resultTemp = float(str(round(sumTemp/noTempReadings, self.precisionTemp)))
                resultTemp = self.getMedian(filter(None, self.arrTemperature))

            self.logger.info("readValue: Temp:'{0}'".format(resultTemp))

        #Simple mode -> Just return last reading
        else:
            resultTemp = float(str(round(valueTemp, self.precissionTemp)))
            self.logger.info("readValue: Temp:'{0}'".format(resultTemp))

        return resultTemp

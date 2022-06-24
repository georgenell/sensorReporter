# Copyright 2022 George Nell
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Checks the state of the 1-wire sensor and publishes any changes to 
temperature
"""
from configparser import NoOptionError
from core.sensor import Sensor
from distutils.util import strtobool

class DS18B20Sensor(Sensor):
    """A polling sensor that reads and reports temperature from a 1-wire
    DS18B20 sensor. It requires a poll > 0.
    Parameters:
        "Address": 1-wire address where the data of the sensor may
        be read, such as: 28-000004828fb3 
        "TempDest": destination for the temp reading
        "TempUnit": optional, one of "C" or "F", units the temp is published,
        defaults to "C"
        "Smoothing": optional parameter, when True it will publish the average
        of the last five readings instead of just the current reading.

    Raises:
        NoOptionError when a required options is not present.
        ValueError when a parameter has an unsupported value.
    """

    def __init__(self, publishers, params):
        """Initialise the DS18B20 sensor and collect the first reading.
        Parameters:
            - Poll: must be > 0
            - Address: 1-wire address where the data of the sensor may
            be read, such as: 28-000004828fb3 
            - TempDest: destination for the temperature readings
            - TempUnit: optional parameter, one of "C" or "F", defaults to "C"
            - Smoothing: optional parameter, if True the average of the last
            five readings is published, when False only the most recent is
            published.
        Raises
            - NoOptionError: if a required parameter is not present
            - ValueError: if a parameter has an unsuable value
            - RuntimeError: if there is a problem connecting to the sensor
        """
        super().__init__(publishers, params)

        if self.poll <= 0:
            raise ValueError("A positive polling period is required: {}"
                             .format(self.poll))

        self.addr = params("Address")
        
        self.log.info("Sensor created, setting parameters.")
        self.temp_dest = params("TempDest")

        # Default to C. If it's defined and not C or F raises ValueError.
        try:
            self.temp_unit = params("TempUnit")
            if self.temp_unit not in ("C", "F"):
                raise ValueError("{} is an unsupported temp unit".format(self.temp_unit))
        except NoOptionError:
            self.temp_unit = "C"

        try:
            self.smoothing = bool(strtobool(params("Smoothing")))
        except NoOptionError:
            self.smoothing = False

        if self.smoothing:
            self.temp_readings = [None] * 5

        self.publish_state()

    def publish_state(self):
        """Acquires the current reading. If the value is reasonable (temperature 
        between -40 and 125) the reading is published.
        If smoothing, the average of the most recent five readings is published.
        If not smoothing the current reading is published. If temp_unit is "F",
        the temperature is published in degrees F. Both temperature is rounded
        to the tenth's place.
        Warning log statements are written for unreasonable values or errors
        reading the sensor.
        """
        try:
            temp = self.readSensor()
            if temp and self.temp_unit == "F":
                temp = temp * (9 / 5) + 32

            if temp and -40 <= temp <= 125:
                to_send = temp
                if self.smoothing:
                    self.temp_readings.pop()
                    self.temp_readings.insert(0, temp)
                    smoothingCount = sum([t is not None for t in self.temp_readings])
                    to_send = sum([t for t in self.temp_readings if t]) / smoothingCount
                self._send("{:.1f}".format(to_send), self.temp_dest)
            else:
                self.log.warning("Unreasonable temperature reading of %s "
                                 "dropping it", temp)
        except RuntimeError as error:
            self.log.warning("Error reading DHT: %s", error.args[0])
        
    def readSensor(self):
        valueTemp = float(-99)
        try:
            mytemp = ''
            f = open('/sys/bus/w1/devices/' + self.addr + '/w1_slave', 'r')
            line = f.readline() # read 1st line
            crc = line.rsplit(' ',1)
            crc = crc[1].replace('\n', '')
            if crc=='YES':
                line = f.readline() # read 2nd line
                mytemp = line.rsplit('t=', 1)
                valueTemp = float(mytemp[1])
                valueTemp = valueTemp/1000
            f.close()

        except IOError as ex:
            self.logger.warning("Error reading DS18B20: %s", ex.args[0])

        #self.logger.debug("Raw reading T:{0}".format(valueTemp ))

        return valueTemp

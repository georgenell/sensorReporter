"""
   Copyright 2019 George Nell

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

 Script:  graphiteConn.py
 Author:  George Nell
 Date:    January 17, 2019
 Purpose: Stores metrics in the Graphite Carbon database
"""

import sys
import socket
import time

class graphiteConnection(object):
    """Centralizes the Graphite logic"""

    def __init__(self, msgProc, logger, params, sensors, actuators):
        """Configures the client"""
        
        # ignore msgProc
        self.logger = logger
        self.server = params("Server")
        self.port   = int(params("Port"))
        
#    def register(unused1, unused2):
        # Do nothing

    def publish(self, message, destination):
        """Called by others to publish a message to a Destination"""
        # Todo - add some validation, Graphite (Carbon) only accepts Numbers as the message
        try:
            msg = "{0} {1} {2}\n".format(destination, message, int(time.time()))
            self.logger.info("Publish message: {0}".format(msg.strip()))
            sock = socket.socket()
            sock.connect((self.server, self.port))
            sock.sendall(msg.encode())
            sock.close()
        except:
            self.logger.error("Error publishing message: {0}".format(sys.exc_info()[0]))

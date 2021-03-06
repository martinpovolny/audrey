'''
*
*   Copyright [2011] [Red Hat, Inc.]
*
*   Licensed under the Apache License, Version 2.0 (the "License");
*   you may not use this file except in compliance with the License.
*   You may obtain a copy of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0
*
*   Unless required by applicable law or agreed to in writing, software
*   distributed under the License is distributed on an "AS IS" BASIS,
*   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
*   See the License for the specific language governing permissions and
*  limitations under the License.
*
'''
import os
import logging
import base64
import urllib

from collections import deque

from audrey.errors import AAError
from audrey.errors import AAErrorMissingDelimiter
from audrey.csclient import CSClient
from audrey.shell import run_cmd

LOGGER = logging.getLogger('Audrey')


class ServiceV1(object):
    '''
    Description:
        Used for storing a service and all of it's associated parameters
        as provided by the Config Server in the "required" parameters
        API message.

        services = [
                Service('serviceA', ['n&v', 'n&v', 'n&v',...]),
                Service('serviceB', ['n&v', 'n&v', 'n&v',...]),
                Service('serviceB', ['n&v', 'n&v', 'n&v',...]),
        ]

        This structure aids in tracking the parsed required config
        parameters which is useful when doing UNITTESTing.

    '''
    def __init__(self, name, tooling):
        self.name = name
        self.tooling = tooling
        self.params = {}

    def __repr__(self):
        return repr((self.name, self.params))

    @staticmethod
    def parse_require_config(src, tooling):
        '''
        Description:
          Parse the required config text message sent from the Config Server.

        Input:
          The required config string obtained from the Config Server,
          delimited by an | and an &

          Two tags will mark the sections of the data,
          '|service|' and  '|parameters|'

          To ensure all the data was received the entire string will be
          terminated with an "|".

          The string "|service|" will precede a service names.

          The string "|parameters|" will precede the parameters for
          the preceeding service, in the form: names&<b64 encoded values>.

        This will be a continuous text string (no CR or New Line).

          Format (repeating for each service):

          |service|<s1>|parameters|name1&<b64val>|name2&<b64val>|nameN&<b64v>|

          e.g.:
          |service|ssh::server|parameters|ssh_port&<b64('22')>
          |service|apache2::common|apache_port&<b64('8081')>|

        Returns:
            - A list of ServiceParams objects.
        '''

        services = []
        new = None

        CSClient.validate_message(src)

        # Message specific validation
        if src == '||':
            # special case indicating no required config needed.
            return []

        # split on pipe and chop of first and last, they will always be empty
        src = src.split('|')[1:-1]
        # get the indexes of the service identifiers
        srvs = deque([i for i,x in enumerate(src) if x == 'service'])
        srvs.append(len(src))

        if srvs[0] != 0:
            raise AAError(('|service| is not the first tag found. %s') % (src))

        while len(srvs) > 1:
            # rebuild a single service's cs string
            svc_str = "|%s|" % "|".join(src[srvs[0]:srvs[1]])
            name = src[srvs[0]+1]
            if name in ['service', 'parameters'] or '&' in name:
                raise AAError('invalid service name: %s' % name)
            # instanciate the service with it's name
            svc = Service(name, tooling)
            svc.parse_configs(svc_str)
            services.append(svc)
            srvs.popleft()

        return services

    def parse_configs(self, cs_str):
        '''
        parses a single service adding the params to the service object
        parses a string of form
        |service|svc_name|parameters|param1&<b64('val')>|param2&<b64('val')>|
        '''
        # split on pipe, remove first and last empty items and 
        # remove first 3 items, they're not parameters
        srv = deque(cs_str.split("|")[4:-1])
        while len(srv):
            param = srv.popleft()
            if '&' not in param:
                msg = 'name&value: %s missing & delimiter'
                raise AAErrorMissingDelimiter(msg % param)
            key, value = param.split('&')
            self.params[key] = value

    def gen_env(self):
        '''
        Description:
          Generate the os environment variables from the config params.

        Input:
          serv_name - A service name
              e.g.:
              jon_agent_config

          param_val - A parameter name&val pair. The value is base64 encoded.
              e.g.:
              jon_server_ip&MTkyLjE2OC4wLjE=

        Output:
          Set environment variables of the form:
          <name>=<value>
              e.g.:
              jon_server_ip=base64.b64decode('MTkyLjE2OC4wLjE=')
              jon_server_ip='192.168.0.1

        Raises AAError when encountering an error.

        '''
        LOGGER.debug('Invoked gen_env()')

        for param in self.params:
            var_name = '_'.join(('AUDREY_VAR', self.name, param))
            os.environ[var_name] = \
                base64.b64decode(self.params[param])

            # Get what was set and log it.
            cmd = ['/usr/bin/printenv', var_name]
            ret = run_cmd(cmd)
            LOGGER.debug(var_name + '=' + str(ret['out'].strip()))


class ServiceV2(ServiceV1):
    '''
    Overrides the V1 service with updates for API V2:w
    '''
    def generate_cs_str(self, status):
        '''
        cs put provides expects |provides&value|service&status|
        we're just pushing the service here
        '''
        return urllib.urlencode({'audrey_data': '||%s&%s|' % \
                                  (self.name, base64.b64encode(str(status)))})

    def invoke_tooling(self):
        '''
        invoke the service's tooling
        '''
        return self.tooling.invoke(self)

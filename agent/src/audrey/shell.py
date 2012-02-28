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

from subprocess import Popen, PIPE
from audrey.errors import ASError


class run_cmd_return_subproc(object):
    '''
    Used to pass return code to caller if no subprocess object
    is generated by Popen() due to an error.
    '''
    returncode = 127


def run_cmd(cmd, my_cwd=None):
    '''
    Description:
        Run a command given by a dictionary, check for stderr output,
        return code.

        To check the return code catch SystemExit then examine:
        ret['subproc'].returncode.

    Input:

        cmd - a list containing the command to execute.
            e.g.: cmd = ['ls', '/tmp']

    Returns:

        ret - a dictionary upon return contains the keys:
            'subproc', 'err', 'out'

        ret['subproc'].returncode = subprocess return code
        ret['err'] = command errors string.
        ret['out'] = command out list.

    Example:

        cmd = ['ls', '/tmp']
        ret = run_cmd(cmd)

        ret.keys()
        ['subproc', 'err', 'out']
        ret['subproc'].returncode
        0
        ret['err']
        ''
        ret['out']

    '''

    pfail = run_cmd_return_subproc()

    # Return dictionary to contain keys: 'cmd', 'subproc', 'err', 'out'
    ret = {'subproc': None, 'err': '', 'out': ''}

    try:
        ret['subproc'] = Popen(cmd, cwd=my_cwd, stdout=PIPE, stderr=PIPE)

    # unable to find command will result in an OSError
    except OSError, err:
        if not ret['subproc']:
            ret['subproc'] = pfail

        ret['subproc'].returncode = 127  # command not found
        ret['err'] = str(err)
        return ret

    # fill ret['out'] with stdout and ret['err'] with stderr
    ret.update(zip(['out', 'err'], ret['subproc'].communicate()))

    return ret


def run_pipe_cmd(cmd1, cmd2):
    '''
    Description:
        Run one command piped into another. Commands are given as
        dictionaries, check for stderr output, return code.

        To check the return code catch SystemExit then examine:
        ret['subproc'].returncode.

        That is this routine can be used to execute a command
        of the form:

    Input:

        cmd1 - a list containing the command to execute.
            e.g.: cmd = ['ls', '/tmp']

        cmd2 - a list containing the command to pipe the output
            of cmd1 to.
            e.g.: cmd = ['grep', 'a_file']

    Returns:

        ret - a dictionary upon return contains the keys:
            'subproc', 'err', 'out'

        ret['subproc'].returncode = subprocess return code
        ret['err'] = command errors string.
        ret['out'] = command out list.

    Example:

        cmd1 = ['ls', '/tmp']
        cmd2 = ['grep', 'a_file']
        ret = run_pipe_cmd(cmd1, cmd2)

        ret.keys()
        ['subproc', 'err', 'out']
        ret['subproc'].returncode
        0
        ret['err']
        ''
        ret['out']

    '''

    # Return dictionary to contain keys: 'cmd', 'subproc', 'err', 'out'
    ret = {'subproc': None, 'err': '', 'out': ''}

    p1 = None
    p2 = None
    pfail = run_cmd_return_subproc()

    # Execute the first command:
    try:
        p1 = Popen(cmd1, stdout=PIPE)
        p2 = Popen(cmd2, stdin=p1.stdout, stdout=PIPE)
        p1.stdout.close()

        # fill ret['out'] with stdout and ret['err'] with stderr
        # ret.update(zip(['out', 'err'], ret['subproc'].communicate()[0]))
        ret.update(zip(['out', 'err'], p2.communicate()))
        ret['subproc'] = p2

    # unable to find command will result in an OSError
    except OSError, err:
        if p2:
            ret['subproc'] = p2
        elif p1:
            ret['subproc'] = p1
        else:
            ret['subproc'] = pfail

        ret['subproc'].returncode = 127  # command not found
        ret['err'] = str(err)
        return ret

    return ret


def get_system_info():
    '''
    Description:
        Get the system info to be used for generating this instances
        provides back to the Config Server.

        Currently utilizes Puppet's facter via a Python subprocess call.

    Input:
        None

    Returns:
        A dictionary of system info name/value pairs.

    '''

    cmd = ['/usr/bin/facter']
    ret = run_cmd(cmd)
    if ret['subproc'].returncode != 0:
        raise ASError(('Failed command: \n%s \nError: \n%s') % \
            (' '.join(cmd), str(ret['err'])))

    facts = {}
    for fact in ret['out'].split('\n'):
        if fact:  # Handle the new line at the end of the facter output
            name, val = fact.split(' => ')
            facts[name] = val.rstrip()

    return facts

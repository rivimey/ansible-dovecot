#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This module is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This software is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this software.  If not, see <http://www.gnu.org/licenses/>.
"""


# ===========================================


DOCUMENTATION = '''
---
module: dovecot_user
author:
    - "David Symons (Multimac) <Mult1m4c@gmail.com>"
short_description: Manages users in a dovecot system.
description:
    - Creates, removes and sets options for users in Dovecot, including presence of standard 
      folders.
notes: []
requirements:
    - Dovecot
options:
    name:
        description:
            - Name of the printer in CUPS.
        required: false
        default: null
    state:
        description:
            - Whether the printer should or not be in CUPS.
        required: false
        default: present
        choices: ["present", "absent"]
    options:
        description:
            - A dictionary of key-value pairs describing printer options and their required value.
        default: {}
        required: false
'''

# ===========================================


EXAMPLES = '''
# Creates HP MFP via ethernet, set default A4 paper size and make this printer
  as server default.
- cups_lpadmin:
    name: 'HP_M1536'
    state: 'present'
    printer_or_class: 'printer'
    uri: 'hp:/net/HP_LaserJet_M1536dnf_MFP?ip=192.168.1.2'
    model: 'drv:///hp/hpcups.drv/hp-laserjet_m1539dnf_mfp-pcl3.ppd'
    default: 'true'
    location: 'Room 404'
    info: 'MFP, but duplex broken, as usual on this model'
    printer_assign_policy: 'students'
    report_ipp_supply_levels: 'true'
    report_snmp_supply_levels: 'false'
    options:
      media: 'iso_a4_210x297mm'

# Purge all printers/classes. Useful when does not matter what we have now,
  client always receive new configuration.
- cups_lpadmin: purge='true'
'''

# ===========================================


RETURN = '''
purge:
    description: Whether to purge all printers on CUPS or not.
    returned: when purge=True
    type: string
    sample: "True"
cmd_history:
    description: A concatenated string of all the commands run.
    returned: always
    type: string
    sample: "\nlpstat -p TEST \nlpinfo -l -m \nlpoptions -p TEST \nlpstat -p TEST \nlpstat -p TEST \nlpadmin -p TEST -o cupsIPPSupplies=true -o cupsSNMPSupplies=true \nlpoptions -p TEST -l "
'''


# ===========================================


class CUPSCommand(object):
    """
        This is the main class that directly deals with the lpadmin command.

        Method naming methodology:
            - Methods prefixed with 'cups_item' or '_cups_item' can be used with both printer and classes.
            - Methods prefixed with 'class' or '_class' are meant to work with classes only.
            - Methods prefixed with 'printer' or '_printer' are meant to work with printers only.

        CUPSCommand handles printers like so:
            - If state=absent:
                - Printer exists: Deletes printer
                - Printer doesn't exist: Does nothing and exits
            - If state=present:
                - Printer exists: Checks printer options and compares them to the ones stated:
                    - Options are different: Deletes the printer and installs it again with stated options.
                    - Options are same: Does nothing and exits.
                - Printer doesn't exist: Installs printer with stated options.
            - Mandatory options are set every time if the right variables are defined. They are:
                - cupsIPPSupplies
                - cupsSNMPSupplies
                - printer-op-policy
                - job-k-limit
                - job-page-limit
                - job-quota-period

        CUPSCommand handles classes like so:
            - If state=absent:
                - Class exists: Deletes class
                - Class doesn't exist: Does nothing and exits
            - If state=present:
                - Class exists: Checks class options and members and compares them to the ones stated:
                    - Options and members are different: Deletes the class and installs it again with
                      stated options and stated members.
                    - Options and members are same: Does nothing and exits.
                - Class doesn't exist: Installs class with stated options and members.
            - Mandatory options are set every time if the right variables are defined. They are:
                - cupsIPPSupplies
                - cupsSNMPSupplies
                - printer-op-policy
            - Notes about how classes are handled:
                - Members stated will be the final list of printers in that class.
                - It cannot add or remove printers from an existing list that might have more/other members defined.
                - It'll uninstall the class and create it from scratch as defined in this script if the defined member
                  list and the actual member list don't match.
    """

    def __init__(self, module):
        """
        Assigns module vars to object.
        """
        self.module = module

        self.driver = CUPSCommand.strip_whitespace(module.params['driver'])
        self.name = CUPSCommand.strip_whitespace(module.params['name'])
        self.printer_or_class = module.params['printer_or_class']

        self.state = module.params['state']
        self.purge = module.params['purge']

        self.uri = CUPSCommand.strip_whitespace(module.params['uri'])

        self.enabled = module.params['enabled']
        self.shared = module.params['shared']
        self.default = module.params['default']

        self.model = CUPSCommand.strip_whitespace(module.params['model'])

        self.info = CUPSCommand.strip_whitespace(module.params['info'])
        self.location = CUPSCommand.strip_whitespace(module.params['location'])

        self.options = module.params['options']

        self.assign_cups_policy = CUPSCommand.strip_whitespace(module.params['assign_cups_policy'])

        self.class_members = module.params['class_members']

        self.report_ipp_supply_levels = module.params['report_ipp_supply_levels']
        self.report_snmp_supply_levels = module.params['report_snmp_supply_levels']
        self.job_kb_limit = module.params['job_kb_limit']
        self.job_quota_limit = module.params['job_quota_limit']
        self.job_page_limit = module.params['job_page_limit']

        self.out = ""
        self.cmd_history = ""
        self.changed = False

        self.cups_current_options = {}
        self.cups_expected_options = {}
        self.class_current_members = []
        self.printer_current_options = {}

        self.check_mode = module.check_mode

        self.check_settings()

    def check_settings(self):
        """
        Checks the values provided to the module and see if there are any missing/illegal settings.

        Module fails and exits if it encounters an illegal combination of variables sent to the module.
        :returns: None
        """
        msgs = []

        if self.state == 'printer':
            if not self.printer_or_class:
                msgs.append("When state=present printer or class must be defined.")

            if self.printer_or_class == 'printer':
                if not self.uri and not self.exists_self():
                    msgs.append("URI is required to install printer.")

            if self.printer_or_class == 'class':
                if not self.class_members and not self.exists_self():
                    self.module.fail_json(msg="Empty class cannot be created.")

        if msgs:
            "\n".join(msgs)
            self.module.fail_json(msg=msgs)

    @staticmethod
    def strip_whitespace(text):
        """
        A static method to help with stripping white space around object variables.

        :returns: Trailing whitespace removed text or 'None' if input is 'None'.
        """
        try:
            return text.strip()
        except:
            return None

    def append_cmd_out(self, cmd_out):
        """
        Appends the out text from the command that was just run to the string with the out text of all the commands run.

        :param cmd_out: The text that was outputted during last command that was run.
        :returns: None
        """
        if cmd_out:
            self.out = "{0}{1}{2}".format(self.out, "\n", cmd_out)

    def append_cmd_history(self, cmd):
        """
        Appends the commands run into a single string.

        :param cmd: The command to be appended into the command history string.
        :returns: None
        """
        safe_cmd = ""
        for x in cmd:
            x = str(x)
            if " " in x:
                if not ((x.startswith('"') and x.endswith('"')) or (x.startswith("'") and x.endswith("'"))):
                    x = '{0}{1}{0}'.format('"', x)
            safe_cmd = "{0}{1}{2}".format(safe_cmd, x, " ")
        self.cmd_history = "{0}{1}{2}".format(self.cmd_history, "\n", safe_cmd)

    def _log_results(self, out):
        """
        Method to log the details outputted from the command that was just run.

        :param out: Output text from the command that was just run.
        :returns: None
        """
        self.append_cmd_out(out)

    def process_info_command(self, cmd):
        """
        Runs a command that's meant to poll information only.

        Wraps around _process_command and ensures command output isn't logged as we're just fetching for information.

        :param cmd: The command to run.
        :returns: The output of _process_command which is return code, command output and error output.
        """
        return self._process_command(cmd, log=False)

    def process_change_command(self, cmd, err_msg, only_log_on_error=False):
        """
        Runs a command that's meant to change CUPS state/settings.

        Wraps around _process_command and ensures command output is logged as we're making changes to the system.
        An optional only_log_on_error is provided for the install_mandatory_options methods that are always run
        almost always and need not pollute the changed/output text with its information. This'll ensure the output
        and error text is only recorded when there's an error (err != None) and (rc != 0).

        It also is an easy way to centralize change command therefore making support_check_mode easier to implement.

        :param cmd: The command to run.
        :param err_msg: The error message with which to exit the module if an error occurred.
        :param only_log_on_error: The optional flag to record output if there's an error. Default=False
        :returns: The output of _process_command which is return code, command output and error output.
        """
        (rc, out, err) = self._process_command(cmd, log=False)

        if rc != 0 and err:
            self.module.fail_json(msg="Error Message - {0}. Command Error Output - {1}.".format(err_msg, err))

        if self.check_mode:
            self.module.exit_json(changed=True)

        if not only_log_on_error:
            self._log_results(out)
            self.changed = True

        return rc, out, err

    def _process_command(self, cmd, log=True):
        """
        Runs a command given to it. Also logs the details if specified.

        :param cmd: The command to run.
        :param log: Boolean to specify if the command output should be logged. Default=True
        :returns: Return code, command output and error output of the command that was run.
        """
        self.append_cmd_history(cmd)

        (rc, out, err) = self.module.run_command(cmd)

        if log:
            self._log_results(out)

        return rc, out, err

    def printer_install(self):
        """
        The main method that's called when state is 'present' and printer_or_class is 'printer'.

        It checks to see if printer exists and if its settings are the same as defined.
        If not, it deletes it.

        It then checks to see if it exists again and installs it with defined settings if it doesn't exist.

        It also installs mandatory settings.

        Lastly it sets the printer specific options to the printer if it isn't the same.
        """
        if self.exists_self() and not self.printer_check_cups_options():
            self.cups_item_uninstall_self()

        if not self.exists_self():
            self._printer_install()

        # cupsIPPSupplies, cupsSNMPSupplies, job-k-limit, job-page-limit, printer-op-policy,
        # job-quota-period cannot be checked via cups command-line tools yet
        # Therefore force set these options if they exist
        if self.exists_self():
            self._printer_install_mandatory_options()

        if not self.printer_check_options():
            self._printer_install_options()

    def start_process(self):
        """
        This starts the process of processing the information provided to the module.

        Based on state, the following is done:
        - state=present:
            - printer_or_class=printer:
                - Call CUPSCommand.printer_install() to install the printer.
            - printer_or_class=class:
                - Call CUPSCommand.class_install() to install the class.
        - state=absent:
            - Call CUPSCommand.cups_item_uninstall() to uninstall either a printer or a class.

        :returns: 'result' a hash containing the desired state.
        """
        result = {}

        if self.purge:
            self.cups_purge_all_items()
            result['purge'] = self.purge

        else:
            result['state'] = self.state
            result['printer_or_class'] = self.printer_or_class
            result['assign_cups_policy'] = self.assign_cups_policy
            result['name'] = self.name

            if self.printer_or_class == 'printer':
                if self.state == 'present':
                    self.printer_install()
                else:
                    self.cups_item_uninstall_self()
                result['uri'] = self.uri

            else:
                if self.state == 'present':
                    self.class_install()
                else:
                    self.cups_item_uninstall_self()
                result['class_members'] = self.class_members

        result['changed'] = self.changed

        if self.out:
            result['stdout'] = self.out

        # Verbose Logging info
        if self.cmd_history:
            result['cmd_history'] = self.cmd_history
        if self.cups_current_options:
            result['cups_current_options'] = self.cups_current_options
        if self.cups_expected_options:
            result['cups_expected_options'] = self.cups_expected_options
        if self.class_current_members:
            result['class_current_members'] = self.class_current_members
        if self.printer_current_options:
            result['printer_current_options'] = self.printer_current_options

        return result


# ===========================================


def main():
    """
    main function that populates this Ansible module with variables and sets it in motion.

    First an Ansible Module is defined with the variable definitions and default values.
    Then a CUPSCommand is created using using this module. CUPSCommand populates its own values with the module vars.

    This CUPSCommand's start_process() method is called to begin processing the information provided to the module.

    Records the rc, out, err values of the commands run above and accordingly exists the module and sends the status
    back to to Ansible using module.exit_json().
    """
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(required=False, default='present', choices=['present', 'absent'], type='str'),
            driver=dict(required=False, default='model', choices=['model', 'ppd'], type='str'),
            purge=dict(required=False, default=False, type='bool'),
            name=dict(required=False, type='str'),
            printer_or_class=dict(default='printer', required=False, type='str', choices=['printer', 'class']),
            uri=dict(required=False, default=None, type='str'),
            enabled=dict(required=False, default=True, type='bool'),
            shared=dict(required=False, default=False, type='bool'),
            default=dict(required=False, default=False, type='bool'),
            model=dict(required=False, default=None, type='str'),
            info=dict(required=False, default=None, type='str'),
            location=dict(required=False, default=None, type='str'),
            assign_cups_policy=dict(required=False, default=None, type='str'),
            class_members=dict(required=False, default=[], type='list'),
            report_ipp_supply_levels=dict(required=False, default=True, type='bool'),
            report_snmp_supply_levels=dict(required=False, default=True, type='bool'),
            job_kb_limit=dict(required=False, default=None, type='int'),
            job_quota_limit=dict(required=False, default=None, type='int'),
            job_page_limit=dict(required=False, default=None, type='int'),
            options=dict(required=False, default={}, type='dict'),
        ),
        supports_check_mode=True,
        required_one_of=[['name', 'purge']],
        mutually_exclusive=[['name', 'purge']]
    )

    cups_command = CUPSCommand(module)
    result_info = cups_command.start_process()
    module.exit_json(**result_info)

# Import statements at the bottom as per Ansible best practices.
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()

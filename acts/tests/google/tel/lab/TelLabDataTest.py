#/usr/bin/env python3.4
#
#   Copyright 2016 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""
Sanity tests for connectivity tests in telephony
"""

import time
from acts.controllers.anritsu_lib._anritsu_utils import AnritsuError
from acts.controllers.anritsu_lib.md8475a import MD8475A
from acts.controllers.anritsu_lib.md8475a import VirtualPhoneStatus
from acts.test_utils.tel.anritsu_utils import cb_serial_number
from acts.test_utils.tel.anritsu_utils import set_system_model_1x
from acts.test_utils.tel.anritsu_utils import set_system_model_gsm
from acts.test_utils.tel.anritsu_utils import set_system_model_lte
from acts.test_utils.tel.anritsu_utils import set_system_model_lte_wcdma
from acts.test_utils.tel.anritsu_utils import set_system_model_wcdma
from acts.test_utils.tel.anritsu_utils import sms_mo_send
from acts.test_utils.tel.anritsu_utils import sms_mt_receive_verify
from acts.test_utils.tel.anritsu_utils import set_usim_parameters
from acts.test_utils.tel.tel_defines import DIRECTION_MOBILE_ORIGINATED
from acts.test_utils.tel.tel_defines import DIRECTION_MOBILE_TERMINATED
from acts.test_utils.tel.tel_defines import NETWORK_MODE_CDMA
from acts.test_utils.tel.tel_defines import NETWORK_MODE_GSM_ONLY
from acts.test_utils.tel.tel_defines import NETWORK_MODE_GSM_UMTS
from acts.test_utils.tel.tel_defines import NETWORK_MODE_LTE_GSM_WCDMA
from acts.test_utils.tel.tel_defines import RAT_1XRTT
from acts.test_utils.tel.tel_defines import RAT_GSM
from acts.test_utils.tel.tel_defines import RAT_LTE
from acts.test_utils.tel.tel_defines import RAT_WCDMA
from acts.test_utils.tel.tel_defines import RAT_FAMILY_CDMA2000
from acts.test_utils.tel.tel_defines import RAT_FAMILY_GSM
from acts.test_utils.tel.tel_defines import RAT_FAMILY_LTE
from acts.test_utils.tel.tel_defines import RAT_FAMILY_UMTS
from acts.test_utils.tel.tel_defines import NETWORK_SERVICE_DATA
from acts.test_utils.tel.tel_defines import GEN_4G
from acts.test_utils.tel.tel_test_utils import ensure_network_rat
from acts.test_utils.tel.tel_test_utils import ensure_phones_idle
from acts.test_utils.tel.tel_test_utils import ensure_network_generation
from acts.test_utils.tel.tel_test_utils import toggle_airplane_mode
from acts.test_utils.tel.tel_test_utils import iperf_test_by_adb
from acts.test_utils.tel.TelephonyBaseTest import TelephonyBaseTest
from acts.utils import adb_shell_ping
from acts.utils import rand_ascii_str
from acts.controllers import iperf_server
from acts.utils import exe_cmd

DEFAULT_PING_DURATION = 30

class TelLabDataTest(TelephonyBaseTest):
    SETTLING_TIME = 30
    SERIAL_NO = cb_serial_number()

    def __init__(self, controllers):
        TelephonyBaseTest.__init__(self, controllers)
        self.ad = self.android_devices[0]
        self.ip_server = self.iperf_servers[0]
        self.port_num = self.ip_server.port
        self.log.info("Iperf Port is %s", self.port_num)
        self.ad.sim_card = getattr(self.ad, "sim_card", None)
        self.log.info("SIM Card is %s", self.ad.sim_card)
        self.md8475a_ip_address = self.user_params[
            "anritsu_md8475a_ip_address"]
        self.wlan_option = self.user_params.get("anritsu_wlan_option", False)

    def setup_class(self):
        try:
            self.anritsu = MD8475A(self.md8475a_ip_address, self.log,
                                   self.wlan_option)
        except AnritsuError:
            self.log.error("Error in connecting to Anritsu Simulator")
            return False
        return True

    def setup_test(self):
        ensure_phones_idle(self.log, self.android_devices)
        toggle_airplane_mode(self.log, self.ad, True)
        return True

    def teardown_test(self):
        self.log.info("Stopping Simulation")
        self.anritsu.stop_simulation()
        toggle_airplane_mode(self.log, self.ad, True)
        return True

    def teardown_class(self):
        self.anritsu.disconnect()
        return True

    def _setup_data(self,
                   set_simulation_func,
                   rat):
        try:
            set_simulation_func(self.anritsu, self.user_params,
                                self.ad.sim_card)
            set_usim_parameters(self.anritsu, self.ad.sim_card)
            self.anritsu.start_simulation()

            if rat == RAT_LTE:
                preferred_network_setting = NETWORK_MODE_LTE_GSM_WCDMA
                rat_family = RAT_FAMILY_LTE
            elif rat == RAT_WCDMA:
                preferred_network_setting = NETWORK_MODE_GSM_UMTS
                rat_family = RAT_FAMILY_UMTS
            elif rat == RAT_GSM:
                preferred_network_setting = NETWORK_MODE_GSM_ONLY
                rat_family = RAT_FAMILY_GSM
            elif rat == RAT_1XRTT:
                preferred_network_setting = NETWORK_MODE_CDMA
                rat_family = RAT_FAMILY_CDMA2000
            else:
                self.log.error("No valid RAT provided for SMS test.")
                return False

            if not ensure_network_rat(self.log,
                                      self.ad,
                                      preferred_network_setting,
                                      rat_family,
                                      toggle_apm_after_setting=True):
                self.log.error(
                    "Failed to set rat family {}, preferred network:{}".format(
                        rat_family, preferred_network_setting))
                return False

            self.anritsu.wait_for_registration_state()
            time.sleep(self.SETTLING_TIME)
            if not ensure_network_generation(self.log, self.ad,
                                             GEN_4G, NETWORK_SERVICE_DATA):
                self.log.error("Device not in 4G Connected Mode.")
                return False

            # Fetch IP address of the host machine
            cmd = "|".join(("ifconfig", "grep eth0 -A1", "grep inet",
                           "cut -d ':' -f2", "cut -d ' ' -f 1"))
            destination_ip = exe_cmd(cmd)
            destination_ip = (destination_ip.decode("utf-8")).split("\n")[0]
            self.log.info("Dest IP is %s", destination_ip)

            if not adb_shell_ping(self.ad, DEFAULT_PING_DURATION,
                                  destination_ip):
                self.log.error("Pings failed to Destination.")
                return False

            self.ip_server.start()
            if not iperf_test_by_adb(self.log, self.ad, destination_ip,
                                     self.port_num, True, 60):
                self.log.error("iperf failed to Destination.")
            self.ip_server.stop()

        except AnritsuError as e:
            self.log.error("Error in connection with Anritsu Simulator: " +
                           str(e))
            return False
        except Exception as e:
            self.log.error("Exception during Data procedure: " + str(e))
            return False
        return True

    """ Tests Begin """

    @TelephonyBaseTest.tel_test_wrap
    def test_lte_pings_iperf(self):
        """ Test Pings functionality on LTE

        Make Sure Phone is in LTE mode
        Ping to destination server IP
        iperf server on host machine
        iperf client in on adb
        iperf DL

        Returns:
            True if pass; False if fail
        """
        return self._setup_data(set_system_model_lte, RAT_LTE)

    """ Tests End """
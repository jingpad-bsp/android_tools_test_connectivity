#!/usr/bin/env python3.4
#
#   Copyright 2017 - The Android Open Source Project
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
import splinter
from time import sleep

BROWSER_WAIT_SHORT = 1
BROWSER_WAIT_MED = 3


def create(configs):
    """ Factory method for retail AP class.

    Args:
        configs: list of dicts containing ap settings. ap settings must contain
        the following: brand, model, ip_address, username and password
    """
    SUPPORTED_APS = {
        ("Netgear", "R7000"): "NetgearR7000AP",
        ("Netgear", "R7500"): "NetgearR7500AP",
        ("Netgear", "R8000"): "NetgearR8000AP"
    }
    objs = []
    for config in configs:
        try:
            ap_class_name = SUPPORTED_APS[(config["brand"], config["model"])]
            ap_class = globals()[ap_class_name]
        except KeyError:
            raise KeyError("Invalid retail AP brand and model combination.")
        objs.append(ap_class(config))
    return objs


def detroy(objs):
    return


class WifiRetailAP(object):
    """ Base class implementation for retail ap.

    Base class provides functions whose implementation is shared by all aps.
    If some functions such as set_power not supported by ap, checks will raise
    exceptions.
    """

    def __init__(self, ap_settings):
        raise NotImplementedError

    def read_ap_settings(self):
        """ Function that reads current ap settings.

        Function implementation is AP dependent and thus base class raises exception
        if function not implemented in child class.
        """
        raise NotImplementedError

    def configure_ap(self):
        """ Function that configures ap based on values of ap_settings.

        Function implementation is AP dependent and thus base class raises exception
        if function not implemented in child class.
        """
        raise NotImplementedError

    def set_ssid(self, network, ssid):
        """ Function that sets network SSID

        Args:
            network: string containing network identifier (2G, 5G_1, 5G_2)
            ssid: string containing ssid
        """
        setting_to_update = {"ssid_{}".format(network): str(ssid)}
        self.update_ap_settings(setting_to_update)

    def set_channel(self, network, channel):
        """ Function that sets network channel

        Args:
            network: string containing network identifier (2G, 5G_1, 5G_2)
            channel: string or int containing channel
        """
        setting_to_update = {"channel_{}".format(network): str(channel)}
        self.update_ap_settings(setting_to_update)

    def set_bandwidth(self, network, bandwidth):
        """ Function that sets network bandwidth/mode

        Args:
            network: string containing network identifier (2G, 5G_1, 5G_2)
            bandwidth: string containing mode, e.g. 11g, VHT20, VHT40, VHT80.
        """
        setting_to_update = {"bandwidth_{}".format(network): str(bandwidth)}
        self.update_ap_settings(setting_to_update)

    def set_power(self, network, power):
        """ Function that sets network transmit power

        Args:
            network: string containing network identifier (2G, 5G_1, 5G_2)
            power: string containing power level, e.g., 25%, 100%
        """
        setting_to_update = {"power_{}".format(network): str(power)}
        self.update_ap_settings(setting_to_update)

    def set_security(self, network, security_type, *password):
        """ Function that sets network security setting and password (optional)

        Args:
            network: string containing network identifier (2G, 5G_1, 5G_2)
            security: string containing security setting, e.g., WPA2-PSK
            password: optional argument containing password
        """
        if (len(password) == 1) and (type(password[0]) == str):
            setting_to_update = {
                "security_type_{}".format(network): str(security_type),
                "password_{}".format(network): str(password[0])
            }
        else:
            setting_to_update = {
                "security_type_{}".format(network): str(security_type)
            }
        self.update_ap_settings(setting_to_update)

    def update_ap_settings(self, *dict_settings, **named_settings):
        """ Function to update settings of existing AP.

        Function copies arguments into ap_settings and calls configure_retail_ap
        to apply them.

        Args:
            *dict_settings accepts single dictionary of settings to update
            **named_settings accepts named settings to update
            Note: dict and named_settings cannot contain the same settings.
        """
        settings_to_update = {}
        if (len(dict_settings) == 1) and (type(dict_settings[0]) == dict):
            for key, value in dict_settings[0].items():
                if key in named_settings:
                    raise KeyError("{} was passed twice.".format(key))
                else:
                    settings_to_update[key] = value
        elif len(dict_settings) > 1:
            raise TypeError("Wrong number of positional arguments given")
            return

        for key, value in named_settings.items():
            settings_to_update[key] = value

        for key, value in settings_to_update.items():
            if (key in self.ap_settings):
                self.ap_settings[key] = value
            else:
                raise KeyError("Invalid setting passed to AP configuration.")

        self.configure_ap()


class NetgearR7000AP(WifiRetailAP):
    """ Class that implements Netgear R7500 AP.
    """

    def __init__(self, ap_settings):
        self.ap_settings = ap_settings.copy()
        self.CONFIG_PAGE = "http://{}:{}@{}/WLG_wireless_dual_band_r10.htm".format(
            self.ap_settings["admin_username"],
            self.ap_settings["admin_password"], self.ap_settings["ip_address"])
        self.CONFIG_PAGE_NOLOGIN = "http://{}/WLG_wireless_dual_band_r10.htm".format(
            self.ap_settings["ip_address"])
        self.NETWORKS = ["2G", "5G_1"]
        self.CONFIG_PAGE_FIELDS = {
            ("2G", "ssid"): "ssid",
            ("5G_1", "ssid"): "ssid_an",
            ("2G", "channel"): "w_channel",
            ("5G_1", "channel"): "w_channel_an",
            ("2G", "bandwidth"): "opmode",
            ("5G_1", "bandwidth"): "opmode_an",
            ("2G", "power"): "enable_tpc",
            ("5G_1", "power"): "enable_tpc_an",
            ("2G", "security_type"): "security_type",
            ("5G_1", "security_type"): "security_type_an",
            ("2G", "password"): "passphrase",
            ("5G_1", "password"): "passphrase_an"
        }
        self.read_ap_settings()
        if ap_settings.items() <= self.ap_settings.items():
            return
        else:
            self.update_ap_settings(ap_settings)

    def read_ap_settings(self):
        BW_MODE_VALUES = {
            "g and b": "11g",
            "145Mbps": "VHT20",
            "300Mbps": "VHT40",
            "HT80": "VHT80"
        }
        POWER_MODE_VALUES = {"1": "100%", "2": "75%", "3": "50%", "4": "25%"}

        chrome_options = splinter.driver.webdriver.chrome.Options()
        chrome_options.add_argument("--no-proxy-server")
        with splinter.Browser("chrome", chrome_options) as browser:
            # Visit URL
            browser.visit(self.CONFIG_PAGE)
            sleep(BROWSER_WAIT_SHORT)
            browser.visit(self.CONFIG_PAGE_NOLOGIN)
            sleep(BROWSER_WAIT_SHORT)

            for key, value in self.CONFIG_PAGE_FIELDS.items():
                config_item = browser.find_by_name(value)
                if "bandwidth" in key:
                    self.ap_settings["{}_{}".format(key[1], key[
                        0])] = BW_MODE_VALUES[config_item.first.value]
                elif "power" in key:
                    self.ap_settings["{}_{}".format(key[1], key[
                        0])] = POWER_MODE_VALUES[config_item.first.value]
                elif "security_type" in key:
                    for item in config_item:
                        if item.checked:
                            self.ap_settings["{}_{}".format(key[1], key[
                                0])] = item.value
                else:
                    self.ap_settings["{}_{}".format(key[1], key[
                        0])] = config_item.first.value
        return self.ap_settings.copy()

    def configure_ap(self):
        BW_MODE_TEXT = {
            "11g": "Up to 54 Mbps",
            "VHT20": "Up to 289 Mbps",
            "VHT40": "Up to 600 Mbps",
            "VHT80": "Up to 1300 Mbps"
        }

        chrome_options = splinter.driver.webdriver.chrome.Options()
        chrome_options.add_argument("--no-proxy-server")
        with splinter.Browser("chrome", chrome_options) as browser:
            # Visit URL
            browser.visit(self.CONFIG_PAGE)
            sleep(BROWSER_WAIT_SHORT)
            browser.visit(self.CONFIG_PAGE_NOLOGIN)
            sleep(BROWSER_WAIT_SHORT)

            # Update power and bandwidth for each network
            for key, value in self.CONFIG_PAGE_FIELDS.items():
                config_item = browser.find_by_name(value).first
                if "power" in key:
                    config_item.select_by_text(
                        self.ap_settings["{}_{}".format(key[1], key[0])])
                elif "bandwidth" in key:
                    config_item.select_by_text(BW_MODE_TEXT[self.ap_settings[
                        "{}_{}".format(key[1], key[0])]])

            # Update security settings (passwords updated only if applicable)
            for key, value in self.CONFIG_PAGE_FIELDS.items():
                if "security_type" in key:
                    browser.choose(
                        value,
                        self.ap_settings["{}_{}".format(key[1], key[0])])
                    if self.ap_settings["{}_{}".format(key[1], key[
                            0])] == "WPA2-PSK":
                        config_item = browser.find_by_name(
                            self.CONFIG_PAGE_FIELDS[(key[0], "password"
                                                     )]).first
                        config_item.fill(self.ap_settings["{}_{}".format(
                            "password", key[0])])

            # Update SSID and channel for each network
            # NOTE: Update ordering done as such as workaround for R8000
            # wherein channel and SSID get overwritten when some other
            # variables are changed
            for key, value in self.CONFIG_PAGE_FIELDS.items():
                config_item = browser.find_by_name(value).first
                if "ssid" in key:
                    config_item.fill(
                        self.ap_settings["{}_{}".format(key[1], key[0])])
                elif "channel" in key:
                    config_item.select(
                        self.ap_settings["{}_{}".format(key[1], key[0])])
                    sleep(BROWSER_WAIT_SHORT)
                    try:
                        alert = browser.get_alert()
                        alert.accept()
                    except:
                        pass

            sleep(BROWSER_WAIT_SHORT)
            browser.find_by_name("Apply").first.click()
            sleep(BROWSER_WAIT_SHORT)
            try:
                alert = browser.get_alert()
                alert.accept()
                sleep(BROWSER_WAIT_SHORT)
            except:
                sleep(BROWSER_WAIT_SHORT)
            browser.visit(self.CONFIG_PAGE)


class NetgearR7500AP(WifiRetailAP):
    """ Class that implements Netgear R7000 AP.

    NOTE: Many of the functions here are reused in NetgearR8000AP
    """

    def __init__(self, ap_settings):
        self.ap_settings = ap_settings.copy()
        self.CONFIG_PAGE = "http://{}:{}@{}/".format(
            self.ap_settings["admin_username"],
            self.ap_settings["admin_password"], self.ap_settings["ip_address"])
        self.CONFIG_PAGE_NOLOGIN = "http://{}/".format(
            self.ap_settings["ip_address"])
        self.NETWORKS = ["2G", "5G_1"]
        self.CONFIG_PAGE_FIELDS = {
            ("2G", "ssid"): "ssid",
            ("5G_1", "ssid"): "ssid_an",
            ("2G", "channel"): "w_channel",
            ("5G_1", "channel"): "w_channel_an",
            ("2G", "bandwidth"): "opmode",
            ("5G_1", "bandwidth"): "opmode_an",
            ("2G", "security_type"): "security_type",
            ("5G_1", "security_type"): "security_type_an",
            ("2G", "password"): "passphrase",
            ("5G_1", "password"): "passphrase_an"
        }
        self.read_ap_settings()
        if ap_settings.items() <= self.ap_settings.items():
            return
        else:
            self.update_ap_settings(ap_settings)

    def read_ap_settings(self):
        BW_MODE_VALUES = {
            "1": "11g",
            "2": "VHT20",
            "3": "VHT40",
            "7": "VHT20",
            "8": "VHT40",
            "9": "VHT80"
        }
        chrome_options = splinter.driver.webdriver.chrome.Options()
        chrome_options.add_argument("--no-proxy-server")
        with splinter.Browser("chrome", chrome_options) as browser:
            browser.visit(self.CONFIG_PAGE)
            browser.visit(self.CONFIG_PAGE_NOLOGIN)
            wireless_button = browser.find_by_id("wireless").first
            wireless_button.click()

            with browser.get_iframe("formframe") as iframe:
                for key, value in self.CONFIG_PAGE_FIELDS.items():
                    if "bandwidth" in key:
                        config_item = iframe.find_by_name(value).first
                        self.ap_settings["{}_{}".format(key[1], key[
                            0])] = BW_MODE_VALUES[config_item.value]
                    elif "password" in key:
                        try:
                            config_item = iframe.find_by_name(value).first
                            self.ap_settings["{}_{}".format(key[1], key[
                                0])] = config_item.value
                            self.ap_settings["{}_{}".format(
                                "security_type", key[0])] = "WPA2-PSK"
                        except:
                            self.ap_settings["{}_{}".format(key[1], key[
                                0])] = "defaultpassword"
                            self.ap_settings["{}_{}".format(
                                "security_type", key[0])] = "Disable"
                    elif "channel" or "ssid" in key:
                        config_item = iframe.find_by_name(value).first
                        self.ap_settings["{}_{}".format(key[1], key[
                            0])] = config_item.value
                    else:
                        pass
            return self.ap_settings.copy()

    def configure_ap(self):
        BW_MODE_TEXT_2G = {
            "11g": "Up to 54 Mbps",
            "VHT20": "Up to 289 Mbps",
            "VHT40": "Up to 600 Mbps"
        }
        BW_MODE_TEXT_5G = {
            "VHT20": "Up to 347 Mbps",
            "VHT40": "Up to 800 Mbps",
            "VHT80": "Up to 1733 Mbps"
        }
        chrome_options = splinter.driver.webdriver.chrome.Options()
        chrome_options.add_argument("--no-proxy-server")
        with splinter.Browser("chrome", chrome_options) as browser:
            browser.visit(self.CONFIG_PAGE)
            browser.visit(self.CONFIG_PAGE_NOLOGIN)
            wireless_button = browser.find_by_id("wireless").first
            wireless_button.click()
            sleep(BROWSER_WAIT_MED)

            with browser.get_iframe("formframe") as iframe:
                # Update SSID and security setting for each network
                for key, value in self.CONFIG_PAGE_FIELDS.items():
                    if "ssid" in key:
                        config_item = iframe.find_by_name(value).first
                        config_item.fill(
                            self.ap_settings["{}_{}".format(key[1], key[0])])
                    elif "channel" in key:
                        channel_string = "0" * (int(
                            self.ap_settings["{}_{}".format(key[1], key[0])]
                        ) < 10) + str(
                            self.ap_settings["{}_{}".format(key[1], key[0])])
                        config_item = iframe.find_by_name(value).first
                        config_item.select_by_text(channel_string)
                    elif key == ("2G", "bandwidth"):
                        config_item = iframe.find_by_name(value).first
                        config_item.select_by_text(
                            str(BW_MODE_TEXT_2G[self.ap_settings[
                                "{}_{}".format(key[1], key[0])]]))
                    elif key == ("5G_1", "bandwidth"):
                        config_item = iframe.find_by_name(value).first
                        config_item.select_by_text(
                            str(BW_MODE_TEXT_5G[self.ap_settings[
                                "{}_{}".format(key[1], key[0])]]))

                # Update passwords for WPA2-PSK protected networks
                # (Must be done after security type is selected)
                for key, value in self.CONFIG_PAGE_FIELDS.items():
                    if "security_type" in key:
                        iframe.choose(
                            value,
                            self.ap_settings["{}_{}".format(key[1], key[0])])
                        if self.ap_settings["{}_{}".format(key[1], key[
                                0])] == "WPA2-PSK":
                            config_item = iframe.find_by_name(
                                self.CONFIG_PAGE_FIELDS[(key[0], "password"
                                                         )]).first
                            config_item.fill(self.ap_settings["{}_{}".format(
                                "password", key[0])])

                apply_button = iframe.find_by_name("Apply")
                apply_button[0].click()
                sleep(BROWSER_WAIT_SHORT)
                try:
                    alert = browser.get_alert()
                    alert.accept()
                except:
                    pass
                sleep(BROWSER_WAIT_SHORT)
                try:
                    alert = browser.get_alert()
                    alert.accept()
                except:
                    pass
                sleep(BROWSER_WAIT_SHORT)
            browser.visit(self.CONFIG_PAGE)


class NetgearR8000AP(NetgearR7000AP):
    """ Class that implements Netgear R8000 AP.

    Since most of the class' implementation is shared with the R7000, this
    class inherits from NetgearR7000AP and simply redifines config parameters
    """

    def __init__(self, ap_settings):
        self.ap_settings = ap_settings.copy()
        self.CONFIG_PAGE = "http://{}:{}@{}/WLG_wireless_dual_band_r8000.htm".format(
            self.ap_settings["admin_username"],
            self.ap_settings["admin_password"], self.ap_settings["ip_address"])
        self.CONFIG_PAGE_NOLOGIN = "http://{}/WLG_wireless_dual_band_r8000.htm".format(
            self.ap_settings["ip_address"])
        self.NETWORKS = ["2G", "5G_1", "5G_2"]
        self.CONFIG_PAGE_FIELDS = {
            ("2G", "ssid"): "ssid",
            ("5G_1", "ssid"): "ssid_an",
            ("5G_2", "ssid"): "ssid_an_2",
            ("2G", "channel"): "w_channel",
            ("5G_1", "channel"): "w_channel_an",
            ("5G_2", "channel"): "w_channel_an_2",
            ("2G", "bandwidth"): "opmode",
            ("5G_1", "bandwidth"): "opmode_an",
            ("5G_2", "bandwidth"): "opmode_an_2",
            ("2G", "security_type"): "security_type",
            ("5G_1", "security_type"): "security_type_an",
            ("5G_2", "security_type"): "security_type_an_2",
            ("2G", "password"): "passphrase",
            ("5G_1", "password"): "passphrase_an",
            ("5G_2", "password"): "passphrase_an_2"
        }
        self.read_ap_settings()
        if ap_settings.items() <= self.ap_settings.items():
            return
        else:
            self.update_ap_settings(ap_settings)
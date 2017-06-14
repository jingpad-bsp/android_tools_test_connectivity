#!/usr/bin/python3.4
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

import queue
import time

from acts import asserts
from acts.test_utils.wifi.aware import aware_const as aconsts
from acts.test_utils.wifi.aware import aware_test_utils as autils
from acts.test_utils.wifi.aware.AwareBaseTest import AwareBaseTest


class LatencyTest(AwareBaseTest):
  """Set of tests for Wi-Fi Aware to measure latency of Aware operations."""
  SERVICE_NAME = "GoogleTestServiceXY"

  # number of second to 'reasonably' wait to make sure that devices synchronize
  # with each other - useful for OOB test cases, where the OOB discovery would
  # take some time
  WAIT_FOR_CLUSTER = 5

  def __init__(self, controllers):
    AwareBaseTest.__init__(self, controllers)

  def start_discovery_session(self, dut, session_id, is_publish, dtype):
    """Start a discovery session

    Args:
      dut: Device under test
      session_id: ID of the Aware session in which to start discovery
      is_publish: True for a publish session, False for subscribe session
      dtype: Type of the discovery session

    Returns:
      Discovery session started event.
    """
    config = {}
    config[aconsts.DISCOVERY_KEY_DISCOVERY_TYPE] = dtype
    config[aconsts.DISCOVERY_KEY_SERVICE_NAME] = "GoogleTestServiceXY"

    if is_publish:
      disc_id = dut.droid.wifiAwarePublish(session_id, config)
      event_name = aconsts.SESSION_CB_ON_PUBLISH_STARTED
    else:
      disc_id = dut.droid.wifiAwareSubscribe(session_id, config)
      event_name = aconsts.SESSION_CB_ON_SUBSCRIBE_STARTED

    event = autils.wait_for_event(dut, event_name)
    return disc_id, event

  def run_discovery_latency(self, results, do_unsolicited_passive, dw_24ghz,
                            dw_5ghz, num_iterations):
    """Run the service discovery latency test with the specified DW intervals.

    Args:
      results: Result array to be populated - will add results (not erase it)
      do_unsolicited_passive: True for unsolicited/passive, False for
                              solicited/active.
      dw_24ghz: DW interval in the 2.4GHz band.
      dw_5ghz: DW interval in the 5GHz band.
    """
    key = "%s_dw24_%d_dw5_%d" % (
        "unsolicited_passive"
        if do_unsolicited_passive else "solicited_active", dw_24ghz, dw_5ghz)
    results[key] = {}
    results[key]["num_iterations"] = num_iterations

    p_dut = self.android_devices[0]
    p_dut.pretty_name = "Publisher"
    s_dut = self.android_devices[1]
    s_dut.pretty_name = "Subscriber"

    # override the default DW configuration
    autils.configure_dw(p_dut, is_default=True, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(
        p_dut, is_default=False, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(p_dut, is_default=True, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(
        p_dut, is_default=False, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(s_dut, is_default=True, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(
        s_dut, is_default=False, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(s_dut, is_default=True, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(
        s_dut, is_default=False, is_24_band=False, value=dw_5ghz)

    # Publisher+Subscriber: attach and wait for confirmation
    p_id = p_dut.droid.wifiAwareAttach(False)
    autils.wait_for_event(p_dut, aconsts.EVENT_CB_ON_ATTACHED)
    s_id = s_dut.droid.wifiAwareAttach(False)
    autils.wait_for_event(s_dut, aconsts.EVENT_CB_ON_ATTACHED)

    # start publish
    p_disc_event = self.start_discovery_session(
        p_dut, p_id, True, aconsts.PUBLISH_TYPE_UNSOLICITED
        if do_unsolicited_passive else aconsts.PUBLISH_TYPE_SOLICITED)

    # wait for for devices to synchronize with each other - used so that first
    # discovery isn't biased by synchronization.
    time.sleep(self.WAIT_FOR_CLUSTER)

    # loop, perform discovery, and collect latency information
    latencies = []
    failed_discoveries = 0
    for i in range(num_iterations):
      # start subscribe
      s_disc_id, s_session_event = self.start_discovery_session(
          s_dut, s_id, False, aconsts.SUBSCRIBE_TYPE_PASSIVE
          if do_unsolicited_passive else aconsts.SUBSCRIBE_TYPE_ACTIVE)

      # wait for discovery (allow for failures here since running lots of
      # samples and would like to get the partial data even in the presence of
      # errors)
      try:
        discovery_event = s_dut.ed.pop_event(
            aconsts.SESSION_CB_ON_SERVICE_DISCOVERED, autils.EVENT_TIMEOUT)
      except queue.Empty:
        s_dut.log.info("[Subscriber] Timed out while waiting for "
                       "SESSION_CB_ON_SERVICE_DISCOVERED")
        failed_discoveries = failed_discoveries + 1
        continue
      finally:
        # destroy subscribe
        s_dut.droid.wifiAwareDestroyDiscoverySession(s_disc_id)

      # collect latency information
      latencies.append(
          discovery_event["data"][aconsts.SESSION_CB_KEY_TIMESTAMP_MS] -
          s_session_event["data"][aconsts.SESSION_CB_KEY_TIMESTAMP_MS])
      self.log.info("Latency #%d = %d" % (i, latencies[-1]))

    autils.extract_stats(
        s_dut,
        data=latencies,
        results=results[key],
        key_prefix="",
        log_prefix="Subscribe Session Discovery (%s, dw24=%d, dw5=%d)" %
        ("Unsolicited/Passive"
         if do_unsolicited_passive else "Solicited/Active", dw_24ghz, dw_5ghz))
    results[key]["num_failed_discovery"] = failed_discoveries

    # clean up
    p_dut.droid.wifiAwareDestroyAll()
    s_dut.droid.wifiAwareDestroyAll()

  def run_message_latency(self, results, dw_24ghz, dw_5ghz, num_iterations):
    """Run the message tx latency test with the specified DW intervals.

    Args:
      results: Result array to be populated - will add results (not erase it)
      dw_24ghz: DW interval in the 2.4GHz band.
      dw_5ghz: DW interval in the 5GHz band.
    """
    key = "dw24_%d_dw5_%d" % (dw_24ghz, dw_5ghz)
    results[key] = {}
    results[key]["num_iterations"] = num_iterations

    p_dut = self.android_devices[0]
    s_dut = self.android_devices[1]

    # override the default DW configuration
    autils.configure_dw(p_dut, is_default=True, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(
        p_dut, is_default=False, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(p_dut, is_default=True, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(
        p_dut, is_default=False, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(s_dut, is_default=True, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(
        s_dut, is_default=False, is_24_band=True, value=dw_24ghz)
    autils.configure_dw(s_dut, is_default=True, is_24_band=False, value=dw_5ghz)
    autils.configure_dw(
        s_dut, is_default=False, is_24_band=False, value=dw_5ghz)

    # Start up a discovery session
    (p_id, s_id, p_disc_id, s_disc_id,
     peer_id_on_sub) = autils.create_discovery_pair(
         p_dut,
         s_dut,
         p_config=autils.create_discovery_config(
             self.SERVICE_NAME, aconsts.PUBLISH_TYPE_UNSOLICITED),
         s_config=autils.create_discovery_config(
             self.SERVICE_NAME, aconsts.SUBSCRIBE_TYPE_PASSIVE))

    latencies = []
    failed_tx = 0
    messages_rx = 0
    missing_rx = 0
    corrupted_rx = 0
    for i in range(num_iterations):
      # send message
      msg_s2p = "Message Subscriber -> Publisher #%d" % i
      next_msg_id = self.get_next_msg_id()
      s_dut.droid.wifiAwareSendMessage(s_disc_id, peer_id_on_sub, next_msg_id,
                                       msg_s2p, 0)

      # wait for Tx confirmation
      try:
        sub_tx_msg_event = s_dut.ed.pop_event(
            aconsts.SESSION_CB_ON_MESSAGE_SENT, 2 * autils.EVENT_TIMEOUT)
        latencies.append(
            sub_tx_msg_event["data"][aconsts.SESSION_CB_KEY_LATENCY_MS])
      except queue.Empty:
        s_dut.log.info("[Subscriber] Timed out while waiting for "
                       "SESSION_CB_ON_MESSAGE_SENT")
        failed_tx = failed_tx + 1
        continue

      # wait for Rx confirmation (and validate contents)
      try:
        pub_rx_msg_event = p_dut.ed.pop_event(
            aconsts.SESSION_CB_ON_MESSAGE_RECEIVED, 2 * autils.EVENT_TIMEOUT)
        messages_rx = messages_rx + 1
        if (pub_rx_msg_event["data"][aconsts.SESSION_CB_KEY_MESSAGE_AS_STRING]
            != msg_s2p):
          corrupted_rx = corrupted_rx + 1
      except queue.Empty:
        s_dut.log.info("[Publisher] Timed out while waiting for "
                       "SESSION_CB_ON_MESSAGE_RECEIVED")
        missing_rx = missing_rx + 1
        continue

    autils.extract_stats(
        s_dut,
        data=latencies,
        results=results[key],
        key_prefix="",
        log_prefix="Subscribe Session Discovery (dw24=%d, dw5=%d)" %
                   (dw_24ghz, dw_5ghz))
    results[key]["failed_tx"] = failed_tx
    results[key]["messages_rx"] = messages_rx
    results[key]["missing_rx"] = missing_rx
    results[key]["corrupted_rx"] = corrupted_rx

    # clean up
    p_dut.droid.wifiAwareDestroyAll()
    s_dut.droid.wifiAwareDestroyAll()


  ########################################################################

  def test_discovery_latency_default_dws(self):
    """Measure the service discovery latency with the default DW configuration.
    """
    results = {}
    self.run_discovery_latency(
        results=results, do_unsolicited_passive=True, dw_24ghz=1, dw_5ghz=1,
        num_iterations=100)
    asserts.explicit_pass(
        "test_discovery_latency_default_parameters finished", extras=results)

  def test_discovery_latency_non_interactive_dws(self):
    """Measure the service discovery latency with the DW configuration for non
    -interactive mode (lower power)."""
    results = {}
    self.run_discovery_latency(
        results=results, do_unsolicited_passive=True, dw_24ghz=4, dw_5ghz=0,
        num_iterations=100)
    asserts.explicit_pass(
        "test_discovery_latency_non_interactive_dws finished", extras=results)

  def test_discovery_latency_all_dws(self):
    """Measure the service discovery latency with all DW combinations (low
    iteration count)"""
    results = {}
    for dw24 in range(1, 6):  # permitted values: 1-5
      for dw5 in range(0, 6): # permitted values: 0, 1-5
        self.run_discovery_latency(
            results=results,
            do_unsolicited_passive=True,
            dw_24ghz=dw24,
            dw_5ghz=dw5,
            num_iterations=10)
    asserts.explicit_pass(
        "test_discovery_latency_all_dws finished", extras=results)

  def test_message_latency_default_dws(self):
    """Measure the send message latency with the default DW configuration. Test
    performed on non-queued message transmission - i.e. waiting for confirmation
    of reception (ACK) before sending the next message."""
    results = {}
    self.run_message_latency(
        results=results, dw_24ghz=1, dw_5ghz=1, num_iterations=100)
    asserts.explicit_pass(
        "test_message_latency_default_dws finished", extras=results)

  def test_message_latency_non_interactive_dws(self):
    """Measure the send message latency with the DW configuration for
    non-interactive mode. Test performed on non-queued message transmission -
    i.e. waiting for confirmation of reception (ACK) before sending the next
    message."""
    results = {}
    self.run_message_latency(
        results=results, dw_24ghz=4, dw_5ghz=0, num_iterations=100)
    asserts.explicit_pass(
        "test_message_latency_non_interactive_dws finished", extras=results)
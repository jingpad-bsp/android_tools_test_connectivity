#!/usr/bin/env python3
#
#   Copyright 2018 - The Android Open Source Project
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

import os
import shutil
import tempfile

from acts import logger
from acts.libs.proc import job

_NUWA_JAR_CMD = 'java -jar %s/nuwa-commandline.jar'
_UNZIP_CMD = 'tar -xzf %s -C %s'


class NuwaError(Exception):
    """Raised for exceptions that occur in Nuwa-related tasks"""


class NuwaCli(object):
    """Provides an interface for running Nuwa workflows under its CLI.

    This class does not handle workflow creation, which requires the Nuwa
    frontend.
    """
    def __init__(self, nuwa_zip, workflow_paths, log_path=None):
        """Creates a NuwaCli object. Extracts the required nuwa-cli binaries.

        Args:
            nuwa_zip: The path to nuwa-cli.tar.gz
            workflow_paths: List of paths to nuwa workflows and/or directories
                containing them.
            log_path: Directory for storing logs generated by Nuwa.
        """
        self._nuwa_zip = nuwa_zip
        self._nuwa_path = tempfile.mkdtemp(prefix='nuwa')
        self._log_path = log_path
        if self._log_path:
            os.makedirs(self._log_path, exist_ok=True)
        self._log = logger.create_tagged_trace_logger(tag='Nuwa')
        self._set_workflows(workflow_paths)
        self._setup_cli()

    def _set_workflows(self, workflow_paths):
        """Set up a dictionary that maps workflow name to its file location.
        This allows the user to specify workflows to run without having to
        provide the full path.

        Args:
            workflow_paths: List of paths to nuwa workflows and/or directories
                containing them.

        Raises:
            NuwaError if two or more Nuwa workflows share the same file name
        """
        if isinstance(workflow_paths, str):
            workflow_paths = [workflow_paths]

        # get a list of workflow files from specified paths
        def _raise(e):
            raise e
        workflow_files = []
        for path in workflow_paths:
            for (root, _, files) in os.walk(path, onerror=_raise):
                for file in files:
                    workflow_files.append(os.path.join(root, file))

        # populate the dictionary
        self._workflows = {}
        for path in workflow_files:
            workflow_name = os.path.basename(path)
            if workflow_name in self._workflows.keys():
                raise NuwaError('Nuwa workflows may not share the same name.')
            self._workflows[workflow_name] = path

    def _setup_cli(self):
        """Extract tar from nuwa_zip and place unzipped files in nuwa_path.

        Raises:
            Exception if the extraction fails.
        """
        self._log.debug('Extracting nuwa-cli binaries from %s' % self._nuwa_zip)
        unzip_cmd = _UNZIP_CMD % (self._nuwa_zip, self._nuwa_path)
        try:
            job.run(unzip_cmd.split())
        except job.Error:
            self._log.exception('Failed to extract nuwa-cli binaries.')
            raise

    def run(self, serial, workflows):
        """Run specified workflows on the Nuwa CLI.

        Args:
            serial: Device serial
            workflows: List or str of workflows to run.
        """
        base_cmd = _NUWA_JAR_CMD % self._nuwa_path
        if isinstance(workflows, str):
            workflows = [workflows]
        for workflow_name in workflows:
            self._log.info('Running workflow "%s"' % workflow_name)
            if workflow_name in self._workflows:
                args = '-d %s -i %s' % (serial, self._workflows[workflow_name])
            else:
                self._log.error(
                    'The workflow "%s" does not exist.' % workflow_name)
                continue
            if self._log_path:
                args = '%s -o %s' % (args, self._log_path)
            cmd = '%s %s' % (base_cmd, args)
            try:
                result = job.run(cmd.split())
            except job.Error:
                self._log.exception(
                    'Failed to run workflow "%s"' % workflow_name)
                continue
            if result.stdout:
                stdout_split = result.stdout.splitlines()
                if len(stdout_split) > 2:
                    self._log.debug('Nuwa logs stored at %s' % stdout_split[2])

    def __del__(self):
        """Delete the temp directory to Nuwa CLI binaries upon ACTS exit."""
        shutil.rmtree(self._nuwa_path)

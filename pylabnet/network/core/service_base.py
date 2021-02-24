import rpyc
import os
import ctypes
import signal
from pylabnet.utils.logging.logger import LogHandler
from pylabnet.utils.helper_methods import get_os


class ServiceBase(rpyc.Service):

    _module = None
    log = LogHandler()

    def on_connect(self, conn):
        # code that runs when a connection is created
        # (to init the service, if needed)
        self.log.info('Client connected')

    def on_disconnect(self, conn):
        # code that runs after the connection has already closed
        # (to finalize the service, if needed)
        self.log.info('Client disconnected')

    def assign_module(self, module):
        self._module = module

    def assign_logger(self, logger=None):
        self.log = LogHandler(logger=logger)

    def close_server(self):
        """ Closes the server for which the service is running """

        pid = os.getpid()
        operating_system = get_os()
        if operating_system == 'Windows':
            handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
        elif operating_system == 'Linux':
            os.kill(pid, signal.SIGTERM)

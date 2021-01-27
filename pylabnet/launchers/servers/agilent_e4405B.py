import socket
import sys

from pylabnet.utils.helper_methods import get_ip, load_device_config
from pylabnet.utils.logging.logger import LogClient
import pylabnet.hardware.spectrum_analyzer.agilent_e4405B as sa
from pylabnet.network.core.generic_server import GenericServer
from pylabnet.network.client_server.agilent_e4405B import Service


def launch(**kwargs):
    """ Connects to MCS2 and instantiates server

    :param kwargs: (dict) containing relevant kwargs
        :logger: instance of LogClient for logging purposes
        :port: (int) port number for the Cnt Monitor server
    """

    settings = load_device_config('agilent_e4405B',
            kwargs['config'],
            logger=kwargs['logger']
    )

    # Instantiate driver
    spectrum_analyzer = sa.Driver(
        gpib_address=settings['device_id'],
        logger=kwargs['logger']
    )

    sa_service = Service()
    sa_service.assign_module(module=spectrum_analyzer)
    sa_service.assign_logger(logger=kwargs['logger'])
    sa_server = GenericServer(
        service=sa_service,
        host=get_ip(),
        port=kwargs['port']
    )
    sa_server.start()



if __name__ == "__main__":


    dev_id = "GPIB0::18::INSTR"
        # Instantiate driver
    spectrum_analyzer = sa.Driver(
        gpib_address=dev_id,
        logger=None
    )
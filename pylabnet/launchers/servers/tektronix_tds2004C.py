from pylabnet.hardware.oscilloscopes.tektronix_tds2004C import Driver
from pylabnet.network.client_server.tektronix_tds2004C import Service, Client
from pylabnet.utils.helper_methods import get_ip, load_device_config, setup_full_service


def launch(**kwargs):

    logger = kwargs['logger']
    config_dict = load_device_config(
        device='tektronix_tds2004C',
        config=kwargs['config'],
        logger=logger
    )
    scope = Driver(
        gpib_address=config_dict['device_id'],
        logger=logger
    )
    setup_full_service(
        service_class=Service,
        module=scope,
        logger=logger,
        host=get_ip()
    )

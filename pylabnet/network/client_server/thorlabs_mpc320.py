from pylabnet.network.core.service_base import ServiceBase
from pylabnet.network.core.client_base import ClientBase
import time

class Service(ServiceBase):

    def exposed_open(self):
        return self._module.open()

    def exposed_close(self):
        return self._module.close()

    def exposed_home(self, paddle_num):
        return self._module.home(paddle_num)

    def exposed_set_velocity(self, velocity):
        return self._module.set_velocity(velocity)

    def exposed_move(self, paddle_num, pos, sleep_time):
        return self._module.move(paddle_num, pos, sleep_time)

    def exposed_move_rel(self, paddle_num, step, sleep_time):
        return self._module.move_rel(paddle_num, step, sleep_time)

    def exposed_get_angle(self, paddle_num):
        return self._module.get_angle(paddle_num)

    # Overwriting close_hardware_connection of ServiceBase
    def close_hardware_connection(self):
        return self._module.close()

class Client(ClientBase):

    def open(self):
        return self._service.exposed_open()

    def close(self):
        return self._service.exposed_close()

    def home(self, paddle_num):
        return self._service.exposed_home(paddle_num)

    def set_velocity(self, velocity):
        return self._service.exposed_set_velocity(velocity)

    def move(self, paddle_num, pos, sleep_time):
        return self._service.exposed_move(paddle_num, pos, sleep_time)

    def move_rel(self, paddle_num, step, sleep_time):
        return self._service.exposed_move_rel(paddle_num, step, sleep_time)

    def get_angle(self, paddle_num):
        return self._service.exposed_get_angle(paddle_num)





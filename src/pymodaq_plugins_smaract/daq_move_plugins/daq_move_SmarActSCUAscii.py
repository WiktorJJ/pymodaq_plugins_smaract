
from typing import Union
import pyvisa

from pymodaq.control_modules.move_utility_classes import DAQ_Move_base, main, comon_parameters_fun, DataActuatorType
from pymodaq.utils.data import DataActuator

from pymodaq_plugins_smaract.utils import Config
from pymeasure.instruments.smaract.scu_ascii import (
    SmarActSCU_ASCII, SmarActSCULinear, SmarActSCUAngular,
    SCUChannelLinear, SCUChannelAngular, Q_)

plugin_config = Config()

rm = pyvisa.ResourceManager()
instruments_ports = rm.list_resources() # liste de touts ports sur ordinateur actuel
instruments_movement = ['Linear','Angular']

# trouver le bon port sur l'ordinateur actuel, sinon prend le 1er sur liste
if plugin_config('SCU', 'ascii', 'default_port') in instruments_ports:
    instrument_port = plugin_config('SCU', 'ascii', 'default_port')
else:
    instrument_port = instruments_ports[0]


class DAQ_Move_SmarActSCUAscii(DAQ_Move_base):
    """

    """
    is_multiaxes = True
    _axis_names: Union[list[str], dict[str, int]] = ['0', '1', '2']
    _controller_units: Union[str, list[str]] = 'mm'
    _epsilon: Union[float, list[float]] = 0.1  # TODO replace this by a value that is correct depending on your controller
    data_actuator_type = DataActuatorType.DataActuator

    #every property of the current driver that will be used, the 'title' is used for calling the object
    params = [
                 {'title': 'Port', 'name': 'port', 'type': 'list', 'value': instrument_port,
                  'limits': list(instruments_ports)},
                 {'title': 'Device:', 'name': 'device', 'type': 'str', 'value': '', 'readonly': True},
                 {'title': 'SN:', 'name': 'serial_number', 'type': 'str', 'value': '', 'readonly': True},
                 {'title': 'Frequency (Hz)', 'name': 'frequency', 'type': 'int', 'value': 1000,},
                 {'title': 'Amplitude (V)', 'name': 'amplitude', 'type': 'int', 'value': 100,
                  'limits': [15, 100]},
                 {'title': 'Movement', 'name': 'movement', 'type': 'list', 'value': instruments_movement,
                  'limits': list(instruments_movement)},

    ] + comon_parameters_fun(is_multiaxes=is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)
    ##########################################################

    def ini_attributes(self):
        self.controller: Union[SCUChannelLinear, SmarActSCUAngular,
        SmarActSCU_ASCII] = None

    def commit_settings(self, param):
        if param.name() == 'amplitude':
            self.controller.amplitude = Q_(param.value(), 'V')
        elif param.name() == 'frequency':
            self.controller.frequency = Q_(param.value(), 'Hz')

    def ini_stage(self, controller=None):
        """Initialize the controller and stages (axes) with given parameters.

        """

        if self.is_master:
            if self.settings['movement'] == 'Linear':
                self.controller = SmarActSCULinear(self.settings['port'])
            else:
                self.controller = SmarActSCUAngular(self.settings['port'])
        else:
            self.controller = controller

        self.settings.child('device').setValue(self.controller.model)
        self.settings.child('serial_number').setValue(self.controller.serial_nb)

        self.commit_settings(self.settings.child('amplitude'))
        self.commit_settings(self.settings.child('frequency'))

        #is it not hardcoding here, when we say that the channel must be '0'?
        self.axis_units = [self.controller.channels['0'].unit for _ in range(3)]

        self.settings.child('movement').setOpts(enabled=False)
        info = ''
        initialized = True

        return info, initialized

    def close(self):
        """
        Close the communication with the SmarAct controller.
        """
        self.settings.child('movement').setOpts(enabled=True)
        if self.is_master:
            self.controller.close()

    def get_actuator_value(self):
        """
        Get the current position from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        quantity: Q_ = self.controller.channels['0'].get_position()
        value = DataActuator(data=quantity.magnitude, units=quantity.units)
        # convert position if scaling options have been used, mandatory here
        value = self.get_position_with_scaling(value)
        value = self.target_position
        self.current_position = value
        return value

    def move_abs(self, value: DataActuator):
        """
        Move to an absolute position

        Parameters:
        ----------
         - position: float
        """
        # limit position if bounds options has been selected and if position is
        # out of them
        value = self.check_bound(value)
        self.target_value = value
        # convert the user set position to the controller position if scaling
        # has been activated by user
        value = self.set_position_with_scaling(value)

        self.controller.channels[self.axis_name].move_abs(value.quantities[0][0])
        #int(value.value(self.axis_unit))


    def move_rel(self, value: DataActuator):
        """
        Move to a relative position

        Parameters:
        ----------
         - position: float
        """
        value = (self.check_bound(self.current_position + value) - self.current_position)
        self.target_position = value + self.current_position
        value = self.set_position_relative_with_scaling(value)

        self.controller.channels['0'].move_rel(int(value.value(self.axis_unit)))
        self.controller.channels[self.axis_name].move_rel(value.quantities[0][0])

    def move_home(self):
        """
        Move to home and reset position to zero.
        """
        self.controller.channels['0'].move_to_ref()
        self.get_actuator_value()

    def stop_motion(self):
        """
        Stop any ongoing movement of the positionner.
        """
        self.controller.stop()
        ##self.move_done()


if __name__ == "__main__":
    main(__file__, init=False)

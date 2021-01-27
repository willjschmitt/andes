"""
Models for playing in history data.
"""

from andes.core.model import Model, ModelData
from andes.core.param import NumParam, DataParam, IdxParam
from andes.core.service import ConstService


class PLBVFU1Data(ModelData):
    def __init__(self):
        ModelData.__init__(self)
        self.bus = IdxParam(model='Bus',
                            info="interface bus idx",
                            mandatory=True,
                            )
        self.gen = IdxParam(info="static generator idx",
                            model='StaticGen',
                            mandatory=True,
                            )

        self.Vflag = NumParam(default=1,
                              info='Voltage playback flag',
                              )
        self.fflag = NumParam(default=1,
                              info='Frequency playback flag',
                              )
        self.fpath = DataParam(mandatory=True,
                               info='Playback file, full path',
                               )

        self.Vscale = NumParam(default=1.0,
                               info='Voltage scaling factor',
                               non_negative=True,
                               )
        self.fscale = NumParam(default=1.0,
                               info='frequency scaling factor',
                               non_negative=True,
                               )
        self.Tv = NumParam(default=0.02,
                           info='Time const for V signal',
                           )
        self.Tf = NumParam(default=0.02,
                           info='Time const for f signal',
                           )


class PLBVFU1Model(Model):
    """
    Implementation of PLBVFU1 play-in model.
    """

    def __init__(self, system, config):
        Model.__init__(self, system, config)

        self.flags.tds = True
        self.flags.s_num = True  # enable call to `s_numeric`
        self.group = 'PlayIn'

        self.Voffset = ConstService(v_str='0.0',
                                    info='Voltage offset',
                                    )
        self.foffset = ConstService(v_str='0.0',
                                    info='freq offset',
                                    )

        # TODO:
        # - Load data from files (t, voltage frequency): use a Block to export values?
        # - Interpolate values (voltage, frequency) for the current t
        # - Calculate the power injections based on V and delta

    def s_numeric(self):
        pass


class PLBVFU1(PLBVFU1Data, PLBVFU1Model):
    """
    Model for playing in voltage and frequency data as a generator.
    """

    def __init__(self, system, config):
        PLBVFU1Data.__init__(self)
        PLBVFU1Model.__init__(self, system, config)

import LMWTimeseries

Rijn = LMWTimeseries('lobith.cfg')
#Rijn_verw = LMWTimeseries('lobith_verwacht.cfg')
Maas = LMWTimeseries('stpieter.cfg')
#Maas_verw = LMWTimeseries('stpieter_verwacht.cfg')

Rijn.update()
Maas.update()
#Rijn_verw.update()
#Maas_verw.update()
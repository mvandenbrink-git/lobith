from LMWTimeseries import LMWTimeseries

Rijn = LMWTimeseries('lobith.cfg', 'LMW.cfg')
#Rijn_verw = LMWTimeseries('lobith_verwacht.cfg')
Maas = LMWTimeseries('borgharen.cfg', 'LMW.cfg')
#Maas_verw = LMWTimeseries('borgharen_verwacht.cfg')

Rijn.update()
Maas.update()
#Rijn_verw.update()
#Maas_verw.update()
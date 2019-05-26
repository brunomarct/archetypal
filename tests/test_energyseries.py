import pandas as pd
import numpy as np
import archetypal as ar


def test_energyseries():
    idf = ['./input_data/regular/5ZoneNightVent1.idf',
           './input_data/regular/AdultEducationCenter.idf']
    outputs = {'ep_object': 'Output:Variable'.upper(),
               'kwargs': {'Key_Value': 'OCCUPY-1',
                          'Variable_Name': 'Schedule Value',
                          'Reporting_Frequency': 'Hourly'}}
    wf = './input_data/CAN_PQ_Montreal.Intl.AP.716270_CWEC.epw'
    idf = ar.copy_file(idf)
    sql = ar.run_eplus(idf, weather_file=wf, prep_outputs=[outputs],
                       annual=True, expandobjects=True)
    report = ar.get_from_reportdata(sql)

    ep = ar.reportdata.ReportData(report)
    # sv = ep.sorted_values(name='Schedule Value', key_value='OCCUPY-1',
    #                       by='TimeIndex')
    sv = ep.filter_report_data(name=('Heating:Electricity',
                                     'Heating:Gas',
                                     'Heating:DistrictHeating'))
    hl = sv.heating_load(normalize=True, sort=False,
                         concurrent_sort=True)
    dl = hl.discretize()
    assert hl.capacity_factor == 0.10376668840257346
    hl.plot3d(
        save=True, axis_off=True, kind='polygon', cmap=None,
        fig_width=3, fig_height=8, edgecolors='k', linewidths=0.5)
    #
    # prob = ar.discretize(hl, bins=10)
    # prob.duration.display()
    # prob.amplitude.display()


def test_energyseries_2():
    idf = ['./input_data/regular/5ZoneNightVent1.idf']
    wf = './input_data/CAN_PQ_Montreal.Intl.AP.716270_CWEC.epw'
    idf = ar.copy_file(idf)
    sql = ar.run_eplus(idf, weather_file=wf,
                       annual=True, expandobjects=True)
    report = ar.get_from_reportdata(sql)

    ep = ar.ReportData(report)
    # sv = ep.sorted_values(name='Schedule Value', key_value='OCCUPY-1',
    #                       by='TimeIndex')
    sv = ep.filter_report_data(name=('Heating:Electricity',
                                     'Heating:Gas',
                                     'Heating:DistrictHeating'))
    hl = sv.heating_load(normalize=True, sort=True)
    dl = hl.discretize()
    assert hl.capacity_factor == 0.10376668840257346
    hl.plot3d(
        save=True, axis_off=True, kind='polygon', cmap=None,
        fig_width=3, fig_height=8, edgecolors='k', linewidths=0.5)
    #


def test_simple_energyseries():
    file = './input_data/test_profile.csv'
    df = pd.read_csv(file, index_col=[0], names=['Heat'])
    ep = ar.EnergySeries(df.Heat, from_units='BTU/hour',
                                               frequency='1H',
                                               is_sorted=True)
    epc = ep.unit_conversion()
    res = epc.discretize()
    print(res)


def test_some():
    # Heating Load Profile
    Fs = 8760
    Sc = 100000  # kWh
    f = 1
    sample = 8760
    x = np.arange(sample)
    y1 = (np.cos(2 * np.pi * f * x / Fs) + f) * Sc

    # Cooling Load Profile
    Fs = 8760
    Sc = 75000  # kWh
    f = 1
    sample = 8760
    y2 = ((-np.cos(2 * np.pi * f * x / Fs)) * Sc) + Sc

    # Electricity Load Profile
    Fs = 8760
    Sc = 75000  # kWh
    f = 365 * 2  # Two peaks per day
    sample = 8760
    y3 = ((-np.cos(2 * np.pi * f * x / Fs)) * Sc) + Sc

    # pd.DatetimeIndex(freq='1H')
    d = {'HeatLoad': ar.EnergySeries(y1, from_units='J/hour'),
         'CoolingLoad': ar.EnergySeries(y2, from_units='J/hour'),
         'ElectricityLoad': ar.EnergySeries(y3, from_units='J/hour')}
    CommunityProfile = ar.EnergyDataFrame(d, from_units='J/hour')
    CommunityProfile.HeatingLoad
    print(CommunityProfile)
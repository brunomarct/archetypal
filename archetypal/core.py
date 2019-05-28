################################################################################
# Module: core.py
# Description:
# License: MIT, see full license in LICENSE.txt
# Web: https://github.com/samuelduchesne/archetypal
################################################################################

import functools
import io
import json
import logging as lg
import os
import time
from collections import OrderedDict
from pprint import pformat

import numpy as np
import pandas as pd
from sklearn import preprocessing

from archetypal import log, label_surface, type_surface, layer_composition, \
    piecewise, rmse
from archetypal import plot_energyprofile
from archetypal import run_eplus, load_idf
from archetypal import settings, object_from_idf, object_from_idfs, \
    calc_simple_glazing, \
    iscore, weighted_mean, top, GasMaterial, BuildingTemplate, \
    GlazingMaterial, OpaqueMaterial, OpaqueConstruction, \
    WindowConstruction, StructureDefinition, DaySchedule, WeekSchedule, \
    YearSchedule, DomesticHotWaterSetting, VentilationSetting, \
    ZoneConditioning, \
    ZoneConstructionSet, ZoneLoad, Zone, WindowSetting, parallel_process


class UmiTemplate:
    """

    """

    def __init__(self, name='unnamed', BuildingTemplates=None,
                 GasMaterials=None, GlazingMaterials=None,
                 OpaqueConstructions=None, OpaqueMaterials=None,
                 WindowConstructions=None, StructureDefinitions=None,
                 DaySchedules=None, WeekSchedules=None, YearSchedules=None,
                 DomesticHotWaterSettings=None, VentilationSettings=None,
                 WindowSettings=None, ZoneConditionings=None,
                 ZoneConstructionSets=None, ZoneLoads=None, Zones=None):
        """

        Args:
            name (str): The name of the template
            Zones (list of Zone):
            ZoneLoads (list of ZoneLoad):
            ZoneConstructionSets (list of ZoneConstructionSet):
            ZoneConditionings (list of ZoneConditioning):
            WindowSettings (list of WindowSetting):
            VentilationSettings (list of VentilationSetting):
            DomesticHotWaterSettings (list of DomesticHotWaterSetting):
            YearSchedules (list of YearSchedule):
            WeekSchedules (list of WeekSchedule):
            DaySchedules (list of DaySchedule):
            StructureDefinitions (list of StructureDefinition):
            WindowConstructions (list of WindowConstruction):
            OpaqueMaterials (list of OpaqueMaterial):
            OpaqueConstructions (list of OpaqueConstruction):
            GlazingMaterials (list of GlazingMaterial):
            GasMaterials (list of GasMaterial):
            BuildingTemplates (list of BuildingTemplate):
        """
        if Zones is None:
            Zones = []
        if ZoneLoads is None:
            ZoneLoads = []
        if ZoneConstructionSets is None:
            ZoneConstructionSets = []
        if ZoneConditionings is None:
            ZoneConditionings = []
        if WindowSettings is None:
            WindowSettings = []
        if VentilationSettings is None:
            VentilationSettings = []
        if DomesticHotWaterSettings is None:
            DomesticHotWaterSettings = []
        if YearSchedules is None:
            YearSchedules = []
        if WeekSchedules is None:
            WeekSchedules = []
        if DaySchedules is None:
            DaySchedules = []
        if StructureDefinitions is None:
            StructureDefinitions = []
        if WindowConstructions is None:
            WindowConstructions = []
        if OpaqueMaterials is None:
            OpaqueMaterials = []
        if OpaqueConstructions is None:
            OpaqueConstructions = []
        if GlazingMaterials is None:
            GlazingMaterials = []
        if GasMaterials is None:
            GasMaterials = []
        if BuildingTemplates is None:
            BuildingTemplates = []

        self.idfs = None
        self.idf_files = None
        self.name = name
        self.Zones = Zones
        self.ZoneLoads = ZoneLoads
        self.ZoneConstructionSets = ZoneConstructionSets
        self.ZoneConditionings = ZoneConditionings
        self.WindowSettings = WindowSettings
        self.VentilationSettings = VentilationSettings
        self.DomesticHotWaterSettings = DomesticHotWaterSettings
        self.YearSchedules = YearSchedules
        self.WeekSchedules = WeekSchedules
        self.DaySchedules = DaySchedules
        self.StructureDefinitions = StructureDefinitions
        self.WindowConstructions = WindowConstructions
        self.OpaqueMaterials = OpaqueMaterials
        self.OpaqueConstructions = OpaqueConstructions
        self.BuildingTemplates = BuildingTemplates
        self.GasMaterials = GasMaterials
        self.GlazingMaterials = GlazingMaterials

    @classmethod
    def from_idf(self, idf_files, weather, sql=None, load=False, name='unnamed',
                 load_idf_kwargs=None, run_eplus_kwargs=None):
        """Initializes a UmiTemplate class from one or more idf_files.

        Iterates over each building zones and creates corresponding objects
        from the building object to material objects.

        Args:
            idf_files (str or list):
            weather (str):
            load (bool):
            run_eplus_kwargs (dict):
            load_idf_kwargs (dict):
        """
        # instanciate class
        if run_eplus_kwargs is None:
            run_eplus_kwargs = {}
        if load_idf_kwargs is None:
            load_idf_kwargs = {}
        t = UmiTemplate(name)

        # fill in arguments
        t.idf_files = idf_files
        t.weather = weather
        t.sql = sql

        t.idfs = [load_idf(idf_file) for idf_file
                  in idf_files]

        # For each idf load
        gms, glazms, oms = [], [], []
        for idf in t.idfs:
            b = BuildingTemplate.from_idf(idf)
            # with each idf, append each objects
            gms.extend(GasMaterial.from_idf(idf))
            glazms.extend(GlazingMaterial.from_idf(idf))
            oms.extend(OpaqueMaterial.from_idf(idf))
        # use set() to remove duplicates
        t.GasMaterials.extend(set(gms))
        t.GlazingMaterials.extend(set(glazms))
        t.OpaqueMaterials.extend(set(oms))

        if load:
            rundict = {idf_file: dict(eplus_file=idf_file,
                                      weather_file=weather,
                                      output_report='sql',
                                      **run_eplus_kwargs) for idf_file in
                       idf_files}
            t.sql = parallel_process(rundict, run_eplus, use_kwargs=True)
            t.read()
            t.fill()

        return t

    def fill(self):
        # Todo: Finish enumerating all UmiTempalate objects

        if self.BuildingTemplates:
            for bt in self.BuildingTemplates:
                day_schedules = [bt.all_objects[obj]
                                 for obj in bt.all_objects
                                 if 'UmiSchedule' in obj]
                self.DaySchedules.extend(day_schedules)

                dhws = [bt.all_objects[obj]
                        for obj in bt.all_objects
                        if 'DomesticHotWaterSetting' in obj]
                self.DomesticHotWaterSettings.extend(dhws)

    def read(self):
        """Initialize UMI objects"""
        # Umi stuff
        in_dict = {idf: {'Name': idf,
                         'idf': self.idfs[idf],
                         'sql': self.sql[idf]}
                   for idf in self.idfs
                   }
        for idf in in_dict:
            building_template = BuildingTemplate.from_idf(**in_dict[idf])
            self.BuildingTemplates.append(building_template)

    def run_eplus(self, idf_files, weather, **kwargs):
        """wrapper for :func:`run_eplus` function

        """
        sql_report = run_eplus(idf_files, weather, output_report='sql',
                               **kwargs)
        self.sql = sql_report

        return sql_report

    @classmethod
    def from_json(cls, filename):
        """Initializes a UmiTemplate class from a json file

        Args:
            filename (str):

        Returns:
            UmiTemplate: The template object
        """
        name = os.path.basename(filename)
        t = UmiTemplate(name)

        import json

        with open(filename, 'r') as f:
            datastore = json.load(f)

            # with datastore, create each objects
            t.GasMaterials = [GasMaterial.from_json(**store) for
                              store in datastore['GasMaterials']]
            t.GlazingMaterials = [GlazingMaterial(**store) for
                                  store in datastore["GlazingMaterials"]]
            t.OpaqueMaterials = [OpaqueMaterial(**store) for
                                 store in datastore["OpaqueMaterials"]]
            t.OpaqueConstructions = [
                OpaqueConstruction.from_json(
                    **store) for store in datastore["OpaqueConstructions"]]
            t.WindowConstructions = [
                WindowConstruction.from_json(
                    **store) for store in datastore["WindowConstructions"]]
            t.StructureDefinitions = [
                StructureDefinition.from_json(
                    **store) for store in datastore["StructureDefinitions"]]
            t.DaySchedules = [DaySchedule(**store)
                              for store in datastore["DaySchedules"]]
            t.WeekSchedules = [WeekSchedule.from_json(**store)
                               for store in datastore["WeekSchedules"]]
            t.YearSchedules = [YearSchedule.from_json(**store)
                               for store in datastore["YearSchedules"]]
            t.DomesticHotWaterSettings = [
                DomesticHotWaterSetting.from_json(**store)
                for store in datastore["DomesticHotWaterSettings"]]
            t.VentilationSettings = [
                VentilationSetting.from_json(**store)
                for store in datastore["VentilationSettings"]]
            t.ZoneConditionings = [
                ZoneConditioning.from_json(**store)
                for store in datastore["ZoneConditionings"]]
            t.ZoneConstructionSets = [
                ZoneConstructionSet.from_json(
                    **store) for store in datastore["ZoneConstructionSets"]]
            t.ZoneLoads = [ZoneLoad.from_json(**store)
                           for store in datastore["ZoneLoads"]]
            t.Zones = [Zone.from_json(**store)
                       for store in datastore["Zones"]]
            t.BuildingTemplates = [
                BuildingTemplate.from_json(**store)
                for store in datastore["BuildingTemplates"]]

            return t

    def to_json(self, path_or_buf=None, indent=2):
        """Writes the umi template to json format"""
        # todo: check is bools are created as lowercase 'false' pr 'true'

        if not path_or_buf:
            json_name = '%s.json' % self.name
            path_or_buf = os.path.join(settings.data_folder, json_name)
            # create the folder on the disk if it doesn't already exist
            if not os.path.exists(settings.data_folder):
                os.makedirs(settings.data_folder)
        with io.open(path_or_buf, 'w+', encoding='utf-8') as path_or_buf:
            data_dict = OrderedDict({'GasMaterials': [],
                                     'GlazingMaterials': [],
                                     'OpaqueMaterials': [],
                                     'OpaqueConstructions': [],
                                     'WindowConstructions': [],
                                     'StructureDefinitions': [],
                                     'DaySchedules': [],
                                     'WeekSchedules': [],
                                     'YearSchedules': [],
                                     'DomesticHotWaterSettings': [],
                                     'VentilationSettings': [],
                                     'ZoneConditionings': [],
                                     'ZoneConstructionSets': [],
                                     'ZoneLoads': [],
                                     'Zones': [],
                                     'WindowSettings': [],
                                     'BuildingTemplates': []})
            jsonized = []
            for bld in self.BuildingTemplates:
                all_objs = bld.all_objects
                for obj in all_objs:
                    if obj not in jsonized:
                        jsonized.append(obj)
                        catname = all_objs[obj].__class__.__name__ + 's'
                        app_dict = all_objs[obj].to_json()
                        data_dict[catname].append(app_dict)

            # Write the dict to json using json.dumps
            response = json.dumps(data_dict, indent=indent)
            path_or_buf.write(response)

        return response


class EnergyProfile(pd.Series):

    @property
    def _constructor(self):
        return EnergyProfile._internal_ctor

    _metadata = ['profile_type', 'base_year', 'frequency', 'is_sorted',
                 'units', 'archetypes', 'concurrent_sort']

    @classmethod
    def _internal_ctor(cls, *args, **kwargs):
        # List required arguments here
        kwargs['profile_type'] = None
        kwargs['frequency'] = None
        kwargs['units'] = None
        return cls(*args, **kwargs)

    def __init__(self, data, frequency, units, profile_type='undefinded',
                 index=None, dtype=None, copy=True, name=None,
                 fastpath=False, base_year=2017, normalize=False,
                 is_sorted=False, ascending=False, archetypes=None,
                 concurrent_sort=False):
        super(EnergyProfile, self).__init__(data=data, index=index,
                                            dtype=dtype, name=name,
                                            copy=copy, fastpath=fastpath)
        self.bin_edges_ = None
        self.bin_scaling_factors_ = None
        self.profile_type = profile_type
        self.frequency = frequency
        self.base_year = base_year
        self.units = units
        self.archetypes = archetypes
        # handle sorting of the data
        if is_sorted:
            self.is_sorted = True
            if concurrent_sort:
                self.concurrent_sort(ascending=ascending, inplace=True)
            else:
                self.sort_values(ascending=ascending, inplace=True)
        else:
            self.is_sorted = False

        # handle archetype names
        if isinstance(self.index, pd.MultiIndex):
            self.archetypes = list(set(self.index.get_level_values(level=0)))
        else:
            self.archetypes = None

        # handle normalization
        if normalize:
            self.normalize(inplace=True)

    def concurrent_sort(self, ascending=False, inplace=False, level=0):
        if isinstance(self.index, pd.MultiIndex):
            concurrent = self.unstack(level=level)
            concurrent_sum = concurrent.sum(axis=1)

            sortedIdx = concurrent_sum.sort_values(ascending=ascending).index

            result = concurrent.loc[sortedIdx, :]
            result.index = concurrent.index
            result = result.stack().swaplevel()

            if inplace:
                self._update_inplace(result)
            else:
                return result.__finalize__(self)

    def normalize(self, inplace=False):
        """Returns a normalized EnergyProfile"""
        scaler = preprocessing.MinMaxScaler()
        if self.archetypes:
            result = pd.concat({name: pd.Series(
                scaler.fit_transform(sub.values.reshape(-1, 1)).ravel()) for
                name, sub in self.groupby(level=0)}).sort_index()
            result = self._constructor(result)
        else:
            result = pd.Series(scaler.fit_transform(self.values.reshape(-1,
                                                                        1)).ravel())
            result = self._constructor(result)
        if inplace:
            self._update_inplace(result)
        else:
            return result.__finalize__(self)

    def discretize(self, n_bins=3, inplace=False, hour_of_min=None):
        """Retruns a discretized EnergyProfile"""
        try:
            from scipy.optimize import minimize
            from itertools import chain
        except ImportError:
            raise ImportError('The sklearn package must be installed to '
                              'use this optional feature.')
        if self.archetypes:
            # if multiindex, group and apply operation on each group.
            # combine at the end
            results = {}
            edges = {}
            ampls = {}
            for name, sub in self.groupby(level=0):
                if not hour_of_min:
                    hour_of_min = sub.time_at_min[1]

                sf = [1 / (i * 1.01) for i in range(1, n_bins + 1)]
                sf.extend([sub.min()])
                sf_bounds = [(0, sub.max()) for i in range(0, n_bins + 1)]
                hours = [hour_of_min - hour_of_min * 1 / (i * 1.01) for i in
                         range(1, n_bins + 1)]
                hours.extend([8760])
                hours_bounds = [(0, 8760) for i in range(0, n_bins + 1)]

                start_time = time.time()
                log('discretizing EnergyProfile {}'.format(name), lg.DEBUG)
                res = minimize(rmse, np.array(hours + sf), args=(self.values),
                               method='L-BFGS-B',
                               bounds=hours_bounds + sf_bounds,
                               options=dict(disp=True))
                log('Completed discretization in {:,.2f} seconds'.format(
                    time.time() - start_time),
                    lg.DEBUG)
                edges[name] = res.x[0:n_bins + 1]
                ampls[name] = res.x[n_bins + 1:]
                results[name] = pd.Series(piecewise(res.x))
            self.bin_edges_ = pd.Series(edges).apply(pd.Series)
            self.bin_scaling_factors_ = pd.Series(ampls).apply(pd.Series)

            result = self._constructor(pd.concat(results))
        else:
            pass
            # Todo: Implement else method
        if inplace:
            self._update_inplace(result)
        else:
            return result.__finalize__(self)

    def plot3d(self, *args, **kwargs):
        """Generate a plot of the EnergyProfile.

        If the ``column`` parameter is given, colors plot according to values
        in that column, otherwise calls ``GeoSeries.plot()`` on the
        ``geometry`` column.

        Wraps the ``plot_energyprofile()`` function, and documentation is copied
        from there.
        """
        return plot_energyprofile(self, *args, **kwargs)

    plot3d.__doc__ = plot_energyprofile.__doc__

    @property
    def p_max(self):
        if isinstance(self.index, pd.MultiIndex):
            return self.groupby(level=0).max()
        else:
            return self.max()

    @property
    def monthly(self):
        if isinstance(self.index, pd.MultiIndex):
            return self.groupby(level=0).max()
        else:
            datetimeindex = pd.date_range(freq=self.frequency,
                                          start='{}-01-01'.format(
                                              self.base_year),
                                          periods=self.size)
            self_copy = self.copy()
            self_copy.index = datetimeindex
            self_copy = self_copy.resample('M').mean()
            self_copy.frequency = 'M'
            return EnergyProfile(self_copy, frequency='M', units=self.units)

    @property
    def capacity_factor(self):
        max = self.max()
        mean = self.mean()
        return mean / max

    @property
    def bin_edges(self):
        """"""
        return self.bin_edges_

    @property
    def time_at_min(self):
        return self.idxmin()

    @property
    def bin_scaling_factors(self):
        return self.bin_scaling_factors_

    @property
    def duration_scaling_factor(self):
        # todo Complete Function
        if not self.bin_edges:
            # if never discretized,
            # run discretization with default values
            self.discretize()
        # Calculate
        a = self.bin_scaling_factors
        b = self.bin_edges
        return None


class EnergyProfiles(pd.DataFrame):

    @property
    def _constructor(self):
        return EnergyProfiles

    @property
    def _constructor_sliced(self):
        return EnergyProfile


class ReportData(pd.DataFrame):
    """This class serves as a subclass of a pandas DataFrame allowing to add
    additional functionnality"""

    ARCHETYPE = 'Archetype'
    REPORTDATAINDEX = 'ReportDataIndex'
    TIMEINDEX = 'TimeIndex'
    REPORTDATADICTIONARYINDEX = 'ReportDataDictionaryIndex'
    VALUE = 'Value'
    ISMETER = 'IsMeter'
    TYPE = 'Type'
    INDEXGROUP = 'IndexGroup'
    TIMESTEPTYPE = 'TimestepType'
    KEYVALUE = 'KeyValue'
    NAME = 'Name'
    REPORTINGFREQUENCY = 'ReportingFrequency'
    SCHEDULENAME = 'ScheduleName'
    UNITS = 'Units'

    @property
    def _constructor(self):
        return ReportData

    @property
    def schedules(self):
        return self.sorted_values(key_value='Schedule Value')

    def heating_load(self, normalize=False, sort=False, ascending=False,
                     concurrent_sort=False):
        """Returns the aggragated 'Heating:Electricity', 'Heating:Gas' and
        'Heating:DistrictHeating' of each archetype

        Args:
            normalize (bool): if True, returns a normalize Series.
                Normalization is done with respect to each Archetype
            sort (bool): if True, sorts the values. Usefull when a load
                duration curve is needed.
            ascending (bool): if True, sorts value in ascending order. If a
                Load Duration Curve is needed, use ascending=False.

        Returns:
            pd.Series: the Value series of the Heating Load with a Archetype,
                TimeIndex as MultiIndex.
        """
        hl = self.filter_report_data(name=('Heating:Electricity',
                                           'Heating:Gas',
                                           'Heating:DistrictHeating'))
        freq = list(set(hl.ReportingFrequency))
        units = list(set(hl.Units))
        if len(units) > 1:
            raise MixedUnitsError()

        hl = hl.groupby(['Archetype', 'TimeIndex']).Value.sum()
        log('Returned Heating Load in units of {}'.format(str(units)), lg.DEBUG)
        return EnergyProfile(hl, frequency=freq, units=units,
                             normalize=normalize, is_sorted=sort,
                             ascending=ascending,
                             concurrent_sort=concurrent_sort)

    def filter_report_data(self, archetype=None, reportdataindex=None,
                           timeindex=None, reportdatadictionaryindex=None,
                           value=None, ismeter=None, type=None,
                           indexgroup=None, timesteptype=None, keyvalue=None,
                           name=None, reportingfrequency=None,
                           schedulename=None, units=None, inplace=False):
        """filter RaportData using specific keywords. Each keywords can be a
        tuple of strings (str1, str2, str3) which will return the logical_or
        on the specific column.

        Args:
            archetype (str or tuple):
            reportdataindex (str or tuple):
            timeindex (str or tuple):
            reportdatadictionaryindex (str or tuple):
            value (str or tuple):
            ismeter (str or tuple):
            type (str or tuple):
            indexgroup (str or tuple):
            timesteptype (str or tuple):
            keyvalue (str or tuple):
            name (str or tuple):
            reportingfrequency (str or tuple):
            schedulename (str or tuple):
            units (str or tuple):
            inplace (str or tuple):

        Returns:
            pandas.DataFrame
        """
        start_time = time.time()
        c_n = []

        if archetype:
            c_1 = conjunction(*[self[self.ARCHETYPE] ==
                                archetype for
                                archetype in
                                archetype], logical=np.logical_or) \
                if isinstance(archetype, tuple) \
                else self[self.ARCHETYPE] == archetype
            c_n.append(c_1)
        if reportdataindex:
            c_2 = conjunction(*[self[self.REPORTDATAINDEX] ==
                                reportdataindex for
                                reportdataindex in
                                reportdataindex],
                              logical=np.logical_or) \
                if isinstance(reportdataindex, tuple) \
                else self[self.REPORTDATAINDEX] == reportdataindex
            c_n.append(c_2)
        if timeindex:
            c_3 = conjunction(*[self[self.TIMEINDEX] ==
                                timeindex for
                                timeindex in
                                timeindex],
                              logical=np.logical_or) \
                if isinstance(timeindex, tuple) \
                else self[self.TIMEINDEX] == timeindex
            c_n.append(c_3)
        if reportdatadictionaryindex:
            c_4 = conjunction(*[self[self.REPORTDATADICTIONARYINDEX] ==
                                reportdatadictionaryindex for
                                reportdatadictionaryindex in
                                reportdatadictionaryindex],
                              logical=np.logical_or) \
                if isinstance(reportdatadictionaryindex, tuple) \
                else self[self.REPORTDATADICTIONARYINDEX] == \
                     reportdatadictionaryindex
            c_n.append(c_4)
        if value:
            c_5 = conjunction(*[self[self.VALUE] ==
                                value for
                                value in
                                value], logical=np.logical_or) \
                if isinstance(value, tuple) \
                else self[self.VALUE] == value
            c_n.append(c_5)
        if ismeter:
            c_6 = conjunction(*[self[self.ISMETER] ==
                                ismeter for
                                ismeter in
                                ismeter],
                              logical=np.logical_or) \
                if isinstance(ismeter, tuple) \
                else self[self.ISMETER] == ismeter
            c_n.append(c_6)
        if type:
            c_7 = conjunction(*[self[self.TYPE] ==
                                type for
                                type in
                                type],
                              logical=np.logical_or) \
                if isinstance(type, tuple) \
                else self[self.TYPE] == type
            c_n.append(c_7)
        if indexgroup:
            c_8 = conjunction(*[self[self.INDEXGROUP] ==
                                indexgroup for
                                indexgroup in
                                indexgroup],
                              logical=np.logical_or) \
                if isinstance(indexgroup, tuple) \
                else self[self.INDEXGROUP] == indexgroup
            c_n.append(c_8)
        if timesteptype:
            c_9 = conjunction(*[self[self.TIMESTEPTYPE] ==
                                timesteptype for
                                timesteptype in
                                timesteptype],
                              logical=np.logical_or) \
                if isinstance(timesteptype, tuple) \
                else self[self.TIMESTEPTYPE] == timesteptype
            c_n.append(c_9)
        if keyvalue:
            c_10 = conjunction(*[self[self.KEYVALUE] ==
                                 keyvalue for
                                 keyvalue in
                                 keyvalue],
                               logical=np.logical_or) \
                if isinstance(keyvalue, tuple) \
                else self[self.KEYVALUE] == keyvalue
            c_n.append(c_10)
        if name:
            c_11 = conjunction(*[self[self.NAME] ==
                                 name for
                                 name in
                                 name],
                               logical=np.logical_or) \
                if isinstance(name, tuple) \
                else self[self.NAME] == name
            c_n.append(c_11)
        if reportingfrequency:
            c_12 = conjunction(*[self[self.REPORTINGFREQUENCY] ==
                                 reportingfrequency for
                                 reportingfrequency in
                                 reportingfrequency],
                               logical=np.logical_or) \
                if isinstance(reportingfrequency, tuple) \
                else self[self.REPORTINGFREQUENCY] == reportingfrequency
            c_n.append(c_12)
        if schedulename:
            c_13 = conjunction(*[self[self.SCHEDULENAME] ==
                                 schedulename for
                                 schedulename in
                                 schedulename],
                               logical=np.logical_or) \
                if isinstance(schedulename, tuple) \
                else self[self.SCHEDULENAME] == schedulename
            c_n.append(c_13)
        if units:
            c_14 = conjunction(*[self[self.UNITS] ==
                                 units for
                                 units in
                                 units], logical=np.logical_or) \
                if isinstance(units, tuple) \
                else self[self.UNITS] == units
            c_n.append(c_14)

        filtered_df = self.loc[conjunction(*c_n, logical=np.logical_and)]
        log('filtered DataFrame in {:,.2f} seconds'.format(
            time.time() - start_time))
        if inplace:
            return filtered_df._update_inplace(filtered_df)
        else:
            return filtered_df._constructor(filtered_df).__finalize__(
                filtered_df)

    def sorted_values(self, key_value=None, name=None,
                      by='TimeIndex', ascending=True):
        """Returns sorted values by filtering key_value and name

        Args:
            self: The ReporatData DataFrame
            key_value (str): key_value column filter
            name (str): name column filter
            by (str): sorting by this column name
            ascending (bool):

        Returns:
            ReportData
        """
        if key_value and name:
            return self.filter_report_data(name=name,
                                           keyvalue=key_value).sort_values(
                by=by, ascending=ascending).reset_index(drop=True).rename_axis(
                'TimeStep').set_index([
                'Archetype'], append=True).swaplevel(i=-2, j=-1, axis=0)
        else:
            return self.sort_values(by=by, inplace=False)


def conjunction(*conditions, logical=np.logical_and):
    """Applies a logical function on n conditons"""
    return functools.reduce(logical, conditions)


def mean_profile(df: ReportData):
    """calculates"""
    return df[df.SCORES].mean()


def convert_necb_to_umi_json(idfs, idfobjects=None):
    # if no list of idfobjects:
    if idfobjects is None:
        idfobjects = settings.useful_idf_objects

    for idf, idfobject in zip(idfs, idfobjects):
        print(object_from_idf(idf, idfobject))


def gas_type(row):
    """Return the UMI gas type number

    Args:
        row (pandas.DataFrame):name

    Returns:
        int: UMI gas type number. The return number is specific to the umi api.

    """
    if 'air' in row['Name'].lower():
        return 0
    elif 'argon' in row['Name'].lower():
        return 1
    elif 'krypton' in row['Name'].lower():
        return 2
    elif 'xenon' in row['Name'].lower():
        return 3
    elif 'sf6' in row['Name'].lower():
        return 4


def materials_gas(idfs):
    """Gas group

    Args:
        idfs: parsed IDF files

    Returns:
        pandas.Series: Returns a Series of GasMaterial objects
    """
    # First, get the list of materials (returns a DataFrame)
    materials_df = object_from_idfs(idfs, 'WINDOWMATERIAL:GAS')

    materials = materials_df.apply(lambda x: GasMaterial(**x), axis=1)

    log('Returning {} WINDOWMATERIAL:GAS objects'.format(len(materials)))
    return materials


def materials_glazing(idfs):
    """Material Glazing group

    Args:
        idfs (list or dict): parsed IDF files

    Returns:
        padnas.DataFrame: Returns a DataFrame with the all necessary Umi columns
    """
    origin_time = time.time()
    log('Initiating materials_glazing...')
    materials_df = object_from_idfs(idfs, 'WINDOWMATERIAL:GLAZING',
                                    first_occurrence_only=False)
    cols = settings.common_umi_objects['GlazingMaterials'].copy()
    cols.pop(0)  # remove $id
    cols.append('Thickness')
    cols.append('Archetype')
    column_rename = {'Optical_Data_Type': 'Optical',
                     'Window_Glass_Spectral_Data_Set_Name': 'OpticalData',
                     'Solar_Transmittance_at_Normal_Incidence':
                         'SolarTransmittance',
                     'Front_Side_Solar_Reflectance_at_Normal_Incidence':
                         'SolarReflectanceFront',
                     'Back_Side_Solar_Reflectance_at_Normal_Incidence':
                         'SolarReflectanceBack',
                     'Infrared_Transmittance_at_Normal_Incidence':
                         'IRTransmittance',
                     'Visible_Transmittance_at_Normal_Incidence':
                         'VisibleTransmittance',
                     'Front_Side_Visible_Reflectance_at_Normal_Incidence':
                         'VisibleReflectanceFront',
                     'Back_Side_Visible_Reflectance_at_Normal_Incidence':
                         'VisibleReflectanceBack',
                     'Front_Side_Infrared_Hemispherical_Emissivity':
                         'IREmissivityFront',
                     'Back_Side_Infrared_Hemispherical_Emissivity':
                         'IREmissivityBack',
                     'Dirt_Correction_Factor_for_Solar_and_Visible_Transmittance':
                         'DirtFactor'}
    # materials_df = materials_df.loc[materials_df.MaterialType == 10]
    materials_df = materials_df.rename(columns=column_rename)
    materials_df = materials_df.reindex(columns=cols)
    materials_df = materials_df.fillna({'DirtFactor': 1.0})
    materials_df['Comments'] = 'default'
    materials_df['Cost'] = 0
    try:
        materials_df['DataSource'] = materials_df['Archetype']
    except Exception as e:
        log('An exception was raised while setting the DataSource of the '
            'objects',
            lg.WARNING)
        log('{}'.format(e), lg.ERROR)
        log('Falling back onto first IDF file containing this common object',
            lg.WARNING)
        materials_df['DataSource'] = 'First IDF file containing this ' \
                                     'common object'

    materials_df['Density'] = 2500
    materials_df['EmbodiedCarbon'] = 0
    materials_df['EmbodiedCarbonStdDev'] = 0
    materials_df['EmbodiedEnergy'] = 0
    materials_df['EmbodiedEnergyStdDev'] = 0
    materials_df['Life'] = 1
    materials_df[
        'SubstitutionRatePattern'] = np.NaN  # TODO: ! Might have to change
    # to an empty array
    materials_df['SubstitutionTimestep'] = 0
    materials_df['TransportCarbon'] = 0
    materials_df['TransportDistance'] = 0
    materials_df['TransportEnergy'] = 0
    materials_df['Type'] = 'Uncoated'  # TODO Further investigation necessary

    materials_df = materials_df.reset_index(drop=True).rename_axis('$id')

    # Now, we create glazing materials using the
    # 'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM' objects and append them to the
    # list.
    # Trying to get simple_glazing_systems
    sgs = get_simple_glazing_system(idfs)
    if not sgs.empty:
        log('Appending to WINDOWMATERIAL:GLAZING DataFrame...')
        materials_df = materials_df.append(sgs, ignore_index=True,
                                           sort=True).reset_index(
            drop=True).rename_axis('$id')
    # Return the Dataframe
    log('Returning {} WINDOWMATERIAL:GLAZING objects in a DataFrame'.format(
        len(materials_df)))
    log('Completed materials_glazing in {:,.2f} seconds\n'.format(
        time.time() - origin_time))
    materials_df = materials_df[cols]
    materials_df.name = 'GlazingMaterials'
    return materials_df


def materials_opaque(idfs):
    """Opaque Material group

    Args:
        idfs (list or dict): parsed IDF files

    Returns:
        padnas.DataFrame: Returns a DataFrame with the all necessary Umi columns
    """
    origin_time = time.time()
    log('Initiating materials_opaque...')
    mass = object_from_idfs(idfs, 'MATERIAL')
    nomass = object_from_idfs(idfs, 'MATERIAL:NOMASS')
    materials_df = pd.concat([mass, nomass], sort=True, ignore_index=True)

    cols = settings.common_umi_objects['OpaqueMaterials'].copy()
    cols.pop(0)  # Pop $id
    cols.append('Thickness')
    cols.append('Archetype')
    cols.append('ThermalResistance')
    column_rename = {'Solar_Absorptance': 'SolarAbsorptance',
                     'Specific_Heat': 'SpecificHeat',
                     'Thermal_Absorptance': 'ThermalEmittance',
                     'Thermal_Resistance': 'ThermalResistance',
                     'Visible_Absorptance': 'VisibleAbsorptance'}
    # Rename columns
    materials_df = materials_df.rename(columns=column_rename)
    materials_df = materials_df.reindex(columns=cols)
    # Thermal_Resistance {m^2-K/W}
    materials_df['ThermalResistance'] = materials_df.apply(
        lambda x: x['Thickness'] / x['Conductivity'] if ~np.isnan(
            x['Conductivity']) else
        x['ThermalResistance'], axis=1)

    # Fill nan values (nomass materials) with defaults
    materials_df = materials_df.fillna(
        {'Thickness': 0.0127,  # half inch thickness
         'Density': 1,  # 1 kg/m3, smallest value umi allows
         'SpecificHeat': 100,  # 100 J/kg-K, smallest value umi allows
         'SolarAbsorptance': 0.7,  # default value
         'SubstitutionTimestep': 0,  # default value
         'ThermalEmittance': 0.9,  # default value
         'VariableConductivityProperties': 0,  # default value
         'VisibleAbsorptance': 0.8,  # default value
         })
    # Calculate Conductivity {W/m-K}
    materials_df['Conductivity'] = materials_df.apply(
        lambda x: x['Thickness'] / x['ThermalResistance'],
        axis=1)

    # Fill other necessary columns
    materials_df['Comments'] = 'default'
    materials_df['Cost'] = 0
    try:
        materials_df['DataSource'] = materials_df['Archetype']
    except Exception as e:
        log(
            'An exception was raised while setting the DataSource of the '
            'objects',
            lg.WARNING)
        log('{}'.format(e), lg.ERROR)
        log('Falling back onto first IDF file containing this common object',
            lg.WARNING)
        materials_df[
            'DataSource'] = 'First IDF file containing this common object'

    materials_df['EmbodiedCarbon'] = 0
    materials_df['EmbodiedCarbonStdDev'] = 0
    materials_df['EmbodiedEnergy'] = 0
    materials_df['EmbodiedEnergyStdDev'] = 0
    materials_df['Life'] = 1
    materials_df['MoistureDiffusionResistance'] = 50
    materials_df['PhaseChange'] = False
    materials_df['PhaseChangeProperties'] = ''
    # TODO: Further investigation needed
    materials_df['SubstitutionRatePattern'] = np.NaN
    # TODO: Might have to change to an empty array
    materials_df['SubstitutionTimestep'] = 0
    materials_df['TransportCarbon'] = 0
    materials_df['TransportDistance'] = 0
    materials_df['TransportEnergy'] = 0
    materials_df['Type'] = ''  # TODO: Further investigation necessary
    materials_df['VariableConductivity'] = False
    materials_df['VariableConductivityProperties'] = np.NaN
    # TODO: Further investigation necessary

    materials_df = materials_df.reset_index(drop=True).rename_axis('$id')
    log('Completed materials_opaque in {:,.2f} seconds\n'.format(
        time.time() - origin_time))
    materials_df = materials_df[cols]
    materials_df.name = 'OpaqueMaterials'
    return materials_df


def constructions_opaque(idfs, opaquematerials=None):
    """Opaque OpaqueConstruction group

    Args:
        idfs (list or dict): parsed IDF files opaquematerials
            (pandas.DataFrame): DataFrame generated by
            :func:`materials_opaque()`

    Returns:
        padnas.DataFrame: Returns a DataFrame with the all necessary Umi columns

    """
    origin_time = time.time()
    log('Initiating constructions_opaque...')
    constructions_df = object_from_idfs(idfs, 'CONSTRUCTION',
                                        first_occurrence_only=False)
    bldg_surface_detailed = object_from_idfs(idfs, 'BUILDINGSURFACE:DETAILED',
                                             first_occurrence_only=False)

    log('Joining constructions_df on bldg_surface_detailed...')
    constructions_df = bldg_surface_detailed.join(
        constructions_df.set_index(['Archetype', 'Name']),
        on=['Archetype', 'Construction_Name'], rsuffix='_constructions')

    constructions_df['Category'] = constructions_df.apply(
        lambda x: label_surface(x), axis=1)
    constructions_df['Type'] = constructions_df.apply(lambda x: type_surface(x),
                                                      axis=1)

    if opaquematerials is not None:
        start_time = time.time()
        log('Initiating constructions_opaque Layer composition...')
        df = pd.DataFrame(constructions_df.set_index(
            ['Archetype', 'Name', 'Construction_Name']).loc[:,
                          constructions_df.set_index(['Archetype', 'Name',
                                                      'Construction_Name']).columns.str.contains(
                              'Layer')].stack(), columns=['Layers']).join(
            opaquematerials.reset_index().set_index(['Archetype', 'Name']),
            on=['Archetype', 'Layers']).loc[:,
             ['$id', 'Thickness']].unstack(level=3).apply(
            lambda x: layer_composition(x), axis=1).rename('Layers')
        constructions_df = constructions_df.join(df, on=['Archetype', 'Name',
                                                         'Construction_Name'])
        log('Completed constructions_df Layer composition in {:,.2f}'
            'seconds'.format(time.time() - start_time))
    else:
        log('Could not create layer_composition because the necessary lookup '
            'DataFrame "OpaqueMaterials"  was '
            'not provided', lg.WARNING)
    cols = settings.common_umi_objects['OpaqueConstructions'].copy()

    constructions_df['AssemblyCarbon'] = 0
    constructions_df['AssemblyCost'] = 0
    constructions_df['AssemblyEnergy'] = 0
    constructions_df['Comments'] = 'default'

    try:
        constructions_df['DataSource'] = constructions_df['Archetype']
    except Exception as e:
        log('An exception was raised while setting the DataSource of the '
            'objects',
            lg.WARNING)
        log('{}'.format(e), lg.ERROR)
        log('Falling back onto first IDF file containing this common object',
            lg.WARNING)
        constructions_df['DataSource'] = 'First IDF file containing ' \
                                         'this common object'

    constructions_df['DisassemblyCarbon'] = 0
    constructions_df['DisassemblyEnergy'] = 0
    constructions_df = constructions_df.rename(
        columns={'Name': 'Zone Name'})
    constructions_df = constructions_df.rename(
        columns={'Construction_Name': 'Name'})
    constructions_df = constructions_df.reset_index(drop=True).rename_axis(
        '$id').reset_index()
    log('Completed constructions_opaque in {:,.2f} seconds\n'.format(
        time.time() - origin_time))
    constructions_df = constructions_df[cols].set_index('$id')
    constructions_df.name = 'OpaqueConstructions'
    return constructions_df


def constructions_windows(idfs, material_glazing=None):
    """Window OpaqueConstruction group

    Args:
        idfs (list or dict): parsed IDF files
        material_glazing (pandas.DataFrame): DataFrame generated by
            :func:`materials_glazing`

    Returns:
        padnas.DataFrame: Returns a DataFrame with the all necessary Umi columns

    """
    origin_time = time.time()
    log('Initiating construction_windows...')
    constructions_df = object_from_idfs(idfs, 'CONSTRUCTION',
                                        first_occurrence_only=False)
    constructions_window_df = object_from_idfs(idfs,
                                               'FENESTRATIONSURFACE:DETAILED',
                                               first_occurrence_only=False)
    constructions_window_df = constructions_window_df.join(
        constructions_df.set_index(['Archetype', 'Name']),
        on=['Archetype', 'Construction_Name'],
        rsuffix='_constructions')
    if material_glazing is not None:
        log('Initiating constructions_windows Layer composition...')
        start_time = time.time()
        df = (pd.DataFrame(constructions_window_df.set_index(
            ['Archetype', 'Name', 'Construction_Name']).loc[:,
                           constructions_window_df.set_index(
                               ['Archetype', 'Name',
                                'Construction_Name']).columns.str.contains(
                               'Layer')].stack(), columns=['Layers']).join(
            material_glazing.reset_index().set_index(['Archetype', 'Name']),
            on=['Archetype', 'Layers']).loc[:, ['$id', 'Thickness']].unstack(
            level=3).apply(lambda x: layer_composition(x), axis=1).rename(
            'Layers'))
        if not df.isna().all():
            constructions_window_df = \
                constructions_window_df.join(df, on=['Archetype',
                                                     'Name',
                                                     'Construction_Name'])
        constructions_window_df.dropna(subset=['Layers'], inplace=True)
        log('Completed constructions_window_df Layer composition in {:,'
            '.2f} seconds'.format(time.time() - start_time))
    else:
        log('Could not create layer_composition because the necessary lookup '
            'DataFrame "OpaqueMaterials"  was '
            'not provided', lg.WARNING)

    constructions_window_df.loc[:, 'AssemblyCarbon'] = 0
    constructions_window_df.loc[:, 'AssemblyCost'] = 0
    constructions_window_df.loc[:, 'AssemblyEnergy'] = 0
    constructions_window_df.loc[:, 'Category'] = 'Single'
    constructions_window_df.loc[:, 'Type'] = 2
    constructions_window_df.loc[:, 'Comments'] = 'default'

    try:
        constructions_window_df['DataSource'] = constructions_window_df[
            'Archetype']
    except Exception as e:
        log('An exception was raised while setting the DataSource of the '
            'objects',
            lg.WARNING)
        log('{}'.format(e), lg.ERROR)
        log('Falling back onto first IDF file containing this common object',
            lg.WARNING)
        constructions_window_df[
            'DataSource'] = 'First IDF file containing this common object'

    constructions_window_df.loc[:, 'DisassemblyCarbon'] = 0
    constructions_window_df.loc[:, 'DisassemblyEnergy'] = 0
    constructions_window_df.rename(columns={'Name': 'Zone Name'},
                                   inplace=True)
    constructions_window_df.rename(columns={'Construction_Name': 'Name'},
                                   inplace=True)
    constructions_window_df = constructions_window_df.reset_index(
        drop=True).rename_axis('$id').reset_index()

    cols = settings.common_umi_objects['WindowConstructions'].copy()
    cols.append('Archetype')
    log('Completed constructions_windows in {:,.2f} seconds\n'.format(
        time.time() - origin_time))
    constructions_window_df = constructions_window_df[cols].set_index('$id')
    constructions_window_df.name = 'WindowConstructions'
    return constructions_window_df


def get_simple_glazing_system(idfs):
    """Retreives all simple glazing objects from a list of IDF files. Calls
    :func:`calc_simple_glazing` in order to calculate a new glazing system that
    has the same properties.

    Args:
        idfs (list or dict): parsed IDF files

    Returns:
        pandas.DataFrame : A DataFrame

    """
    try:
        materials_df = object_from_idfs(idfs,
                                        'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM',
                                        first_occurrence_only=False)

        materials_with_sg = materials_df.set_index(['Archetype', 'Name']).apply(
            lambda row: calc_simple_glazing(row['Solar_Heat_Gain_Coefficient'],
                                            row['UFactor'],
                                            row['Visible_Transmittance']),
            axis=1).apply(pd.Series)
        materials_umi = materials_with_sg.reset_index()
        materials_umi['Optical'] = 'SpectralAverage'
        materials_umi['OpticalData'] = ''
        materials_umi['DataSource'] = materials_umi.apply(
            lambda row: apply_window_perf(row), axis=1)
        materials_umi['key'] = 'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM'
    except Exception as e:
        log('Error: {}'.format(e), lg.ERROR)
        return pd.DataFrame([])
        # return empty df since we could not find any simple glazing systems
    else:
        log('Found {} WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM objects'.format(
            len(materials_umi)))
        return materials_umi


def apply_window_perf(row):
    """Returns the string description of the window component"""
    perfs = {'shgc': row['SolarHeatGainCoefficient'],
             'ufactor': row['UFactor'],
             'tvis': row['VisibleTransmittance']}
    for perf in perfs:
        try:
            perfs[perf] = float(perfs[perf])
        except ValueError:
            perfs['tvis'] = row['SolarTransmittance']
    return 'EnergyPlus Simple Glazing Calculation shgc: {:,.2f}, u-value: ' \
           '{:,.2f}, t_vis: {:,.2f}'.format(perfs['shgc'],
                                            perfs['ufactor'],
                                            perfs['tvis'])


def nominal_domestic_hot_water_settings(idfs):
    water_use = object_from_idfs(idfs, 'WaterUse:Equipment'.upper(),
                                 first_occurrence_only=False)
    # WaterUseLEquipment can sometimes not have a Zone Name sepcified. This
    # will break the code. Users must provide one.
    condition = (water_use.Zone_Name.apply(
        lambda x: x == '') | water_use.Zone_Name.isna())
    if condition.any():
        these_ones = water_use.loc[condition, 'Archetype'].unique()
        raise ValueError('The WaterUse:Equipement Zone Name must not be '
                         'empty.\nPlease provide a Zone Name for '
                         'WaterUse:Equipement in idfs: '
                         '{}\nbefore rerunning this function'.format(
            these_ones))

    # Make sure the Zone_Name is in capitals
    water_use.Zone_Name = water_use.Zone_Name.str.upper()

    # check if multiple WaterUse:Equipment for one zone.
    # Todo: Multiple WaterUse:Equipement for the same zone should be
    #  aggragated: PeakLoads summed and schedules merged.
    to_drop = water_use.groupby(['Archetype', 'Zone_Name']).apply(lambda x:
                                                                  x.duplicated(
                                                                      subset='Zone_Name')).reset_index()
    water_use = water_use.loc[~to_drop[0], :]

    return water_use


def zone_domestic_hot_water_settings(df, idfs):
    d = {'Zone': zone_information(df).reset_index().set_index(['Archetype',
                                                               'Zone Name']),
         'NominalDhw': nominal_domestic_hot_water_settings(idfs).reset_index(
         ).set_index([
             'Archetype', 'Zone_Name'])}
    df = (pd.concat(d, axis=1, keys=d.keys())
          .dropna(axis=0, how='all',
                  subset=[('Zone', 'Type')])  # Drop rows that are all nans
          .rename_axis(['Archetype', 'Zone Name'])
          .reset_index(level=1, col_level=1,
                       col_fill='Zone')  # Reset Index level to get Zone Name
          .reset_index().set_index(['Archetype', ('Zone', 'RowName')])
          .rename_axis(['Archetype', 'RowName']))

    df[('Zone', 'Zone Type')] = df.apply(lambda x: iscore(x), axis=1)

    df = df.reset_index().groupby(['Archetype', ('Zone', 'Zone Type')]).apply(
        lambda x: domestichotwatersettings_aggregation(x.set_index([
            'Archetype', 'RowName'])))
    df.name = 'DomesticHotWaterSettings'

    return df


def domestichotwatersettings_aggregation(x):
    area_m_ = [('Zone', 'Floor Area {m2}'),
               ('Zone', 'Zone Multiplier')]  # Floor area and zone_loads
    # multiplier
    d = {('FlowRatePerFloorArea', 'weighted mean'):
             weighted_mean(x[('NominalDhw', 'Peak_Flow_Rate')] * 3600,
                           x, area_m_),
         ('FlowRatePerFloorArea', 'top'):
             top(x[('NominalDhw', 'Flow_Rate_Fraction_Schedule_Name')],
                 x, area_m_)
         }

    return pd.Series(d)


def zone_loads(df):
    """Takes the sql reports (as a dict of DataFrames), concatenates all
    relevant 'Initialization Summary' tables and
    applies a series of aggragation functions (weighted means and "top").

    Args:
        df (dict): A dict of pandas.DataFrames

    Returns:
        pandas.DataFrame : A new DataFrame with aggragated values

    """
    # Loading each section in a dictionnary. Used to create a new DF using
    # pd.concat()
    d = {'Zone': zone_information(df).reset_index().set_index(['Archetype',
                                                               'Zone Name']),
         'NominalLighting': nominal_lighting(df).reset_index().set_index(
             ['Archetype', 'Zone Name']),
         'NominalPeople': nominal_people(df).reset_index().set_index(
             ['Archetype', 'Zone Name']),
         'NominalInfiltration': nominal_infiltration(
             df).reset_index().set_index(['Archetype', 'Zone Name']),
         'NominalEquipment': nominal_equipment(df).reset_index().set_index(
             ['Archetype', 'Zone Name'])}

    df = (pd.concat(d, axis=1, keys=d.keys())
          .dropna(axis=0, how='all',
                  subset=[('Zone', 'Type')])  # Drop rows that are all nans
          .reset_index(level=1, col_level=1,
                       col_fill='Zone')  # Reset Index level to get Zone Name
          .reset_index().set_index(['Archetype', ('Zone', 'RowName')])
          .rename_axis(['Archetype', 'RowName']))

    df[('Zone', 'Zone Type')] = df.apply(lambda x: iscore(x), axis=1)

    df = df.reset_index().groupby(['Archetype', ('Zone', 'Zone Type')]).apply(
        lambda x: zoneloads_aggregation(x.set_index(['Archetype', 'RowName'])))
    df.name = 'ZoneLoads'
    return df


def zone_ventilation(df):
    """Takes the sql reports (as a dict of DataFrames), concatenates all
    relevant 'Initialization Summary' tables and
    applies a series of aggragation functions (weighted means and "top").

    Args:
        df (dict): A dict of pandas.DataFrames

    Returns:
        pandas.DataFrame:

    """
    # Loading each section in a dictionnary. Used to create a new DF using
    # pd.concat()

    z_info = zone_information(df).reset_index().set_index(['Archetype',
                                                           'Zone Name'])

    _nom_infil = nominal_infiltration(df)
    nom_infil = (_nom_infil.reset_index().set_index(['Archetype',
                                                     'Zone Name'])
                 if not _nom_infil.empty else None)
    _nom_vent = nominal_ventilation(df)
    nom_vent = (_nom_vent.reset_index().set_index(['Archetype',
                                                   'Zone Name']).loc[
                lambda e: e['Fan Type {Exhaust;Intake;Natural}']
                .str.contains('Natural'), :]
                if not _nom_vent.empty else None)
    _nom_natvent = _nom_vent  # we can reuse _nom_vent
    nom_natvent = (_nom_natvent.reset_index().set_index(['Archetype',
                                                         'Zone Name']).loc[
                   lambda e: ~e['Fan Type {Exhaust;Intake;Natural}']
                   .str.contains('Natural'), :]
                   if not _nom_vent.empty else None)
    d = {'Zone': z_info,
         'NominalInfiltration': nom_infil,
         'NominalScheduledVentilation': nom_vent,
         'NominalNaturalVentilation': nom_natvent}

    df = (pd.concat(d, axis=1, keys=d.keys())
          .dropna(axis=0, how='all',
                  subset=[('Zone', 'Type')])  # Drop rows that are all nans
          .reset_index(level=1, col_level=1,
                       col_fill='Zone')  # Reset Index level to get Zone Name
          .reset_index().set_index(['Archetype', ('Zone', 'RowName')])
          .rename_axis(['Archetype', 'RowName']))

    df[('Zone', 'Zone Type')] = df.apply(lambda x: iscore(x), axis=1)

    df_g = df.reset_index().groupby(['Archetype', ('Zone', 'Zone Type')])
    log('{} groups in zone ventiliation aggregation'.format(len(df_g)))
    log('groups are:\n{}'.format(pformat(df_g.groups, indent=3)))
    df = df_g.apply(lambda x: zoneventilation_aggregation(
        x.set_index(['Archetype', 'RowName'])))

    return df


def zoneloads_aggregation(x):
    """Set of different zoneloads_aggregation (weighted mean and "top") on
    multiple objects, eg. ('NominalLighting',
    'Lights/Floor Area {W/m2}').

    All the DataFrame is passed to each function.

    Returns a Series with a MultiIndex

    Args:
        x (pandas.DataFrame):

    Returns:
        pandas.Series: Series with a MultiIndex

    """
    area_m_ = [('Zone', 'Floor Area {m2}'),
               ('Zone',
                'Zone Multiplier')]  # Floor area and zone_loads multiplier
    d = {('NominalLighting', 'weighted mean'):
             weighted_mean(x[('NominalLighting', 'Lights/Floor Area {W/m2}')],
                           x, area_m_),
         ('NominalLighting', 'top'):
             top(x[('NominalLighting', 'Schedule Name')],
                 x, area_m_),
         ('NominalPeople', 'weighted mean'):
             weighted_mean(
                 x[('NominalPeople', 'People/Floor Area {person/m2}')],
                 x, area_m_),
         ('NominalPeople', 'top'):
             top(x[('NominalPeople', 'Schedule Name')],
                 x, area_m_),
         ('NominalEquipment', 'weighted mean'):
             weighted_mean(
                 x[('NominalEquipment', 'Equipment/Floor Area {W/m2}')],
                 x, area_m_),
         ('NominalEquipment', 'top'):
             top(x[('NominalEquipment', 'Schedule Name')],
                 x, area_m_)
         }

    d['']

    return pd.Series(d)


def zoneventilation_aggregation(df):
    """Set of different zoneventilation_aggregation (weighted mean and "top")
    on multiple objects, eg. ('NominalVentilation', 'ACH - Air Changes per
    Hour').

    All the DataFrame is passed to each function.

    Args:
        df (pandas.DataFrame):

    Returns:
        (pandas.Series): Series with a MultiIndex

    Todo: infiltration for plenums should not be taken into account

    """
    log('\naggregating zone ventilations '
        'for archetype "{}", zone "{}"'.format(df.index.values[0][0],
                                               df[('Zone',
                                                   'Zone Type')].values[0]))

    area_m_ = [('Zone', 'Floor Area {m2}'),
               ('Zone', 'Zone Multiplier')]  # Floor area and zone_loads
    # multiplier

    ach_ = safe_loc(df, ('NominalInfiltration',
                         'ACH - Air Changes per Hour'))
    infil_schedule_name_ = safe_loc(df, ('NominalInfiltration',
                                         'Schedule Name'))
    changes_per_hour_ = safe_loc(df, ('NominalScheduledVentilation',
                                      'ACH - Air Changes per Hour'))
    vent_schedule_name_ = safe_loc(df, ('NominalScheduledVentilation',
                                        'Schedule Name'))
    vent_min_temp_ = safe_loc(df, ('NominalScheduledVentilation',
                                   'Minimum Indoor Temperature{C}/Schedule'))
    natvent_ach_ = safe_loc(df, ('NominalNaturalVentilation',
                                 'ACH - Air Changes per Hour'))
    natvent_schedule_name_ = safe_loc(df, ('NominalNaturalVentilation',
                                           'Schedule Name'))
    natvent_max_temp_ = safe_loc(df, ('NominalNaturalVentilation',
                                      'Maximum Outdoor Temperature{'
                                      'C}/Schedule'))
    natvent_minoutdoor_temp_ = safe_loc(df, ('NominalNaturalVentilation',
                                             'Minimum Outdoor Temperature{'
                                             'C}/Schedule'))
    natvent_minindoor_temp_ = safe_loc(df, ('NominalNaturalVentilation',
                                            'Minimum Indoor Temperature{'
                                            'C}/Schedule'))
    d = {
        ('Infiltration', 'weighted mean {ACH}'): (
            weighted_mean(ach_, df, area_m_)),
        ('Infiltration', 'Top Schedule Name'): (
            top(infil_schedule_name_, df, area_m_)),
        ('ScheduledVentilation', 'weighted mean {ACH}'): (
            weighted_mean(changes_per_hour_, df, area_m_)),
        ('ScheduledVentilation', 'Top Schedule Name'): (
            top(vent_schedule_name_, df, area_m_)),
        ('ScheduledVentilation', 'Setpoint'): (
            top(vent_min_temp_, df, area_m_)),
        ('NatVent', 'weighted mean {ACH}'): (
            weighted_mean(natvent_ach_, df, area_m_)),
        ('NatVent', 'Top Schedule Name'): (
            top(natvent_schedule_name_, df, area_m_)),
        ('NatVent', 'MaxOutdoorAirTemp'): (
            top(natvent_max_temp_, df, area_m_)),
        ('NatVent', 'MinOutdoorAirTemp'): (
            top(natvent_minoutdoor_temp_, df, area_m_)),
        ('NatVent', 'ZoneTempSetpoint'): (
            top(natvent_minindoor_temp_, df, area_m_))}

    return pd.Series(d)


def safe_loc(x, colnames):
    try:
        ach = x[colnames]
    except KeyError:
        log('No such columns {} in DataFrame'.format(str(colnames)))
        return pd.Series([], name=colnames)
    else:
        return ach


def nominal_lighting(df):
    """Nominal lighting

    Args:
        df:

    Returns:
        df

    References:
        * `NominalLighting Table \
        <https://bigladdersoftware.com/epx/docs/8-9/output-details-and \
        -examples/eplusout-sql.html#nominallighting-table>`_

    """
    df = get_from_tabulardata(df)
    tbstr = df[(df.ReportName == 'Initialization Summary') &
               (df.TableName == 'Lights Internal Gains Nominal')].reset_index()

    tbpiv = tbstr.pivot_table(index=['Archetype', 'RowName'],
                              columns='ColumnName',
                              values='Value',
                              aggfunc=lambda x: ' '.join(x))
    tbpiv = tbpiv.replace({'N/A': np.nan}).apply(
        lambda x: pd.to_numeric(x, errors='ignore'))
    tbpiv = tbpiv.reset_index().groupby(['Archetype', 'Zone Name']).apply(
        nominal_lighting_aggregation)
    return tbpiv.reset_index().groupby(['Archetype', 'Zone Name']).agg(
        lambda x: pd.to_numeric(x, errors='ignore').sum())


def nominal_people(df):
    """Nominal People

    Args:
        df:

    Returns:
        df

    References:
        * `NominalPeople Table \
        <https://bigladdersoftware.com/epx/docs/8-9/output-details-and- \
        examples/eplusout-sql.html#nominalpeople-table>`_

    """
    df = get_from_tabulardata(df)
    tbstr = df[(df.ReportName == 'Initialization Summary') &
               (df.TableName == 'People Internal Gains Nominal')].reset_index()

    tbpiv = tbstr.pivot_table(index=['Archetype', 'RowName'],
                              columns='ColumnName',
                              values='Value',
                              aggfunc=lambda x: ' '.join(x))
    tbpiv.replace({'N/A': np.nan}, inplace=True)
    return tbpiv.reset_index().groupby(['Archetype', 'Zone Name']).agg(
        lambda x: pd.to_numeric(x, errors='ignore').sum())


def nominal_equipment(df):
    """Nominal Electric Equipment

    Args:
        df:

    Returns:
        df

    References:
        * `NominalElectricEquipment Table \
        <https://bigladdersoftware.com/epx/docs/8-9/output-details-and \
        -examples/eplusout-sql.html#nominalelectricequipment-table>`_ \

    """
    df = get_from_tabulardata(df)
    tbstr = df[(df.ReportName == 'Initialization Summary') &
               (df.TableName == 'ElectricEquipment Internal Gains '
                                'Nominal')].reset_index()

    tbpiv = tbstr.pivot_table(index=['Archetype', 'RowName'],
                              columns='ColumnName',
                              values='Value',
                              aggfunc=lambda x: ' '.join(x))
    tbpiv = tbpiv.replace({'N/A': np.nan}).apply(
        lambda x: pd.to_numeric(x, errors='ignore'))
    tbpiv = tbpiv.reset_index().groupby(['Archetype', 'Zone Name']).apply(
        nominal_equipment_aggregation)
    return tbpiv


def nominal_infiltration(df):
    """Nominal Infiltration

    Args:
        df:

    Returns:
        df

    References:
        * `Nominal Infiltration Table \
        <https://bigladdersoftware.com/epx/docs/8-9/output-details-and \
        -examples/eplusout-sql.html#nominalinfiltration-table>`_

    """
    df = get_from_tabulardata(df)
    tbstr = df[(df.ReportName == 'Initialization Summary') &
               (df.TableName == 'ZoneInfiltration Airflow Stats '
                                'Nominal')].reset_index()

    tbpiv = tbstr.pivot_table(index=['Archetype', 'RowName'],
                              columns='ColumnName',
                              values='Value',
                              aggfunc=lambda x: ' '.join(x))
    tbpiv.replace({'N/A': np.nan}, inplace=True)
    return tbpiv.reset_index().groupby(['Archetype', 'Zone Name']).agg(
        lambda x: pd.to_numeric(x, errors='ignore').sum())


def nominal_ventilation(df):
    """Nominal Ventilation

    Args:
        df:

    Returns:
        df

    References:
        * `Nominal Ventilation Table \
        <https://bigladdersoftware.com/epx/docs/8-9/output-details-and \
        -examples/eplusout-sql.html#nominalventilation-table>`_

    """
    df = get_from_tabulardata(df)
    report_name = 'Initialization Summary'
    table_name = 'ZoneVentilation Airflow Stats Nominal'
    tbstr = df[(df.ReportName == report_name) &
               (df.TableName == table_name)] \
        .reset_index()
    if tbstr.empty:
        log('Table {} does not exist. '
            'Returning an empty DataFrame'.format(table_name), lg.WARNING)
        return pd.DataFrame([])
    tbpiv = tbstr.pivot_table(index=['Archetype', 'RowName'],
                              columns='ColumnName',
                              values='Value',
                              aggfunc=lambda x: ' '.join(x))

    tbpiv = tbpiv.replace({'N/A': np.nan}).apply(
        lambda x: pd.to_numeric(x, errors='ignore'))
    tbpiv = tbpiv.reset_index().groupby(['Archetype',
                                         'Zone Name',
                                         'Fan Type {Exhaust;Intake;Natural}']) \
        .apply(nominal_ventilation_aggregation)
    return tbpiv
    # .reset_index().groupby(['Archetype', 'Zone Name']).agg(
    # lambda x: pd.to_numeric(x, errors='ignore').sum())


def nominal_lighting_aggregation(x):
    """Aggregates the lighting equipments whithin a single zone_loads name (
    implies that .groupby(['Archetype', 'Zone Name']) is performed before
    calling this function).

    Args:
        x (pandas.DataFrame): x

    Returns:
        pandas.DataFrame: A DataFrame with at least one entry per (
        'Archetype', 'Zone Name'), aggregated accordingly.

    """
    how_dict = {'# Zone Occupants': x['# Zone Occupants'].sum(),
                'End-Use Category': top(x['End-Use Category'],
                                        x, 'Zone Floor Area {m2}'),
                'Fraction Convected': weighted_mean(x['Fraction Convected'],
                                                    x, 'Lighting Level {W}'),
                'Fraction Radiant': weighted_mean(x['Fraction Radiant'],
                                                  x, 'Lighting Level {W}'),
                'Fraction Replaceable': weighted_mean(x['Fraction Replaceable'],
                                                      x, 'Lighting Level {W}'),
                'Fraction Return Air': weighted_mean(x['Fraction Return Air'],
                                                     x, 'Lighting Level {W}'),
                'Fraction Short Wave': weighted_mean(x['Fraction Short Wave'],
                                                     x, 'Lighting Level {W}'),
                'Lighting Level {W}': x['Lighting Level {W}'].sum(),
                'Lights per person {W/person}': x[
                    'Lights per person {W/person}'].sum(),
                'Lights/Floor Area {W/m2}': x['Lights/Floor Area {W/m2}'].sum(),
                'Name': '+'.join(x['Name']),
                'Nominal Maximum Lighting Level {W}': x[
                    'Nominal Maximum Lighting Level {W}'].sum(),
                'Nominal Minimum Lighting Level {W}': x[
                    'Nominal Minimum Lighting Level {W}'].sum(),
                'Schedule Name': top(x['Schedule Name'], x,
                                     'Lighting Level {W}'),
                # todo: The schedule could be an aggregation by itself
                'Zone Floor Area {m2}': x['Zone Floor Area {m2}'].sum()}

    try:
        df = pd.DataFrame(how_dict, index=range(0, 1))  # range should always be
        # one since we are trying to merge zones
    except Exception as e:
        print('{}'.format(e))
    return df


def nominal_equipment_aggregation(x):
    """Aggregates the equipments whithin a single zone_loads name (implies that
    .groupby(['Archetype', 'Zone Name']) is
    performed before calling this function).

    Args:
        x (pandas.DataFrame): x

    Returns:
        pandas.DataFrame: A DataFrame with at least one entry per
            ('Archetype', 'Zone Name'), aggregated accordingly.

    """
    how_dict = {'# Zone Occupants': x['# Zone Occupants'].sum(),
                'End-Use SubCategory': top(x['End-Use SubCategory'],
                                           x, 'Zone Floor Area {m2}'),
                'Equipment Level {W}': x['Equipment Level {W}'].sum(),
                'Equipment per person {W/person}': x[
                    'Equipment per person {W/person}'].sum(),
                'Equipment/Floor Area {W/m2}': x[
                    'Equipment/Floor Area {W/m2}'].sum(),
                'Fraction Convected': weighted_mean(x['Fraction Convected'],
                                                    x, 'Equipment Level {W}'),
                'Fraction Latent': weighted_mean(x['Fraction Latent'],
                                                 x, 'Equipment Level {W}'),
                'Fraction Lost': weighted_mean(x['Fraction Lost'],
                                               x, 'Equipment Level {W}'),
                'Fraction Radiant': weighted_mean(x['Fraction Radiant'],
                                                  x, 'Equipment Level {W}'),
                'Name': '+'.join(x['Name']),
                'Nominal Maximum Equipment Level {W}': x[
                    'Nominal Maximum Equipment Level {W}'].sum(),
                'Nominal Minimum Equipment Level {W}': x[
                    'Nominal Minimum Equipment Level {W}'].sum(),
                'Schedule Name': top(x['Schedule Name'], x,
                                     'Equipment Level {W}'),
                # todo: The schedule could be an aggregation by itself
                'Zone Floor Area {m2}': x['Zone Floor Area {m2}'].sum()}

    try:
        df = pd.DataFrame(how_dict, index=range(0, 1))  # range should always be
        # one since we are trying to merge zones
    except Exception as e:
        print('{}'.format(e))
    return df


def nominal_ventilation_aggregation(x):
    """Aggregates the ventilations whithin a single zone_loads name (implies
    that
    .groupby(['Archetype', 'Zone Name']) is
    performed before calling this function).

    Args:
        x:

    Returns:
        A DataFrame with at least one entry per ('Archetype', 'Zone Name'),
        aggregated accordingly.
    """
    how_dict = {'Name': top(x['Name'],
                            x, 'Zone Floor Area {m2}'),
                'Schedule Name': top(x['Schedule Name'],
                                     x, 'Zone Floor Area {m2}'),
                'Zone Floor Area {m2}': top(x['Zone Floor Area {m2}'],
                                            x, 'Zone Floor Area {m2}'),
                '# Zone Occupants': top(x['# Zone Occupants'],
                                        x, 'Zone Floor Area {m2}'),
                'Design Volume Flow Rate {m3/s}': weighted_mean(
                    x['Design Volume Flow Rate {m3/s}'],
                    x, 'Zone Floor Area {m2}'),
                'Volume Flow Rate/Floor Area {m3/s/m2}': weighted_mean(
                    x['Volume Flow Rate/Floor Area {m3/s/m2}'],
                    x, 'Zone Floor Area {m2}'),
                'Volume Flow Rate/person Area {m3/s/person}': weighted_mean(
                    x['Volume Flow Rate/person Area {m3/s/person}'],
                    x, 'Zone Floor Area {m2}'),
                'ACH - Air Changes per Hour': weighted_mean(
                    x['ACH - Air Changes per Hour'],
                    x, 'Zone Floor Area {m2}'),
                'Fan Pressure Rise {Pa}': weighted_mean(
                    x['Fan Pressure Rise {Pa}'],
                    x, 'Zone Floor Area {m2}'),
                'Fan Efficiency {}': weighted_mean(x['Fan Efficiency {}'],
                                                   x, 'Zone Floor Area {m2}'),
                'Equation A - Constant Term Coefficient {}': top(
                    x['Equation A - Constant Term Coefficient {}'],
                    x, 'Zone Floor Area {m2}'),
                'Equation B - Temperature Term Coefficient {1/C}': top(
                    x['Equation B - Temperature Term Coefficient {1/C}'],
                    x, 'Zone Floor Area {m2}'),
                'Equation C - Velocity Term Coefficient {s/m}': top(
                    x['Equation C - Velocity Term Coefficient {s/m}'],
                    x, 'Zone Floor Area {m2}'),
                'Equation D - Velocity Squared Term Coefficient {s2/m2}': top(
                    x['Equation D - Velocity Squared Term Coefficient {s2/m2}'],
                    x, 'Zone Floor Area {m2}'),
                'Minimum Indoor Temperature{C}/Schedule': top(
                    x['Minimum Indoor Temperature{C}/Schedule'],
                    x, 'Zone Floor Area {m2}'),
                'Maximum Indoor Temperature{C}/Schedule': top(
                    x['Maximum Indoor Temperature{C}/Schedule'],
                    x, 'Zone Floor Area {m2}'),
                'Delta Temperature{C}/Schedule': top(
                    x['Delta Temperature{C}/Schedule'],
                    x, 'Zone Floor Area {m2}'),
                'Minimum Outdoor Temperature{C}/Schedule': top(
                    x['Minimum Outdoor Temperature{C}/Schedule'],
                    x, 'Zone Floor Area {m2}'),
                'Maximum Outdoor Temperature{C}/Schedule': top(
                    x['Maximum Outdoor Temperature{C}/Schedule'],
                    x, 'Zone Floor Area {m2}'),
                'Maximum WindSpeed{m/s}': top(x['Maximum WindSpeed{m/s}'],
                                              x, 'Zone Floor Area {m2}')}
    try:
        df = pd.DataFrame(how_dict, index=range(0, 1))  # range should always be
        # one since we are trying to merge zones
    except Exception as e:
        print('{}'.format(e))
    else:
        return df


def get_from_tabulardata(results):
    """Returns a DataFrame from the 'TabularDataWithStrings' table. A
    multiindex is returned with names ['Archetype', 'Index']

    Args:
        results:

    Returns:

    """
    tab_data_wstring = pd.concat(
        [value['TabularDataWithStrings'] for value in results.values()],
        keys=results.keys(), names=['Archetype'])
    tab_data_wstring.index.names = ['Archetype', 'Index']  #
    # strip whitespaces
    tab_data_wstring.Value = tab_data_wstring.Value.str.strip()
    tab_data_wstring.RowName = tab_data_wstring.RowName.str.strip()
    return tab_data_wstring


def get_from_reportdata(results):
    """Returns a DataFrame from the 'ReportData' table. A multiindex is
    returned with names ['Archetype', 'Index']

    Args:
        results:

    Returns:

    """
    report_data = pd.concat([value['ReportData'] for value in results.values()],
                            keys=results.keys(), names=['Archetype'])
    report_data['ReportDataDictionaryIndex'] = pd.to_numeric(
        report_data['ReportDataDictionaryIndex'])

    report_data_dict = pd.concat(
        [value['ReportDataDictionary'] for value in results.values()],
        keys=results.keys(), names=['Archetype'])

    return report_data.reset_index().join(report_data_dict,
                                          on=['Archetype',
                                              'ReportDataDictionaryIndex'])


def zone_information(df):
    """Each zone_loads is summarized in a simple set of statements

    Args:
        df:

    Returns:
        df

    References:
        * `Zone Loads Information \
        <https://bigladdersoftware.com/epx/docs/8-3/output-details-and \
        -examples/eplusout.eio.html#zone_loads-information>`_

    """
    df = get_from_tabulardata(df)
    tbstr = df[(df.ReportName == 'Initialization Summary') &
               (df.TableName == 'Zone Information')].reset_index()
    # Ignore Zone that are not part of building area
    pivoted = tbstr.pivot_table(index=['Archetype', 'RowName'],
                                columns='ColumnName',
                                values='Value',
                                aggfunc=lambda x: ' '.join(x))

    return pivoted.loc[pivoted['Part of Total Building Area'] == 'Yes', :]


def zoneconditioning_aggregation(x):
    """Aggregates the zones conditioning parameters whithin a single zone_loads
    name (implies that `.groupby(['Archetype',
    ('Zone', 'Zone Type')])` is performed before calling this function).

    Args:
        x:

    Returns:

    """
    d = {}
    area_m_ = [('Zone', 'Zone Multiplier'), ('Zone', 'Floor Area {m2}')]

    d[('COP Heating', 'weighted mean {}')] = (
        weighted_mean(x[('COP', 'COP Heating')],
                      x, area_m_))

    d[('COP Cooling', 'weighted mean {}')] = (
        weighted_mean(x[('COP', 'COP Cooling')],
                      x, area_m_))

    d[('ZoneCooling', 'designday')] = \
        np.nanmean(x.loc[x[(
            'ZoneCooling', 'Thermostat Setpoint Temperature at Peak Load')] > 0,
                         ('ZoneCooling',
                          'Thermostat Setpoint Temperature at Peak Load')])

    d[('ZoneHeating', 'designday')] = \
        np.nanmean(x.loc[x[(
            'ZoneHeating', 'Thermostat Setpoint Temperature at Peak Load')] > 0,
                         ('ZoneHeating',
                          'Thermostat Setpoint Temperature at Peak Load')])

    d[('MinFreshAirPerArea', 'weighted average {m3/s-m2}')] = \
        max(weighted_mean(
            x[('ZoneCooling', 'Minimum Outdoor Air Flow Rate')].astype(float)
            / x.loc[:, ('Zone', 'Floor Area {m2}')].astype(float),
            x,
            area_m_),
            weighted_mean(
                x[('ZoneHeating', 'Minimum Outdoor Air Flow Rate')].astype(
                    float)
                / x[('Zone', 'Floor Area {m2}')].astype(float),
                x,
                area_m_))

    d[('MinFreshAirPerPerson', 'weighted average {m3/s-person}')] = \
        max(weighted_mean(
            x[('ZoneCooling', 'Minimum Outdoor Air Flow Rate')].astype(float)
            / x[('NominalPeople', '# Zone Occupants')].astype(float),
            x,
            area_m_),
            weighted_mean(
                x[('ZoneHeating', 'Minimum Outdoor Air Flow Rate')].astype(
                    float)
                / x[('NominalPeople', '# Zone Occupants')].astype(float),
                x,
                area_m_))
    return pd.Series(d)


def zone_cop(df):
    """Returns the heating and cooling COP for each zones. The energyplus SQL
    result must contain some required meters as described bellow. Also requires
    a full year simulation.

    Todo:
        * We could check if the meters are included in the IDF file.

    Args:
        df (pandas.DataFrame):

    Returns:


    Notes:

        Mandatory Output Meters

        Heating

        - Air System Total Heating Energy
        - Heating:Electricity
        - Heating:Gas
        - Heating:DistrictHeating

        Cooling

        - Air System Total Cooling Energy
        - Cooling:Electricity
        - Cooling:Gas
        - Cooling:DistrictCooling

    """
    # Heating Energy
    rdf = ReportData(get_from_reportdata(df))
    heating = rdf.filter_report_data(
        name='Air System Total Heating Energy').reset_index()
    heating_out_sys = heating.groupby(['Archetype', 'KeyValue']).sum()['Value']
    heating_out = heating.groupby(['Archetype']).sum()['Value']
    nu_heating = heating_out_sys / heating_out
    heating_in = rdf.filter_report_data(name=('Heating:Electricity',
                                              'Heating:Gas',
                                              'Heating:DistrictHeating')).groupby(
        ['Archetype', 'TimeIndex']).Value.sum()
    heating_in = EnergyProfile(heating_in, frequency='1H', units='J',
                               is_sorted=False, concurrent_sort=False)

    # Cooling Energy
    cooling = rdf.filter_report_data(
        name='Air System Total Cooling Energy').reset_index()
    cooling_out_sys = cooling.groupby(['Archetype', 'KeyValue']).sum()['Value']
    cooling_out = cooling.groupby(['Archetype']).sum()['Value']
    nu_cooling = cooling_out_sys / cooling_out
    cooling_in = rdf.filter_report_data(name=('Cooling:Electricity',
                                              'Cooling:Gas',
                                              'Cooling:DistrictCooling')).groupby(
        ['Archetype', 'TimeIndex']).Value.sum()
    cooling_in = EnergyProfile(cooling_in, frequency='1H', units='J',
                               is_sorted=False, concurrent_sort=False)

    d = {'Heating': heating_out_sys / (nu_heating * heating_in.sum(
        level='Archetype')),
         'Cooling': cooling_out_sys / (nu_cooling * cooling_in.sum(
             level='Archetype'))}

    # Zone to system correspondence
    df = get_from_tabulardata(df).loc[
        ((lambda e: e.ReportName == 'Standard62.1Summary') and
         (lambda e: e.TableName == 'System Ventilation Parameters') and
         (lambda e: e.ColumnName == 'AirLoop Name')), ['RowName',
                                                       'Value']].reset_index()
    df.rename(columns={'RowName': 'Zone Name', 'Value': 'System Name'},
              inplace=True)
    df.loc[:, 'COP Heating'] = \
        df.join(d['Heating'], on=['Archetype', 'System Name'])['Value']
    df.loc[:, 'COP Cooling'] = \
        df.join(d['Cooling'], on=['Archetype', 'System Name'])['Value']
    df.drop(columns='Index', inplace=True)
    return df.groupby(['Archetype', 'Zone Name']).mean()


def zone_setpoint(df):
    """Zone heating and cooling setpoints. Since we can't have a schedule
    setpoint in Umi, we return the "Design Day" 'Thermostat Setpoint Temperature
    at 'Peak Load'

    Args:
        df (pandas.DataFrame): df

    Returns:
        DataFrame of Zone Setpoints for Cooling and Heating
    """
    df = get_from_tabulardata(df)
    tbstr_cooling = df[(df.ReportName == 'HVACSizingSummary') &
                       (df.TableName == 'Zone Sensible Cooling')].reset_index()
    tbpiv_cooling = tbstr_cooling.pivot_table(index=['Archetype', 'RowName'],
                                              columns='ColumnName',
                                              values='Value',
                                              aggfunc=lambda x: ' '.join(
                                                  x)).replace(
        {'N/A': np.nan}).apply(
        lambda x: pd.to_numeric(x, errors='ignore'))
    tbstr_heating = df[(df.ReportName == 'HVACSizingSummary') &
                       (df.TableName == 'Zone Sensible Heating')].reset_index()
    tbpiv_heating = tbstr_heating.pivot_table(index=['Archetype', 'RowName'],
                                              columns='ColumnName',
                                              values='Value',
                                              aggfunc=lambda x: ' '.join(
                                                  x)).replace(
        {'N/A': np.nan}).apply(
        lambda x: pd.to_numeric(x, errors='ignore'))
    cd = pd.concat([tbpiv_cooling, tbpiv_heating], keys=['cooling', 'heating'],
                   axis=1)
    cd.index.names = ['Archetype', 'Zone Name']
    return cd


def zone_conditioning(df):
    """Aggregation of zone_loads conditioning parameters. Imports Zone,
    NominalPeople, COP, ZoneCooling and ZoneHeating.

    Args:
        df (pandas.DataFrame): df

    Returns:
        DataFrame of Zone Condition parameters

    Examples:
        .. doctest:: *

            # >>> df = ar.run_eplus([./examples/zoneuncontrolled.idf],
            # >>> output_report='sql')
            # >>> zone_conditioning(df)

    """
    # Loading each section in a dictionnary. Used to create
    # a new DF using pd.concat()
    d = {'Zone': zone_information(df).reset_index().set_index(
        ['Archetype', 'Zone Name']),
        'NominalPeople': nominal_people(df).reset_index().set_index(
            ['Archetype', 'Zone Name']),
        'COP': zone_cop(df).reset_index().set_index(
            ['Archetype', 'Zone Name']),
        'ZoneCooling': zone_setpoint(df).loc[:, 'cooling'],
        'ZoneHeating': zone_setpoint(df).loc[:, 'heating']}

    df = (pd.concat(d, axis=1, keys=d.keys())
          .dropna(axis=0, how='all',
                  subset=[('Zone', 'Type')])  # Drop rows that are all nans
          .reset_index(level=1, col_level=1,
                       col_fill='Zone')  # Reset Index level to get Zone Name
          .reset_index().set_index(['Archetype', ('Zone', 'RowName')])
          .rename_axis(['Archetype', 'RowName']))

    df[('Zone', 'Zone Type')] = df.apply(lambda x: iscore(x), axis=1)

    df = df.reset_index().groupby(['Archetype', ('Zone', 'Zone Type')]).apply(
        lambda x: zoneconditioning_aggregation(
            x.set_index(['Archetype', 'RowName'])))

    return df


def zone_conditioning_umi(df):
    pass


def structure_definition(idf):
    cols = settings.common_umi_objects['StructureDefinitions'].copy()
    structure_definition_df = pd.DataFrame([], columns=cols)
    structure_definition_df.set_index('$id', inplace=True)
    structure_definition_df.name = 'StructureDefinitions'
    return structure_definition_df

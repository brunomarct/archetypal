################################################################################
# Module: dataportal.py
# Description: Various functions to acquire building archetype data using
#              available APIs
# License: MIT, see full license in LICENSE.txt
# Web: https://github.com/samuelduchesne/archetypal
################################################################################

import hashlib
import io
import json
import logging as lg
import os
import re
import time
import zipfile

import pandas as pd
import pycountry as pycountry
import requests
from archetypal import log, settings, make_str

# scipy and sklearn are optional dependencies for faster nearest node search
try:
    from osgeo import gdal
except ImportError as e:
    gdal = None


def tabula_available_buildings(code_country='France'):
    """Returns all available building types for a specific country.

    Args:
        code_country:

    Returns:

    """
    # Check code country
    if code_country.upper() not in ['AT', 'BA', 'BE', 'BG', 'CY', 'CZ', 'DE',
                                    'DK', 'ES', 'FR', 'GB', 'GR', 'HU', 'IE',
                                    'IT', 'NL', 'NO', 'PL', 'RS', 'SE', 'SI']:
        code_country = pycountry.countries.get(name=code_country)
        if code_country is not None:
            code_country = code_country.alpha_2
        else:
            raise ValueError('Country name {} is invalid'.format(code_country))
    data = {'code_country': code_country}
    json_response = tabula_api_request(data, table='all-country')

    # load data
    df = pd.DataFrame(json_response)
    df = df.data.apply(pd.Series)
    return df


def tabula_api_request(data, table='detail'):
    """Send a request to the TABULA API via HTTP GET and return the JSON
    response.

    Args:
        data (dict): dictionnary of query attributes.
            with table='all-country', data expects 'code_country'.
            with table='detail', data expects 'buildingtype', 'suffix', and
            'variant'.
        table (str): the server-table to query. 'detail' or 'all-country'
    Returns:

    """
    # Prepare URL
    if table == 'all-country':
        codehex = str(
            int(hashlib.md5(data['code_country'].encode('utf-8')).hexdigest(),
                16))[0:13]
        url_base = ('http://webtool.building-typology.eu/data/matrix/building'
                    '/{0}/p/0/o/0/l/10/dc/{1}')
        prepared_url = url_base.format(data['code_country'], codehex)

    elif table == 'detail':
        buildingtype = '.'.join(s for s in data['buildingtype'])
        suffix = '.'.join(s for s in data['suffix'])
        bldname = buildingtype + '.' + suffix
        hexint = hashlib.md5(bldname.encode('utf-8')).hexdigest()[0:13]
        url_base = ('http://webtool.building-typology.eu/data/adv/building'
                    '/detail/{0}/bv/{1}/dc/{2}')
        prepared_url = url_base.format(bldname, data['variant'], hexint)

    else:
        raise ValueError('server-table name "{}" invalid'.format(table))

    # First, try to get the cached resonse from file
    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json
    else:
        # if this URL is not already in the cache, request it
        response = requests.get(prepared_url)
        if response.status_code == 200:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            elif not response_json['success']:
                raise ValueError('The query "{}" returned no results'.format(
                    prepared_url), lg.WARNING)
            save_to_cache(prepared_url, response_json)
            return response_json
        else:
            # Handle some server errors
            pass


def tabula_building_details_sheet(code_building=None, code_country='FR',
                                  code_typologyregion='N',
                                  code_buildingsizeclass='SFH',
                                  code_construcionyearclass=1,
                                  code_additional_parameter='Gen',
                                  code_type='ReEx',
                                  code_num=1, code_variantnumber=1):
    """

    Args:
        code_building (str) : Whole building code e.g.:
            "AT.MT.AB.02.Gen.ReEx.001.001"
             |  |  |  |   |   |    |   |__code_variantnumber
             |  |  |  |   |   |    |______code_num
             |  |  |  |   |   |___________code_type
             |  |  |  |   |_______________code_additional_parameter
             |  |  |  |___________________code_construcionyearclass
             |  |  |______________________code_buildingsizeclass
             |  |_________________________code_typologyregion
             |____________________________code_country
        code_country (str): Country name or International Country Code (ISO
            3166-1-alpha-2 code). Input as 'France' will work equally as 'FR'.
        code_typologyregion (str): N for national; otherwise specific codes
            representing regions in a given country
        code_buildingsizeclass (str): 4 standardized classes: 'SFH':
        Single-family house, 'TH': Terraced house, 'MFH': multi-family house,
            'AB': Apartment block
        code_construcionyearclass (int or str): allocation of time bands to
            classes. Defined nationally (according to significant changes in
            construction technologies, building codes or available statistical
            data
        code_additional_parameter (str): 1 unique category. Defines the generic
            (or basic) typology matrix so that each residential building of a
            given country can be assigned to one generic type. A further
            segmentation in subtypes is  possible and can be indicated by a
            specific code. Whereas the generic types must comprise the whole
            building stock the total of subtypes must be comprehensive. e.g.
            'HR' (highrises), 'TFrame' (timber frame), 'Semi' (semi-detached)
        code_type: “ReEx” is a code for “real example” and “SyAv” for
            “Synthetical Average”
        code_num: TODO: What is this paramter?
        code_variantnumber: the energy performance level 1, 2 and 3. 1: minimum
            requirements, 2: improved and 3: ambitious or NZEB standard (assumed
            or announced level of Nearly Zero-Energy Buildings)

    Returns:
        pandas.DataFrame: The DataFrame from the

    """
    # Parse builsing_code
    if code_building is not None:
        try:
            code_country, code_typologyregion, code_buildingsizeclass, \
            code_construcionyearclass, \
            code_additional_parameter, code_type, code_num, \
            code_variantnumber = code_building.split('.')
        except ValueError:
            msg = (
                'the query "{}" is missing a parameter. Make sure the '
                '"code_building" has the form: '
                'AT.MT.AB.02.Gen.ReEx.001.001').format(code_building)
            log(msg, lg.ERROR)
            raise ValueError(msg)

    # Check code country
    if code_country.upper() not in ['AT', 'BA', 'BE', 'BG', 'CY', 'CZ', 'DE',
                                    'DK', 'ES', 'FR', 'GB', 'GR', 'HU', 'IE',
                                    'IT', 'NL', 'NO', 'PL', 'RS', 'SE', 'SI']:
        code_country = pycountry.countries.get(name=code_country)
        if code_country is not None:
            # if country is valid, return ISO 3166-1-alpha-2 code
            code_country = code_country.alpha_2
        else:
            raise ValueError('Country name {} is invalid'.format(code_country))

    # Check code_buildingsizeclass
    if code_buildingsizeclass.upper() not in ['SFH', 'TH', 'MFH', 'AB']:
        raise ValueError(
            'specified code_buildingsizeclass "{}" not supported. Available '
            'values are "SFH", "TH", '
            '"MFH" or "AB"')
    # Check numericals
    if not isinstance(code_construcionyearclass, str):
        code_construcionyearclass = str(code_construcionyearclass).zfill(2)

    if not isinstance(code_num, str):
        code_num = str(code_num).zfill(3)

    if not isinstance(code_variantnumber, str):
        code_variantnumber = str(code_variantnumber).zfill(3)

    # prepare data
    data = {'buildingtype': [code_country, code_typologyregion,
                             code_buildingsizeclass, code_construcionyearclass,
                             code_additional_parameter],
            'suffix': [code_type, code_num],
            'variant': code_variantnumber}
    json_response = tabula_api_request(data, table='detail')

    if json_response is not None:
        log('')
        # load data
        df = pd.DataFrame(json_response)
        df = df.data.apply(pd.Series)

        # remove html tags from labels
        df.label = df.label.str.replace('<[^<]+?>', ' ')
        return df
    else:
        raise ValueError('No data found in TABULA matrix with query:"{}"\nRun '
                         'archetypal.dataportal.tabula_available_buildings() '
                         'with country code "{}" to get list of possible '
                         'building types'
                         ''.format('.'.join(s for s in data['buildingtype']),
                                   code_country))


def tabula_system(code_country, code_boundarycond='SUH', code_variantnumber=1):
    """

    Args:
        code_country:
        code_boundarycond:
        code_variantnumber:

    Returns:

    """
    # Check code country
    if code_country.upper() not in ['AT', 'BA', 'BE', 'BG', 'CY', 'CZ', 'DE',
                                    'DK', 'ES', 'FR', 'GB', 'GR', 'HU', 'IE',
                                    'IT', 'NL', 'NO', 'PL', 'RS', 'SE', 'SI']:
        code_country = pycountry.countries.get(name=code_country)
        if code_country is not None:
            # if country is valid, return ISO 3166-1-alpha-2 code
            code_country = code_country.alpha_2
        else:
            raise ValueError('Country name {} is invalid')

    # Check code_buildingsizeclass
    if code_boundarycond.upper() not in ['SUH', 'MUH']:
        raise ValueError(
            'specified code_boundarycond "{}" not valid. Available values are '
            '"SUH" (Single Unit Houses) '
            'and "MUH" (Multi-unit Houses)')

    # Check code variant number
    if not isinstance(code_variantnumber, str):
        code_variantnumber = str(code_variantnumber).zfill(2)

    # prepare data
    data = {'systype': [code_country, code_boundarycond, code_variantnumber]}
    json_response = tabula_system_request(data)

    if json_response is not None:
        log('')
        # load data
        df = pd.DataFrame(json_response)
        return df.data.to_frame()
    else:
        raise ValueError('No data found in TABULA matrix with query:"{}"\nRun '
                         'archetypal.dataportal.tabula_available_buildings() '
                         'with country code "{}" to get list of possible '
                         'building types'
                         ''.format('.'.join(s for s in data['systype']),
                                   code_country))


def tabula_system_request(data):
    """

    Args:
        data (dict): prepared data for html query

    Returns:

    Examples:
        'http://webtool.building-typology.eu/data/matrix/system/detail/IT.SUH
        .01/dc/1546889637169'

    """
    system = '.'.join(s for s in data['systype'])
    hexint = hashlib.md5(system.encode('utf-8')).hexdigest()[0:13]

    log('quering system type {}'.format(system))
    prepared_url = 'http://webtool.building-typology.eu/data/matrix/system' \
                   '/detail/{0}/dc/{1}'.format(
        system, hexint)

    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json

    else:
        # if this URL is not already in the cache, pause, then request it
        response = requests.get(prepared_url)

        try:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            save_to_cache(prepared_url, response_json)
        except Exception:
            # Handle some server errors
            pass
        else:
            return response_json


def get_from_cache(url):
    """

    Args:
        url:

    Returns:

    """
    # if the tool is configured to use the cache
    if settings.use_cache:
        # determine the filename by hashing the url
        filename = hashlib.md5(url.encode('utf-8')).hexdigest()

        cache_path_filename = os.path.join(settings.cache_folder,
                                           os.extsep.join([filename, 'json']))
        # open the cache file for this url hash if it already exists, otherwise
        # return None
        if os.path.isfile(cache_path_filename):
            with io.open(cache_path_filename, encoding='utf-8') as cache_file:
                response_json = json.load(cache_file)
            log('Retrieved response from cache file "{}" for URL "{}"'.format(
                cache_path_filename, url))
            return response_json


def save_to_cache(url, response_json):
    """

    Args:
        url:
        response_json:

    Returns:

    """
    if settings.use_cache:
        if response_json is None:
            log('Saved nothing to cache because response_json is None')
        else:
            # create the folder on the disk if it doesn't already exist
            if not os.path.exists(settings.cache_folder):
                os.makedirs(settings.cache_folder)

            # hash the url (to make filename shorter than the often extremely
            # long url)
            filename = hashlib.md5(url.encode('utf-8')).hexdigest()
            cache_path_filename = os.path.join(settings.cache_folder,
                                               os.extsep.join(
                                                   [filename, 'json']))
            # dump to json, and save to file
            json_str = make_str(json.dumps(response_json))
            with io.open(cache_path_filename, 'w',
                         encoding='utf-8') as cache_file:
                cache_file.write(json_str)

            log('Saved response to cache file "{}"'.format(cache_path_filename))


def openei_api_request(data, pause_duration=None, timeout=180,
                       error_pause_duration=None):
    """

    Args:
        data (dict or OrderedDict): key-value pairs of parameters to post to
            the API
        pause_duration:
        timeout (int): how long to pause in seconds before requests, if None,
            will query API status endpoint to find when next slot is available
        error_pause_duration (int): the timeout interval for the requests
            library

    Returns:
        dict
    """
    # define the Overpass API URL, then construct a GET-style URL as a string to
    # hash to look up/save to cache
    url = ' https://openei.org/services/api/content_assist/recommend'
    prepared_url = requests.Request('GET', url, params=data).prepare().url
    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json


# def openei_dataset_request(data):
#     'COMMERCIAL_LOAD_DATA_E_PLUS_OUTPUT'
#     'https://openei.org/datasets/files/961/pub/{}
#     'USA_AR_Batesville'
#     'AWOS'
#     '723448'
#     'RefBldgMediumOfficeNew2004'
#     '/{}.{}.{}_TMY3/{}_v1.3_7.1_3A_USA_GA_ATLANTA\
#         .csv'


def nrel_api_cbr_request(data):
    """

    Args:
        data: a dict of

    Returns:
        dict: the json response

    Examples:
        >>> import archetypal as ar
        >>> ar.dataportal.nrel_api_cbr_request({'s': 'Commercial'
        >>> 'Reference', 'api_key': 'oGZdX1nhars1cTJYTm7M9T12T1ZOvikX9pH0Zudq'})

    Notes
        For a detailed description of data arguments, visit
        https://developer.nrel.gov/docs/buildings/commercial-building
        -resource-database-v1/resources/
    """
    # define the Overpass API URL, then construct a GET-style URL as a string to
    # hash to look up/save to cache
    url = 'https://developer.nrel.gov/api/commercial-building-resources/v1' \
          '/resources.json'
    prepared_url = requests.Request('GET', url, params=data).prepare().url
    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json

    else:
        start_time = time.time()
        log('Getting from {}, "{}"'.format(url, data))
        response = requests.get(prepared_url)
        # if this URL is not already in the cache, pause, then request it
        # get the response size and the domain, log result
        size_kb = len(response.content) / 1000.
        domain = re.findall(r'//(?s)(.*?)/', url)[0]
        log('Downloaded {:,.1f}KB from {}'
            ' in {:,.2f} seconds'.format(size_kb, domain,
                                         time.time() - start_time))

        try:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            save_to_cache(prepared_url, response_json)
        except Exception:
            # deal with response satus_code here
            log(
                'Server at {} returned status code {} and no JSON data.'.format(
                    domain,
                    response.status_code),
                level=lg.ERROR)
        else:
            return response_json


def nrel_bcl_api_request(data):
    """Send a request to the Building Component Library API via HTTP GET and
    return the JSON response.

    Args:
        data (dict or OrderedDict): key-value pairs of parameters to post to
            the API

    Returns:
        dict
    """
    try:
        kformat = data.pop('format')  # json or xml
        keyword = data.pop('keyword')
    except KeyError:
        url = 'https://bcl.nrel.gov/api/search/'
    else:
        url = 'https://bcl.nrel.gov/api/search/{}.{}'.format(keyword, kformat)
    prepared_url = requests.Request('GET', url, params=data).prepare().url
    print(prepared_url)
    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json

    else:
        start_time = time.time()
        log('Getting from {}, "{}"'.format(url, data))
        response = requests.get(prepared_url)
        # if this URL is not already in the cache, pause, then request it
        # get the response size and the domain, log result
        size_kb = len(response.content) / 1000.
        domain = re.findall(r'//(?s)(.*?)/', url)[0]
        log('Downloaded {:,.1f}KB from {}'
            ' in {:,.2f} seconds'.format(size_kb, domain,
                                         time.time() - start_time))

        try:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            save_to_cache(prepared_url, response_json)
        except Exception:
            # deal with response satus_code here
            log(
                'Server at {} returned status code {} and no JSON data.'.format(
                    domain,
                    response.status_code),
                level=lg.ERROR)
            return response.content
        else:
            return response_json


def stat_can_request(data):
    prepared_url = 'https://www12.statcan.gc.ca/rest/census-recensement' \
                   '/CPR2016.{type}?lang={lang}&dguid={dguid}&topic=' \
                   '{topic}&notes={notes}'.format(
        type=data.get('type', 'json'),
        lang=data.get('land', 'E'),
        dguid=data.get('dguid', '2016A000011124'),
        topic=data.get('topic', 1),
        notes=data.get('notes', 0))

    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json

    else:
        # if this URL is not already in the cache, request it
        start_time = time.time()
        log('Getting from {}, "{}"'.format(prepared_url, data))
        response = requests.get(prepared_url)
        # if this URL is not already in the cache, pause, then request it
        # get the response size and the domain, log result
        size_kb = len(response.content) / 1000.
        domain = re.findall(r'//(?s)(.*?)/', prepared_url)[0]
        log('Downloaded {:,.1f}KB from {}'
            ' in {:,.2f} seconds'.format(size_kb, domain,
                                         time.time() - start_time))

        try:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            save_to_cache(prepared_url, response_json)

        except Exception:
            # There seems to be a double backlash in the response. We try
            # removing it here.
            try:
                response = response.content.decode('UTF-8').replace('//',
                                                                    '')
                response_json = json.loads(response)
            except Exception:
                log(
                    'Server at {} returned status code {} and no JSON '
                    'data.'.format(
                        domain,
                        response.status_code),
                    level=lg.ERROR)
            else:
                save_to_cache(prepared_url, response_json)
                return response_json
            # deal with response satus_code here
            log('Server at {} returned status code {} and no JSON '
                'data.'.format(
                domain, response.status_code), level=lg.ERROR)
        else:
            return response_json


def stat_can_geo_request(data):
    prepared_url = 'https://www12.statcan.gc.ca/rest/census-recensement' \
                   '/CR2016Geo.{type}?lang={lang}&geos={geos}&cpt={cpt}'.format(
        type=data.get('type', 'json'),
        lang=data.get('land', 'E'),
        geos=data.get('geos', 'PR'),
        cpt=data.get('cpt', '00'))

    cached_response_json = get_from_cache(prepared_url)

    if cached_response_json is not None:
        # found this request in the cache, just return it instead of making a
        # new HTTP call
        return cached_response_json

    else:
        # if this URL is not already in the cache, request it
        start_time = time.time()
        log('Getting from {}, "{}"'.format(prepared_url, data))
        response = requests.get(prepared_url)
        # if this URL is not already in the cache, pause, then request it
        # get the response size and the domain, log result
        size_kb = len(response.content) / 1000.
        domain = re.findall(r'//(?s)(.*?)/', prepared_url)[0]
        log('Downloaded {:,.1f}KB from {}'
            ' in {:,.2f} seconds'.format(size_kb, domain,
                                         time.time() - start_time))

        try:
            response_json = response.json()
            if 'remark' in response_json:
                log('Server remark: "{}"'.format(response_json['remark'],
                                                 level=lg.WARNING))
            save_to_cache(prepared_url, response_json)

        except Exception:
            # There seems to be a double backlash in the response. We try
            # removing it here.
            try:
                response = response.content.decode('UTF-8').replace('//',
                                                                    '')
                response_json = json.loads(response)
            except Exception:
                log(
                    'Server at {} returned status code {} and no JSON '
                    'data.'.format(
                        domain,
                        response.status_code),
                    level=lg.ERROR)
            else:
                save_to_cache(prepared_url, response_json)
                return response_json
            # deal with response satus_code here
            log('Server at {} returned status code {} and no JSON '
                'data.'.format(
                domain, response.status_code), level=lg.ERROR)
        else:
            return response_json


def download_bld_window(u_factor, shgc, vis_trans, oauth_key, tolerance=0.05,
                        extension='idf', output_folder=None):
    """Find window constructions corresponding to a combination of a
    u_factor, shgc and visible transmittance and download their idf file to
    disk. it is necessary to have an authentication key (see Info below).

    Args:
        u_factor (float or tuple): The center of glass u-factor. Pass a
            range of values by passing a tuple (from, to). If a tuple is
            passed, *tolerance* is ignored.
        shgc (float or tuple): The Solar Heat Gain Coefficient. Pass a range
            of values by passing a tuple (from, to). If a tuple is passed,
            *tolerance* is ignored.
        vis_trans (float or tuple): The Visible Transmittance. Pass a range
            of values by passing a tuple (from, to). If a tuple is passed,
            *tolerance* is ignored.
        tolerance (float): relative tolerance for the input values. Default
            is 0.05 (5%).
        oauth_key (str): the Building_Component_Library_ authentication key.
        extension (str): specify the extension of the file to download.
            (default: 'idf')
        output_folder (str, optional): specify folder to save response data
            to. Defaults to settings.data_folder.

    Returns:
        archetypal.IDF: a list of IDF files containing window objects
            matching the  parameters.

    Note:
        An authentication key from NREL is required to download building
        components. Register at Building_Component_Library_

    .. _Building_Component_Library: https://bcl.nrel.gov/user/register

    """
    # check if one or multiple values
    if isinstance(u_factor, tuple):
        u_factor_dict = '[{} TO {}]'.format(u_factor[0], u_factor[1])
    else:
        # apply tolerance
        u_factor_dict = '[{} TO {}]'.format(u_factor * (1 - tolerance),
                                            u_factor * (1 + tolerance))
    if isinstance(shgc, tuple):
        shgc_dict = '[{} TO {}]'.format(shgc[0], shgc[1])
    else:
        # apply tolerance
        shgc_dict = '[{} TO {}]'.format(shgc * (1 - tolerance),
                                        shgc * (1 + tolerance))
    if isinstance(vis_trans, tuple):
        vis_trans_dict = '[{} TO {}]'.format(vis_trans[0], vis_trans[1])
    else:
        # apply tolerance
        vis_trans_dict = '[{} TO {}]'.format(vis_trans * (1 - tolerance),
                                             vis_trans * (1 + tolerance))

    data = {'keyword': 'Window',
            'format': 'json',
            'f[]': ['fs_a_Overall_U-factor:{}'.format(u_factor_dict),
                    'fs_a_VLT:{}'.format(vis_trans_dict),
                    'fs_a_SHGC:{}'.format(shgc_dict),
                    'sm_component_type:"Window"'],
            'oauth_consumer_key': oauth_key}
    response = nrel_bcl_api_request(data)

    if response['result']:
        log('found {} possible window component(s) matching '
            'the range {}'.format(len(response['result']), str(data['f[]'])))

    # download components
    uids = []
    for component in response['result']:
        uids.append(component['component']['uid'])
    url = 'https://bcl.nrel.gov/api/component/download?uids={}'.format(','
                                                                       ''.join(
        uids))
    # actual download with get()
    d_response = requests.get(url)

    if d_response.ok:
        # loop through files and extract the ones that match the extension
        # parameter
        results = []
        if output_folder is None:
            output_folder = settings.data_folder
        with zipfile.ZipFile(io.BytesIO(d_response.content)) as z:
            for info in z.infolist():
                if info.filename.endswith(extension):
                    z.extract(info, path=output_folder)
                    results.append(os.path.join(settings.data_folder,
                                                info.filename))
        return results
    else:
        return response['result']

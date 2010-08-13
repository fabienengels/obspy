# -*- coding: utf-8 -*-
"""
SeisHub database client for ObsPy.

:copyright:
    The ObsPy Development Team (devs@obspy.org)
:license:
    GNU Lesser General Public License, Version 3
    (http://www.gnu.org/copyleft/lesser.html)
"""

from lxml import objectify
from lxml.etree import Element, SubElement, tostring
from datetime import datetime
from math import log
import pickle
import sys
import time
import urllib2
import urllib
import inspect
from obspy.core.util import BAND_CODE
from obspy.core import UTCDateTime


class Client(object):
    """
    SeisHub database request Client class.

    Notes
    -----
    The following classes are automatically linked with initialization.
    Follow the links in "Linked Class" for more information. They register
    via the name listed in "Entry Point".

    ===================  ====================================================
    Entry Point          Linked Class
    ===================  ====================================================
    ``Client.station``   :class:`~obspy.seishub.client._WaveformMapperClient`
    ``Client.waveform``  :class:`~obspy.seishub.client._StationMapperClient`
    ``Client.event``     :class:`~obspy.seishub.client._EventMapperClient`
    ===================  ====================================================

    Examples
    --------

    >>> from obspy.seishub import Client
    >>> from obspy.core import UTCDateTime
    >>>
    >>> t = UTCDateTime("2009-09-03 00:00:00")
    >>> client = Client()
    >>>
    >>> st = client.waveform.getWaveform("BW", "RTPI", "", "EHZ", t, t + 20)
    >>> print st
    1 Trace(s) in Stream:
    .GP01..SHZ | 2009-09-03T00:00:00.000000Z - 2009-09-03T00:00:20.000000Z | 250.0 Hz, 5001 samples
    """
    def __init__(self, base_url="http://teide.geophysik.uni-muenchen.de:8080",
                 user="admin", password="admin", timeout=10):
        self.base_url = base_url
        self.waveform = _WaveformMapperClient(self)
        self.station = _StationMapperClient(self)
        self.event = _EventMapperClient(self)
        self.timeout = timeout
        # Create an OpenerDirector for Basic HTTP Authentication
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, base_url, user, password)
        auth_handler = urllib2.HTTPBasicAuthHandler(password_mgr)
        opener = urllib2.build_opener(auth_handler)
        # install globally
        urllib2.install_opener(opener)

    def ping(self):
        """
        Ping the SeisHub server.
        """
        try:
            t1 = time.time()
            urllib2.urlopen(self.base_url).read()
            return (time.time() - t1) * 1000.0
        except:
            None

    def _fetch(self, url, *args, **kwargs):
        params = {}
        for key, value in kwargs.iteritems():
            if not value:
                continue
            if isinstance(value, tuple) and len(value) == 2:
                params['min_' + str(key)] = str(value[0])
                params['max_' + str(key)] = str(value[1])
            elif isinstance(value, list) and len(value) == 2:
                params['min_' + str(key)] = str(value[0])
                params['max_' + str(key)] = str(value[1])
            else:
                params[str(key)] = str(value)
        # replace special characters 
        remoteaddr = self.base_url + url + '?' + urllib.urlencode(params)
        # timeout exists only for Python >= 2.6
        if sys.hexversion < 0x02060000:
            response = urllib2.urlopen(remoteaddr)
        else:
            response = urllib2.urlopen(remoteaddr, timeout=self.timeout)
        doc = response.read()

        return doc

    def _objectify(self, url, *args, **kwargs):
        doc = self._fetch(url, *args, **kwargs)
        return objectify.fromstring(doc)


class _WaveformMapperClient(object):
    """
    """
    def __init__(self, client):
        self.client = client

    def getNetworkIds(self, **kwargs):
        url = '/seismology/waveform/getNetworkIds'
        root = self.client._objectify(url, **kwargs)
        return [str(node['network']) for node in root.getchildren()]

    def getStationIds(self, **kwargs):
        url = '/seismology/waveform/getStationIds'
        root = self.client._objectify(url, **kwargs)
        return [str(node['station']) for node in root.getchildren()]

    def getLocationIds(self, **kwargs):
        url = '/seismology/waveform/getLocationIds'
        root = self.client._objectify(url, **kwargs)
        return [str(node['location']) for node in root.getchildren()]

    def getChannelIds(self, **kwargs):
        url = '/seismology/waveform/getChannelIds'
        root = self.client._objectify(url, **kwargs)
        return [str(node['channel']) for node in root.getchildren()]

    def getLatency(self, *args, **kwargs):
        """
        Gets a list of network latency values.

        :param network_id: Network code, e.g. 'BW'.
        :param station_id: Station code, e.g. 'MANZ'.
        :param location_id: Location code, e.g. '01'.
        :param channel_id: Channel code, e.g. 'EHE'.
        :return: List of dictionaries containing latency information.
        """
        map = ['network_id', 'station_id', 'location_id', 'channel_id']
        for i in range(len(args)):
            kwargs[map[i]] = args[i]
        url = '/seismology/waveform/getLatency'
        root = self.client._objectify(url, **kwargs)
        return [node.__dict__ for node in root.getchildren()]

    def getWaveform(self, network_id, station_id, location_id, channel_id,
                    start_datetime, end_datetime, apply_filter=False,
                    **kwargs):
        """
        Gets a ObsPy Stream object.

        :type network_id: String
        :param network_id: Network code, e.g. 'BW'.
        :type station_id: String
        :param station_id: Station code, e.g. 'MANZ'.
        :type location_id: String
        :param location_id: Location code, e.g. '01'.
        :type channel_id: String
        :param channel_id: Channel code, supporting wildcard for component,
            e.g. 'EHE' or 'EH*'.
        :type start_datetime: String or
            :class:`~obspy.core.utcdatetime.UTCDateTime`
        :param start_datetime: start time of requested data
        :type end_datetime: String or
            :class:`~obspy.core.utcdatetime.UTCDateTime`
        :param end_datetime: end time of requested data
        :type apply_filter: Boolean
        :param apply_filter: apply filter, default False.
        :return: :class:`~obspy.core.stream.Stream`
        """
        # analyze args passed on to method call and put them into
        # kwargs-dictionary for the _fetch() call later on
        frame = inspect.currentframe()
        args, _, _, values = inspect.getargvalues(frame)
        for arg in args[1:]:
            kwargs[arg] = values[arg]
        
        # we expand the requested timespan on both ends by two samples in
        # order to be able to make use of the nearest_sample option of
        # stream.trim(). (see trim() and tickets #95 and #105)
        band_code = kwargs['channel_id'][0]
        start = kwargs['start_datetime']
        if isinstance(start, str):
            start = UTCDateTime(start)
        kwargs['start_datetime'] = start - 2.0 / BAND_CODE[band_code]
        end = kwargs['end_datetime']
        if isinstance(end, str):
            end = UTCDateTime(end)
        kwargs['end_datetime'] = end + 2.0 / BAND_CODE[band_code]

        url = '/seismology/waveform/getWaveform'
        data = self.client._fetch(url, **kwargs)
        if data == '':
            raise Exception("No waveform data available")
        # unpickle
        stream = pickle.loads(data)
        if len(stream) == 0:
            raise Exception("No waveform data available")

        stream.trim(start, end)
        return stream

    def getPreview(self, *args, **kwargs):
        """
        Gets a preview of a ObsPy Stream object.

        :param network_id: Network code, e.g. 'BW'.
        :param station_id: Station code, e.g. 'MANZ'.
        :param location_id: Location code, e.g. '01'.
        :param channel_id: Channel code, e.g. 'EHE'.
        :param start_datetime: start time as
            :class:`~obspy.core.utcdatetime.UTCDateTime` object.
        :param end_datetime: end time as 
            :class:`~obspy.core.utcdatetime.UTCDateTime` object
        :return: :class:`~obspy.core.stream.Stream` object.
        """
        map = ['network_id', 'station_id', 'location_id', 'channel_id',
               'start_datetime', 'end_datetime', 'trace_ids']
        for i in range(len(args)):
            kwargs[map[i]] = args[i]
        url = '/seismology/waveform/getPreview'
        data = self.client._fetch(url, **kwargs)
        if not data:
            raise Exception("No waveform data available")
        # unpickle
        stream = pickle.loads(data)
        return stream

    def getPreviewByIds(self, *args, **kwargs):
        """
        Gets a preview of a ObsPy Stream object.

        :param trace_ids: List of trace IDs, e.g. ['BW.MANZ..EHE'].
        :param start_datetime: start time as
            :class:`~obspy.core.utcdatetime.UTCDateTime` object.
        :param end_datetime: end time as 
            :class:`~obspy.core.utcdatetime.UTCDateTime` object
        :return: :class:`~obspy.core.stream.Stream` object.
        """
        map = ['trace_ids', 'start_datetime', 'end_datetime']
        for i in range(len(args)):
            kwargs[map[i]] = args[i]
        # concatenate list of IDs into string
        if 'trace_ids' in kwargs:
            if isinstance(kwargs['trace_ids'], list):
                kwargs['trace_ids'] = ','.join(kwargs['trace_ids'])
        url = '/seismology/waveform/getPreview'
        data = self.client._fetch(url, **kwargs)
        if not data:
            raise Exception("No waveform data available")
        # unpickle
        stream = pickle.loads(data)
        return stream


class _BaseRESTClient(object):
    def __init__(self, client):
        self.client = client

    def getResource(self, resource_name, **kwargs):
        """
        Gets a resource.

        :param resource_name: Name of the resource.
        :param format: Format string, e.g. 'xml' or 'map'.
        :return: Resource
        """
        url = '/xml/' + self.package + '/' + self.resourcetype + '/' + \
              resource_name
        return self.client._fetch(url, **kwargs)

    def getXMLResource(self, resource_name, **kwargs):
        """
        Gets a XML resource.

        :param resource_name: Name of the resource.
        :return: Resource
        """
        url = '/xml/' + self.package + '/' + self.resourcetype + '/' + \
              resource_name
        return self.client._objectify(url, **kwargs)


class _StationMapperClient(_BaseRESTClient):
    """
    """
    package = 'seismology'
    resourcetype = 'station'

    def getList(self, *args, **kwargs):
        """
        Gets a list of station information.

        :param network_id: Network code, e.g. 'BW'.
        :param station_id: Station code, e.g. 'MANZ'.
        :return: List of dictionaries containing station information.
        """
        map = ['network_id', 'station_id']
        for i in range(len(args)):
            kwargs[map[i]] = args[i]
        url = '/seismology/station/getList'
        root = self.client._objectify(url, **kwargs)
        return [node.__dict__ for node in root.getchildren()]

    def getPAZ(self, network_id, station_id, datetime, location_id='',
               channel_id='', seismometer_gain=False):
        """
        Get PAZ for a station at given time span. Gain is the A0 normalization
        constant for the poles and zeros.

        >>> c = Client()
        >>> a = c.station.getPAZ('BW', 'MANZ', '20090707', channel_id='EHZ')
        >>> a['zeros']
        [0j, 0j]
        >>> a['poles']
        [(-0.037004000000000002+0.037016j), (-0.037004000000000002-0.037016j), (-251.33000000000001+0j), (-131.03999999999999-467.29000000000002j), (-131.03999999999999+467.29000000000002j)]
        >>> a['gain']
        60077000.0
        >>> a['sensitivity']
        2516800000.0

        :param network_id: Network id, e.g. 'BW'.
        :param station_id: Station id, e.g. 'RJOB'.
        :param location_id: Location id, e.g. ''.
        :param channel_id: Channel id, e.g. 'EHE'.
        :param datetime: :class:`~obspy.core.utcdatetime.UTCDateTime` or
            time string.
        :param seismometer_gain: If True add also seismometer gain to
            dictionary
        :return: Dictionary containing zeros, poles, gain and sensitivity.
        """
        # request station information
        station_list = self.getList(network_id=network_id,
                                    station_id=station_id, datetime=datetime)
        if not station_list:
            return {}
        # don't allow wild cards - either search over exact one node or all
        for t in ['*', '?']:
            if t in channel_id:
                channel_id = ''
            if t in location_id:
                location_id = ''

        xml_doc = station_list[0]
        # request station resource
        res = self.client.station.getXMLResource(xml_doc['resource_name'])
        base_node = res.station_control_header
        # search for nodes with correct channel and location code
        if channel_id or location_id:
            xpath_expr = "channel_identifier[channel_identifier='" + \
                channel_id + "' and location_identifier='" + location_id + "']"
            # fetch next following response_poles_and_zeros node
            xpath_expr = "channel_identifier[channel_identifier='" + \
                channel_id + "' and location_identifier='" + location_id + \
                "']/following-sibling::response_poles_and_zeros"
            paz_node = base_node.xpath(xpath_expr)[0]
            # fetch next following channel_sensitivity_node with 
            # stage_sequence_number == 0
            xpath_expr = "channel_identifier[channel_identifier='" + \
                channel_id + "' and location_identifier='" + location_id + \
                "']/following-sibling::channel_sensitivity_" + \
                "gain[stage_sequence_number='0']"
            sensitivity_node = base_node.xpath(xpath_expr)[0]
            # fetch seismometer gain following channel_sensitivity_node with 
            # stage_sequence_number == 1
            xpath_expr = "channel_identifier[channel_identifier='" + \
                channel_id + "' and location_identifier='" + location_id + \
                "']/following-sibling::channel_sensitivity_" + \
                "gain[stage_sequence_number='1']"
            seismometer_gain_node = base_node.xpath(xpath_expr)[0]
        else:
            # just take first existing nodes
            paz_node = base_node.response_poles_and_zeros[0]
            sensitivity_node = base_node.channel_sensitivity_gain[-1]
            seismometer_gain_node = base_node.channel_sensitivity_gain[0]
        paz = {}
        # poles
        poles_real = paz_node.complex_pole.real_pole[:]
        poles_imag = paz_node.complex_pole.imaginary_pole[:]
        poles = zip(poles_real, poles_imag)
        paz['poles'] = [p[0] + p[1] * 1j for p in poles]
        # zeros
        zeros_real = paz_node.complex_zero.real_zero[:][:]
        zeros_imag = paz_node.complex_zero.imaginary_zero[:][:]
        zeros = zip(zeros_real, zeros_imag)
        paz['zeros'] = [p[0] + p[1] * 1j for p in zeros]
        # gain
        paz['gain'] = paz_node.A0_normalization_factor
        # sensitivity
        paz['sensitivity'] = sensitivity_node.sensitivity_gain
        # paz['name'] = name
        if seismometer_gain:
            paz['seismometer_gain'] = seismometer_gain_node.sensitivity_gain
        return paz


class _EventMapperClient(_BaseRESTClient):
    """
    """
    package = 'seismology'
    resourcetype = 'event'

    def getList(self, *args, **kwargs):
        """
        Gets a list of event information.

        :return: List of dictionaries containing event information.
        """
        url = '/seismology/event/getList'
        root = self.client._objectify(url, **kwargs)
        return [node.__dict__ for node in root.getchildren()]

    def getKml(self, nolabels=False, *args, **kwargs):
        """
        Posts an event.getList() and returns the results as a KML file.

        :return: String containing KML information of all matching events. This
                 string can be written to a file and loaded into e.g. Google
                 Earth.
        """
        events = self.getList(*args, **kwargs)
        timestamp = datetime.now()

        # construct the KML file
        kml = Element("kml")
        kml.set("xmlns", "http://www.opengis.net/kml/2.2")

        document = SubElement(kml, "Document")
        SubElement(document, "name").text = "Seishub Event Locations"

        # style definitions for earthquakes
        style = SubElement(document, "Style")
        style.set("id", "earthquake")

        iconstyle = SubElement(style, "IconStyle")
        SubElement(iconstyle, "scale").text = "0.5"
        icon = SubElement(iconstyle, "Icon")
        SubElement(icon, "href").text = "http://maps.google.com/mapfiles/kml/" + \
                                 "shapes/earthquake.png"
        hotspot = SubElement(iconstyle, "hotSpot")
        hotspot.set("x", "0.5")
        hotspot.set("y", "0")
        hotspot.set("xunits", "fraction")
        hotspot.set("yunits", "fraction")

        labelstyle = SubElement(style, "LabelStyle")
        SubElement(labelstyle, "color").text = "ff0000ff"
        SubElement(labelstyle, "scale").text = "0.8"

        folder = SubElement(document, "Folder")
        SubElement(folder, "name").text = "Seishub Events (%s)" % \
                                          timestamp.date()
        SubElement(folder, "open").text = "1"

        # additional descriptions for the folder
        descrip_str = "Fetched from: %s" % self.client.base_url
        descrip_str += "\nFetched at: %s" % timestamp
        descrip_str += "\n\nSearch options:\n"
        descrip_str += "\n".join(["=".join(str(item)) for item in kwargs.items()])
        SubElement(folder, "description").text = descrip_str

        style = SubElement(folder, "Style")
        liststyle = SubElement(style, "ListStyle")
        SubElement(liststyle, "listItemType").text = "check"
        SubElement(liststyle, "bgColor").text = "00ffffff"
        SubElement(liststyle, "maxSnippetLines").text = "5"

        # add one marker per event
        interesting_keys = ['resource_name', 'localisation_method', 'account',
                            'user', 'public', 'datetime', 'longitude',
                            'latitude', 'depth', 'magnitude', 'used_p',
                            'used_s']
        for event_dict in events:
            placemark = SubElement(folder, "Placemark")
            date = str(event_dict['datetime']).split(" ")[0]
            mag = str(event_dict['magnitude'])

            # scale marker size to magnitude if this information is present
            if mag:
                mag = float(mag)
                label = "%s: %.1f" % (date, mag)
                try:
                    icon_size = 1.2 * log(1.5 + mag)
                except ValueError:
                    icon_size = 0.1
            else:
                label = date
                icon_size = 0.5
            if nolabels:
                SubElement(placemark, "name").text = ""
            else:
                SubElement(placemark, "name").text = label
            SubElement(placemark, "styleUrl").text = "#earthquake"
            style = SubElement(placemark, "Style")
            icon_style = SubElement(style, "IconStyle")
            liststyle = SubElement(style, "ListStyle")
            SubElement(liststyle, "maxSnippetLines").text = "5"
            SubElement(icon_style, "scale").text = str(icon_size)
            point = SubElement(placemark, "Point")
            SubElement(point, "coordinates").text = "%.10f,%.10f,0" % \
                    (event_dict['longitude'], event_dict['latitude'])

            # detailed information on the event for the description
            descrip_str = ""
            for key in interesting_keys:
                if not key in event_dict:
                    continue
                descrip_str += "\n%s: %s" % (key, event_dict[key])
            SubElement(placemark, "description").text = descrip_str

        # generate and return KML string
        return tostring(kml, pretty_print=True, xml_declaration=True)


if __name__ == '__main__':
    import doctest
    doctest.testmod(exclude_empty=True)

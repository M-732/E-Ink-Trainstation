#!/usr/bin/python
# -*- coding:utf-8 -*-

import json
import requests

class TransportRequest:

    def __init__(self, _configAPI):
        self.m_AppID = _configAPI['appID']
        self.m_AppKey = _configAPI['key']
        self.m_StationCode = _configAPI['station_code']
        self.m_CallingAt = _configAPI['calling_at']


    def DefaultRequest(self, _url, _customParams):
        queryParameters = {'app_id': self.m_AppID,
                  'app_key': self.m_AppKey}

        queryParameters.update(_customParams)
        try:
            responseObject = requests.get(_url, queryParameters)
            if(responseObject.ok == False):
                print("")
                return

            return responseObject.json()

        except requests.ConnectionError:
            return


    def GetLiveServices(self):
        ''' Live service updates at a given station: departures, arrivals or passes '''
        url = f"https://transportapi.com/v3/uk/train/station/{self.m_StationCode}/live.json"
        customQueryParameters = { 'calling_at': self.m_CallingAt,
                    'darwin': 'true' }

        dataTransport = self.DefaultRequest(url, customQueryParameters)
        if(dataTransport == None):
            return [], ""

        return dataTransport['departures']['all'], dataTransport["station_name"]


    def GetTimetabledAtServiceID(self, _serviceID):
        ''' Timetabled service updates for a given service '''
        url = f"https://transportapi.com/v3/uk/train/service/{_serviceID}///timetable.json"
        customQueryParameters = { 'station_code': self.m_StationCode }

        dataTransport = self.DefaultRequest(url, customQueryParameters)
        if(dataTransport == None):
            return []

        return dataTransport['stops']

    def GetPlacesInformations(self, _query: str, _type: str):
        ''' Various information from a location (geo location, code, name, type) '''
        url = f"https://transportapi.com/v3/uk/places.json"
        customQueryParameters = {'query': _query,
                                 'type': _type}

        dataTransport = self.DefaultRequest(url, customQueryParameters)
        if(dataTransport == None):
            return []

        return dataTransport['member']
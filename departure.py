#!/usr/bin/python
# -*- coding:utf-8 -*-

import datetime

from utility import AbbreviateMessage, GetCurrentDateTime

K_DEFAULT_DATECODE = '%Y-%m-%d'
K_DEFAULT_TIMECODE = '%H:%M'

def CheckValue(_value: str, _exception):
    return _value if _value != None else _exception

def ParseStopDatetime(_stopData: dict, _type: str):
    '''
    Get the time and date data to create a Datetime class.
    :param _stopData: A raw stop data dictionary.
    :param _type: The attribute name of the aimed time ('departure' or 'arrival'). Raise a Error if the type is not valid.
    :return: a parsed Datetime class or None if _stopData doesn't contains a time value
    '''
    assert _type == 'arrival' or _type == 'departure', "_type value is incorrect, should correspond to 'arrival' or 'departures' only"
    aimedStopTime = CheckValue(_stopData['aimed_'+ _type +'_time'], None)
    aimedStopDate = CheckValue(_stopData['aimed_'+ _type +'_date'], None)

    result = None
    if aimedStopTime != None:
        aimedStopDatetime = '{} {}'.format(aimedStopDate, aimedStopTime)
        aimedStopFormat = '{} {}'.format((K_DEFAULT_DATECODE if aimedStopDate != ' ' else ''), (K_DEFAULT_TIMECODE if aimedStopTime != ' ' else ''))

        result = datetime.datetime.strptime(aimedStopDatetime, aimedStopFormat)
    return result


class Stop:
    ''' Simplified timetable stop'''
    def __init__(self, _timetable: dict):
        self.m_StationCode = _timetable['station_code']
        self.m_TiplocCode = _timetable['tiploc_code']

        self.m_AimedDepartureDatetime = ParseStopDatetime(_timetable, 'departure')
        self.m_AimedArrivalDatetime = ParseStopDatetime(_timetable, 'arrival')


class Departure:
    '''Class for keeping track of a departure'''

    def __init__(self, _departureData: dict, _abbreviationDict: dict):
        self.m_Mode = _departureData['mode'].title()
        self.m_ServiceID = str(_departureData['service'])
        self.m_Platform = CheckValue(_departureData['platform'], '-')

        self.m_AimedDepartureDatetime = None
        self.m_AimedArrivalDatetime = None

        self.m_DestinationName = AbbreviateMessage(_abbreviationDict, CheckValue(_departureData['destination_name'], '----'))
        self.m_Status = _departureData['status']

        self.m_Timetable = []
        self.m_TimetableAfterArrival = []

    def CanDelete(self):
        '''
        Condition to validate the deletion
        Check if the departure time is still valid
        :return: True if the departure time has not passed
        '''

        if(self.m_AimedDepartureDatetime == None):
            return True

        return GetCurrentDateTime() > self.m_AimedDepartureDatetime

    def FillTimetable(self, _timetableData: list, _stationCode: str):
        '''
        Convert all the raw stop data into a simplified Stop class.
        :param _timetableData: A raw timetable data list.
        :param _stationCode: The attribute name of the aimed time ('departure' or 'arrival').
        :return: None
        '''
        if len(_timetableData) == 0:
            return

        del self.m_Timetable[:]
        del self.m_TimetableAfterArrival[:]

        isAfterArrival = False
        for stopData in _timetableData:
            if isAfterArrival :
                self.m_TimetableAfterArrival.append(Stop(stopData))
            else:
                self.m_Timetable.append(Stop(stopData))

            if stopData['station_code'] == _stationCode:
                isAfterArrival = True
                pass

        self.m_TimetableAfterArrival.reverse()

        self.m_AimedArrivalDatetime = self.m_Timetable[-1].m_AimedArrivalDatetime
        self.m_AimedDepartureDatetime = self.m_Timetable[-1].m_AimedDepartureDatetime

    def GetDepartureInformation(self):
        '''
        Get all information about the current departure
        :return: None
        '''

        arrivalTime = '--:--' if self.m_AimedArrivalDatetime == None else (str(self.m_AimedArrivalDatetime.hour) + ':' + ('' if self.m_AimedArrivalDatetime.minute >= 10 else '0') + str(self.m_AimedArrivalDatetime.minute))
        #No check if m_AimedDepartureDatetime is None because it's a condition of deletion
        departureTime = str(self.m_AimedDepartureDatetime.hour) + ':' + ('' if self.m_AimedDepartureDatetime.minute >= 10 else '0') + str(self.m_AimedDepartureDatetime.minute)

        message = '{} : {}\
                  \n    Plat. : {}    {}\
                  \n    Arr.: {}      Dep.: {}'\
                  .format(self.m_Mode, self.m_DestinationName,\
                          self.m_Platform, self.m_Status,\
                          arrivalTime, departureTime)

        return message


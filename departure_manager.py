#!/usr/bin/python
# -*- coding:utf-8 -*-

import json
import logging
import math
import time

from datetime import timedelta
from PIL import Image, ImageDraw, ImageFont

import utility
from departure import Departure
from transportrequest import TransportRequest


class NodeStation:
    def __init__(self, _ID: str, _pixelPosition = (0,0)):
        self.m_ID = _ID
        self.m_PixelPosition = _pixelPosition

        self.m_ChildNodeStation = []

    def AddNode(self, _node):
        self.m_ChildNodeStation.append(_node)

    def Search(self, _ID: str):
        '''
        Recursively search the corresponding stastion code
        :param _ID: station code ID to search
        :return: the corresponding NodeStation if found or None
        '''
        if self.m_ID == _ID:
            return self

        result = None
        for childNodeStation in self.m_ChildNodeStation:
            result = childNodeStation.Search(_ID)

            if result != None:
                return result

        return None


class DepartureManager:
    '''Handle the request, the display and the validity of the departures'''
    def __init__(self):
        self.config = self.LoadConfig()
        self.maxDeparture = self.config['maxDepartures']
        self.distanceDrawMap = self.config['distanceDrawMap']

        self.m_AgendaTimer = utility.Timer()
        self.m_DepartureRequestTimer = utility.Timer()
        self.m_RefreshDisplayTimer = utility.Timer()
        self.b_CanRefresh = False

        self.transportRequest = TransportRequest(self.config['transportRequest'])
        self.stationName = str("")
        self.allDepartures = []

        self.m_Tree = None
        self.m_CenterCoordinate = (0,0)

        self.m_DepartureFilename = "departures.png"
        self.m_StationMapFilename = "station_map.jpg"

    def Update(self):
        self.AgendaUpdate()

        #Requests
        self.DepartureRequests()
        self.UpdateDepartures()
        self.FillNodeStation()

        #Drawing
        self.CreateDepartureImage()
        self.DrawStationMap()
        self.DrawTrainPosition()

        utility.MergeImages(self.m_DepartureFilename, self.m_StationMapFilename, self.m_DepartureFilename, box= (250, 0))

        utility.DisplayOnEPaper(self.m_DepartureFilename)

        self.SleepBehavior()

    def AgendaUpdate(self):
        '''
        Update and restart the different timers based on Agenda in config.json.
        Set b_CanRefresh to True
        :return: None
        '''
        if self.m_AgendaTimer.IsElapsed():
            logging.info("Agenda Update")
            agenda = self.config['agenda']

            currentDateTime = utility.GetCurrentDateTime()
            conditionDateTime = currentDateTime
            currentAgendaUpdate = agenda[-1]
            nextAgendaRefresh = None
            for timeCondition in agenda:
                hour, minute = [int(value) for value in timeCondition['startCondition'].split(':')]
                conditionDateTime = currentDateTime.replace(hour=hour, minute=minute)
                if conditionDateTime > currentDateTime:
                    nextAgendaRefresh = conditionDateTime
                    break

                currentAgendaUpdate = timeCondition

            assert currentAgendaUpdate, "At this point, the time condition should not be equals to None. Check config.json, agenda part"

            if nextAgendaRefresh == None:
                nextAgendaRefresh = currentDateTime

                hour, minute = [int(value) for value in agenda[0]['startCondition'].split(':')]
                nextAgendaRefresh = currentDateTime.replace(hour=hour, minute=minute)
                nextAgendaRefresh = nextAgendaRefresh + timedelta(days=1)

            #calculate duration next refresh
            calculatedDuration = (nextAgendaRefresh - currentDateTime).total_seconds()

            self.m_AgendaTimer.Reset()
            self.m_AgendaTimer.m_Duration = calculatedDuration


            refreshDisplay = currentAgendaUpdate['refreshDisplay']
            refreshDepartures = currentAgendaUpdate['refreshDepartures']

            self.m_DepartureRequestTimer.m_Duration = refreshDepartures
            self.m_DepartureRequestTimer.Reset()
            self.m_RefreshDisplayTimer.m_Duration = refreshDisplay
            self.m_RefreshDisplayTimer.Reset()
            self.b_CanRefresh = True

            logging.debug("Next agenda update {} | Timer Departure : {} | Refresh Display {}".format(calculatedDuration, refreshDepartures, refreshDisplay))

    def DepartureRequests(self):
        '''
        Pulls the departures data from the transport API.
        Checks if the condition to refresh the departures is valid before ask.
        :return: None
        '''
        if self.m_DepartureRequestTimer.IsElapsed() or self.b_CanRefresh:
            logging.info("Departure Requests")

            del self.allDepartures[:]

            allDeparturesData, self.stationName = self.transportRequest.GetLiveServices()

            for departureData in allDeparturesData:
                departure = Departure(departureData, self.config['abbreviation'])
                self.allDepartures.append(departure)

            self.m_DepartureRequestTimer.Reset()
            self.b_CanRefresh = True

    def UpdateDepartures(self):
        '''
        Check if the departures are still valid to be displayed
        :return: None
        '''
        logging.info("Updates Departure")

        if self.b_CanRefresh:
            for departure in self.allDepartures:
                timetable = self.transportRequest.GetTimetabledAtServiceID(departure.m_ServiceID)
                departure.FillTimetable(timetable, self.transportRequest.m_StationCode)

        index = len(self.allDepartures) - 1
        while index >= 0:
            if(self.allDepartures[index].CanDelete()):
                self.allDepartures.pop(index)

            index -= 1

        del self.allDepartures[self.maxDeparture:] #truncate list

    def CreateDepartureImage(self):
        '''
        Convert the departure data into an image.
        The type of image is defined by m_DepartureFilename.
        :return: None
        '''

        if self.m_RefreshDisplayTimer.IsElapsed() or self.b_CanRefresh:
            logging.info("Create Departure PNG")

            departureDict = self.InitDeparturesDictionaries()

            if(len(self.allDepartures) == 0):
                departureDict['DEPARTURE_02'] = "No departures for the moment." #Display in the 'middle' of the screen

            else:
                index = 0
                for departure in self.allDepartures:

                    departureID = "DEPARTURE_0" + str(index)
                    departureMessage = departure.GetDepartureInformation()

                    departureDict[departureID] = departureMessage
                    index += 1

            utility.UpdateSVG('asset/template.svg', 'departures.svg', departureDict)
            utility.ConvertSVG('departures.svg', self.m_DepartureFilename)

            self.m_RefreshDisplayTimer.Reset()

    def FillNodeStation(self):
        '''
        Create a NodeStation tree of all of the connected station with the timetable.
        :return: None
        '''

        if self.b_CanRefresh == False or len(self.allDepartures) == 0:
            return

        logging.info("Fill node station")

        initList = list(self.allDepartures[-1].m_Timetable)
        self.CreateNodeStation(initList)

        for departure in reversed(self.allDepartures):
            self.CreateNodeStation(departure.m_TimetableAfterArrival)

        for departure in reversed(self.allDepartures):
            self.CreateNodeStation(departure.m_Timetable)

    def CreateNodeStation(self, _currentTimetable : []):

        index = len(_currentTimetable) - 1
        imageSize = (400, 480)

        if self.m_Tree == None: #Init tree
            stop = _currentTimetable[index]

            result = self.transportRequest.GetPlacesInformations("{},{}".format(stop.m_StationCode, stop.m_TiplocCode), 'train_station')
            assert result, "API couldn't return a valid result at the main station code {} {}".format(stop.m_StationCode, stop.m_TiplocCode)

            assert 'latitude' in result[0] , "No latitude at station {} {}".format(stop.m_StationCode, stop.m_TiplocCode)
            self.m_CenterCoordinate = (result[0]['latitude'], result[0]['longitude'])

            self.m_Tree = NodeStation(result[0]['station_code'], self.ConvertCoordinateToPixel(imageSize, self.m_CenterCoordinate, self.m_CenterCoordinate))

            index -= 1

        radius = 6371.0 # Volumetric Earth radius (Km)
        degToRad = 0.017453292519943295  # Pi / 180.0
        refLatitudeRad = self.m_CenterCoordinate[0] * degToRad

        previousNode = self.m_Tree
        while index >= 0:
            stop = _currentTimetable[index]

            node = self.m_Tree.Search(stop.m_StationCode)
            if node == None:
                placeResult = self.transportRequest.GetPlacesInformations("{},{}".format(stop.m_StationCode, stop.m_TiplocCode), 'train_station')

                if placeResult != None: #It appears, sometimes, the API couldn't return a valid result with a station code

                    if placeResult[0].get('latitude') == None:
                        logging.debug("No latitude at station {} {}".format(stop.m_StationCode, stop.m_TiplocCode))
                        pass

                    coordinateResult = (placeResult[0]['latitude'], placeResult[0]['longitude'])
                    nodeResult = NodeStation(placeResult[0]['station_code'], self.ConvertCoordinateToPixel(imageSize, coordinateResult, self.m_CenterCoordinate))

                    previousNode.AddNode(nodeResult)
                    previousNode = nodeResult

                    #Using Haversine formula to calculate distance between 2 points
                    latitudeRad = coordinateResult[0] * degToRad
                    deltaLatitudeRad = (latitudeRad - refLatitudeRad) * degToRad
                    deltaLongitudeRad = ( coordinateResult[1] - self.m_CenterCoordinate[1]) * degToRad

                    #https://www.movable-type.co.uk/scripts/latlong.html
                    sqrHalfChordLength = math.sin(deltaLatitudeRad / 2.0)  * math.sin(deltaLatitudeRad / 2.0) +\
                                            math.cos(refLatitudeRad)          * math.cos(radius) *\
                                            math.sin(deltaLongitudeRad / 2.0) * math.sin(deltaLongitudeRad / 2.0)

                    angularDistance = 2.0 * math.atan2(math.sqrt(sqrHalfChordLength), math.sqrt(1.0 - sqrHalfChordLength))

                    distance = radius * angularDistance

                    #Intentionally checked after adding the node for drawing line outside
                    if distance > (self.distanceDrawMap * 1.414):
                        break

                else:
                    logging.warning("API couldn't return a valid result at the station code {} | {}".format(stop.m_StationCode, stop.m_TiplocCode))
            else:
                previousNode = node

            index -= 1

    def ConvertCoordinateToPixel(self, _imageSize: Image.BOX, _coordinates, _offset = (0,0)):
        ratioPixelPerKm = _imageSize[0] / self.distanceDrawMap

        xMiddle = _imageSize[0] / 2.0
        yMiddle = _imageSize[1] / 2.0

        radius = 6371.0 # Volumetric Earth radius (Km)
        degToRad = 0.017453292519943295  # Pi / 180.0

        xPosition = xMiddle + ((_coordinates[1] - _offset[1]) * degToRad * radius * ratioPixelPerKm)
        yPosition = yMiddle - ((_coordinates[0] - _offset[0]) * degToRad * radius * ratioPixelPerKm)

        return (xPosition, yPosition)

    def DrawStationMap(self):
        if self.m_Tree == None:
            logging.warning("No node tree to draw")
            return

        if self.b_CanRefresh == False:
            return

        logging.info("Draw Station Map")

        imageSize = (400, 480)
        stationMapImg = Image.new('RGB', (imageSize[0], imageSize[1]), (255,255,255))
        draw = ImageDraw.Draw(stationMapImg)

        fontSize = 15
        font = ImageFont.truetype(r'asset/IBMPlexSans-ExtraLight.ttf', fontSize)

        queue = []
        queue.append(self.m_Tree)

        while len(queue) != 0:
            currentNode = queue.pop()

            #draw station point
            cubeSize = 2 if currentNode != self.m_Tree else 6
            draw.rectangle((currentNode.m_PixelPosition[0] - cubeSize, currentNode.m_PixelPosition[1] - cubeSize, currentNode.m_PixelPosition[0] + cubeSize, currentNode.m_PixelPosition[1] + cubeSize), fill = 0, outline=0, width=3)
            draw.text((currentNode.m_PixelPosition[0] + 5, currentNode.m_PixelPosition[1] - fontSize), currentNode.m_ID, fill = 0, font = font)

            for childNode in currentNode.m_ChildNodeStation:
                queue.append(childNode)

                # draw stations connection
                draw.line((currentNode.m_PixelPosition[0], currentNode.m_PixelPosition[1], childNode.m_PixelPosition[0], childNode.m_PixelPosition[1]), fill = 0)

        stationMapImg.save(self.m_StationMapFilename)

    def DrawTrainPosition(self):
        if self.m_Tree == None or len(self.allDepartures) == 0:
            return

        logging.info("Draw Train Position")
        mapImage = Image.open(self.m_StationMapFilename)
        draw = ImageDraw.Draw(mapImage)

        previousStop = None
        nextStop = None
        for departure in self.allDepartures:
            #Get current and next train station with current time
            currentTime = utility.GetCurrentDateTime()

            for index in range(len(departure.m_Timetable)):
                stop = departure.m_Timetable[index]
                if stop.m_AimedDepartureDatetime > currentTime:
                    nextStop = stop
                    break

                previousStop = stop

            if nextStop == None:
                logging.debug("No station code found on departure {} {}".format(departure.m_DestinationName, departure.m_ServiceID))
                continue

            if nextStop.m_AimedArrivalDatetime == None or previousStop.m_AimedDepartureDatetime == None:
                continue

            previousNodeStation = self.m_Tree.Search(previousStop.m_StationCode)
            nextNodeStation = self.m_Tree.Search(nextStop.m_StationCode)

            if previousNodeStation == None or nextNodeStation == None: #Can be an out of range node station or with no place result
                continue

            remainingTime = (currentTime - previousStop.m_AimedDepartureDatetime)
            totalTime = nextStop.m_AimedArrivalDatetime - previousStop.m_AimedDepartureDatetime

            timeRatio = remainingTime / totalTime
            timeRatio = utility.Clamp(timeRatio, 0.0, 1.0)

            interpolatedPixelPosition = utility.Lerp(previousNodeStation.m_PixelPosition, nextNodeStation.m_PixelPosition, timeRatio)
            draw.ellipse((interpolatedPixelPosition[0] - 3, interpolatedPixelPosition[1] - 3,interpolatedPixelPosition[0] + 3, interpolatedPixelPosition[1] + 3), fill = 'black')

        mapImage.save(self.m_StationMapFilename)

    def LoadConfig(self):
        '''
        Load the configuration file 'config.json'
        :return: json dictionary
        '''

        configFilename = 'config.json'
        utility.AssertOnFile(configFilename)

        with open(configFilename, 'r') as jsonConfig:
           data = json.load(jsonConfig)
           return data

    def InitDeparturesDictionaries(self):
        '''
        Initialization of the default dictionary parameters
        :return: Initialized
        '''

        templateDict ={
            'HEADER_DEPARTURE': time.strftime(self.config['timeCodeFormat']),
            'HEADER_DESTINATION': "{} ({})".format(self.stationName, self.transportRequest.m_StationCode)
        }

        for index in range(self.config['maxDepartures']):
            templateDict['DEPARTURE_0' + str(index)] = ''

        return templateDict

    def SleepBehavior(self):
        '''
        Sleep until the shortest time.
        :return: None
        '''
        self.b_CanRefresh = False

        minTime = min(self.m_DepartureRequestTimer.GetRemainingTime(), self.m_RefreshDisplayTimer.GetRemainingTime())
        minTime = min(minTime, self.m_AgendaTimer.GetRemainingTime())
        minTime = max(60, minTime) #Clamp value to 60sec minimum

        logging.info("Next update in {} seconds\n\n\n\n".format(minTime))
        time.sleep(minTime)

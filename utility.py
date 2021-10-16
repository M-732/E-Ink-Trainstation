import codecs
import logging
import os
import subprocess
import time

from datetime import datetime, timezone, timedelta
from http.client import HTTPConnection
from sys import platform

from PIL import Image

IsLaunchOnRaspberry = platform.startswith('linux')

if IsLaunchOnRaspberry:
    import lib.epd5in83_V2 as EPaperLib


def AssertOnFile(_filename: str):
    '''
    Assert the existence of a file.
    :param _filename: filename to check.
    :return: True if the file exist, otherwise, terminating the program execution.
    '''
    assert os.path.exists(_filename), "{} doest not exist".format(_filename)

def SetupLogging(_logLevel: int):
    '''
    Defines and configures the logging level.
    :param _logLevel: Correspond to the LogLevel in the logging module (CRITICAL, ERROR, WARNING,INFO, DEBUG)
    :return: None
    '''
    if _logLevel == logging.NOTSET:
        return

    log_format = "%(asctime)s - %(name)s - %(levelname)s | %(message)s"
    log_dateformat = "%Y-%m-%d|%H:%M:%S"

    logging.basicConfig(level=_logLevel, format=log_format, datefmt=log_dateformat)
    logger = logging.getLogger()
    logger.setLevel(level=_logLevel)

    '''Switches on logging of the requests module.'''
    if _logLevel == logging.INFO:
        return
    HTTPConnection.debuglevel = 1

    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def Clamp(_value, _min, _max):
    '''
    Clamp a value to the inclusive range of min and max.
    :param _value: The value to be clamped.
    :param _min: The lower bound of the result.
    :param _max: The upper bound of the result.
    :return: value clamped to the inclusive range of _min and _max
    '''
    return max(_min, min(_value, _max))

def GetCurrentDateTime():
    '''
    Get the current date and time into a Datetime class.
    The current datetime is construct with a specific timezone (UTC+01:00/London) but reset to None to compare two offset-naive.
    :return: Datetime class of the current day
    '''
    timezone_offset = 1.0  # London Standard Time (UTC+01:00)
    timezoneInfo = timezone(timedelta(hours=timezone_offset))

    currentDateTime = datetime.now(timezoneInfo)
    return currentDateTime.replace(tzinfo=None) #remove tzinfo to allow comparison between 2 offset-naive

def UpdateSVG(_templateSvgFilename: str, _outputSvgFilename: str, _inputDict: dict):
    '''
    Create an SVG file from a template by overwriting the default values.
    :param _templateSvgFilename: Reference template.
    :param _outputSvgFilename: name of the result
    :param _inputDict:
    :return: None
    '''
    logging.info("Update %s", _outputSvgFilename)

    AssertOnFile(_templateSvgFilename)

    streamRead = codecs.open(_templateSvgFilename, 'r', encoding='UTF-8').read()

    for output_key in _inputDict:
        streamRead = streamRead.replace(output_key, _inputDict[output_key], 1)
        logging.debug("Replaces \"{}\" to \"{}\"".format(output_key, _inputDict[output_key]))

    codecs.open(_outputSvgFilename, 'w', encoding='UTF-8').write(streamRead)


def ConvertSVG(_svgFilename: str, _outputFilename: str):
    '''
    Converts an SVG file to a png file
    :param _svgFilename: file to convert.
    :param _outputFilename: name of the converted file
    :return: None
    '''
    if not IsLaunchOnRaspberry:
        return

    AssertOnFile(_svgFilename)

    try:
        logging.info("RenderSVG()")

        args = ['inkscape', '--without-gui', '--file={}'.format(_svgFilename), '--export-png={}'.format(_outputFilename)]
        subprocess.run(args)

    except subprocess.CalledProcessError as e:
        logging.debug(e.output)

def DisplayOnEPaper(_filename: str):
    '''
    Display a png/jpg/bmp image to th e-ink screen
    :param _filename: filename to display
    :return: None
    '''

    logging.info("Display %s on ePaper", _filename)
    if not IsLaunchOnRaspberry:
        return

    AssertOnFile(_filename)
    assert _filename.lower().endswith(('.png', '.jpg', '.bmp')), "{} is not a PNG, JPG or BMP file"

    Himage = Image.open(_filename)

    ePaperDriver = EPaperLib.EPD()
    ePaperDriver.init()

    logging.info("Display image file on screen")
    ePaperDriver.display(ePaperDriver.getbuffer(Himage))
    ePaperDriver.sleep()

def ClearEPaper():
    logging.info("Clear image on screen")
    
    if IsLaunchOnRaspberry:
        return

    ePaperDriver = EPaperLib.EPD()
    ePaperDriver.init()

    ePaperDriver.Clear()
    ePaperDriver.sleep()

def MergeImages(_lhsFilename: str, _rhsFilename: str, _name: str, box = None):
    '''
    Pastes _rhsFilename image into _lhsFilename image.
    :param _lhsFilename: Reference image.
    :param _rhsFilename: Image to be copied.
    :param _name: Saves this image under the given filename. If no format is specified, the format to use is determined from the filename extension, if possible.
    :param box: An optional 4-tuple giving the region to paste into. If a 2-tuple is used instead, it’s treated as the upper left corner. If omitted or None, the source is pasted into the upper left corner
    :return: None
    '''

    firstImg = Image.open(_lhsFilename)
    secondImg = Image.open(_rhsFilename)

    firstImg.paste(secondImg, box)
    firstImg.save(_name)

def AbbreviateMessage(_abbreviationsDict: dict, _value: str):
    '''
    Abbreviate a message from a dictionnary
    :param _abbreviationsDict: Available abbreviations list.
    :param _value: message to abbreviate
    :return: The message in its abbreviated form.
    '''
    for key, value in _abbreviationsDict.items():
        _value = _value.replace(key, value)
    return _value

def Lerp(_startValue, _endValue, _value: float):
    '''
    Performs a linear interpolation between two values
    :param _startValue:
    :param _endValue:
    :param _value: _value is clamped to the range [0, 1].
    :return: a "lerped" position
    '''
    _value = Clamp(_value, 0.0, 1.0)
    return (_startValue[0] * (1 - _value) + _endValue[0] * _value,
            _startValue[1] * (1 - _value) + _endValue[1] * _value)


class Timer:
    def __init__(self, _duration: float = 0.0):
        self.m_StartTime = 0.0
        self.m_Duration = _duration

    def Reset(self):
        self.m_StartTime = time.time()

    def GetElapsedTime(self):
        return abs(self.m_StartTime - time.time())

    def GetRemainingTime(self):
        return self.m_Duration - self.GetElapsedTime() 

    def IsElapsed(self):
        return self.GetElapsedTime() > self.m_Duration

#!/usr/bin/python
# -*- coding:utf-8 -*-

import logging

from departure_manager import DepartureManager
from utility import SetupLogging

def main():
    SetupLogging(logging.INFO)

    departureManager = DepartureManager()

    try:
        while True:
            departureManager.Update()

    except IOError as e:
        logging.exception(e)
        exit()

    except KeyboardInterrupt:
        logging.debug("Keyboard Interrupt")
        exit()

if __name__ == "__main__":
    main()

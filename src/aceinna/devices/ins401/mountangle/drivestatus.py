from math import fabs, fmod, sqrt
import copy
import time
import logging
import os


class DriveStatus:
    def __init__(self):
        self.curinsresult = None
        self.lastinsresult = None

        self.statusstage = 0

        self.pattern = {
            'mode' : 0,
            'starttime' : -1,
            'curtime' : -1,
            'endtime' : -1,
            'angle' : 0.0,
            'distance' : 0
        }
        self.patterns = []

        self.liveresult = {
            'type' : 0,
            'totalangle_r' : 0,
            'totalangle_l' : 0,
            'distance' : 0,
            'starttime' : 0,
            'curtime' : 0,
        }

    def init_patterns(self):
        self.patterns = []
        self.pattern['mode'] = 0
        self.pattern['starttime'] = -1
        self.pattern['curtime'] = -1
        self.pattern['endtime'] = -1
        self.pattern['angle'] = 0.0
        self.pattern['distance'] = 0

    def clear_pattern(self):
        if self.pattern['starttime'] != -1:
            self.pattern['starttime'] = -1
            self.pattern['curtime'] = -1
            self.pattern['endtime'] = -1
            self.pattern['angle'] = 0.0
            self.pattern['distance'] = 0

    def checkdatapattern(self, estdata, mode):
        if (mode == 1):  # turn
            threshold = [5, 360, 0, 2]
        elif (mode == 2): # line
            threshold = [0, 5, 5, 360]
        ret = 0
        if (fabs(estdata['angle']) >= threshold[0] and fabs(estdata['angle']) <= threshold[1]):
            if (mode == 1 or estdata['distance'] > 0.3):
                if self.pattern['starttime'] == -1:
                    self.pattern['mode'] = mode
                    self.pattern['starttime'] = estdata['time']
                self.pattern['curtime'] = estdata['time']
                self.pattern['angle'] = self.pattern['angle'] + estdata['angle']
                self.pattern['distance'] = self.pattern['distance'] + estdata['distance']
            else:
                if (self.pattern['distance'] < 500):
                    ret = -2
                else:
                    ret = 2
        elif (fabs(estdata['angle']) >= threshold[2] and fabs(estdata['angle']) <= threshold[3]):
            if (mode == 1):
                if (fabs(self.pattern['angle']) < 30):
                    ret = -1
                else:
                    ret = 1
            elif (mode == 2):
                if (self.pattern['distance'] < 500):
                    ret = -2
                else:
                    ret = 2
        if (ret == 1 or ret == 2):
            self.pattern['endtime'] = estdata['time']
            self.patterns.append(copy.deepcopy(self.pattern))
        if (ret != 0):
            self.clear_pattern()
        return ret
    
    def calpatterns(self, mode):
        estflag = 0
        if (mode == 1):
            totalangle = [0, 0]
            for pattern in self.patterns:
                if pattern['mode'] == 1:
                    if (pattern['angle'] > 0):
                        totalangle[0] = totalangle[0] + pattern['angle']
                    else:
                        totalangle[1] = totalangle[1] + pattern['angle']
                
            self.liveresult['totalangle_r'] = totalangle[0]
            self.liveresult['totalangle_l'] = totalangle[1]

            if (totalangle[0] > 270 and totalangle[1] < -270):
                estflag = 3
            elif (totalangle[0] > 270):
                estflag = 2
            elif (totalangle[1] < -270):
                estflag = 1
            else:
                estflag = 0
        elif (mode == 2):
            if self.pattern['mode'] == 2:
                if (self.pattern['distance'] > 300):
                    self.liveresult['starttime'] = self.pattern['starttime']
                    self.liveresult['curtime'] = self.pattern['curtime']
                else:
                    self.liveresult['starttime'] = 0
                    self.liveresult['curtime'] = 0
                self.liveresult['distance'] = self.pattern['distance']

                if (self.pattern['distance'] > 700):
                    estflag = 7
                elif (self.pattern['distance'] > 500):
                    estflag = 6
                elif (self.pattern['distance'] > 300):
                    estflag = 5
                else:
                    estflag = 4
        return estflag

    def addestdata2patterns(self, estdata):
        self.liveresult['type'] = 0
        if (self.statusstage == 0):
            if (estdata['status'] == 2):
                self.liveresult['type'] = 1
                self.statusstage = 1
            elif (estdata['status'] == 3):
                self.liveresult['type'] = 2
                self.statusstage = 2
            elif (estdata['status'] == 4):
                self.statusstage = 0
            else:
                self.statusstage = 0

        elif (self.statusstage == 1):
            if (estdata['status'] == 3):
                self.liveresult['type'] = 2
                self.statusstage = 2

        elif (self.statusstage == 2):
            if (estdata['status'] == 2 or estdata['status'] == 3):
                self.checkdatapattern(estdata, 1)
                turnflag = self.calpatterns(1)
                if (turnflag == 3):
                    self.statusstage = 3
                    self.liveresult['type'] = 12
                elif (turnflag == 2):
                    self.liveresult['type'] = 11
                elif (turnflag == 1):
                    self.liveresult['type'] = 10
                elif (turnflag == 0):
                    self.liveresult['type'] = 9
            else:
                self.liveresult['type'] = 7
                self.statusstage = 0
                self.init_patterns()

        elif (self.statusstage == 3):
            if (estdata['status'] == 2 or estdata['status'] == 3):
                self.checkdatapattern(estdata, 2)
                lineflag = self.calpatterns(2)
                if (lineflag == 7):
                    self.liveresult['type'] = 15
                elif (lineflag == 6):
                    self.liveresult['type'] = 14
                elif (lineflag == 5):
                    self.liveresult['type'] = 13
            else:
                self.liveresult['type'] = 8
                self.liveresult['starttime'] = 0
                self.liveresult['curtime'] = 0
                self.liveresult['distance'] = 0
                self.clear_pattern()

    def addestcheckdata(self, curinsresult, lastinsresult):
        angle = curinsresult['heading'] - lastinsresult['heading']
        while (angle > 180):
            angle = angle - 360
        while (angle < -180):
            angle = angle + 360
        distance = sqrt(0.25*(curinsresult['vn'] + lastinsresult['vn'])*(curinsresult['vn'] + lastinsresult['vn']) +
                        0.25*(curinsresult['ve'] + lastinsresult['ve'])*(curinsresult['ve'] + lastinsresult['ve']))
        estcheckdata = {
            'status' : curinsresult['insstatus'],
            'postype' : curinsresult['inspostype'],
            'time' : curinsresult['timestamp'],
            'angle' : angle,
            'distance' : distance
        }
        return estcheckdata


    def addrawdata(self, rawdata, type):
        if type == 0:
            self.curinsresult = {
                'week' : rawdata[0],
                'timestamp': rawdata[1]/1000,
                'insstatus': rawdata[2],
                'inspostype': rawdata[3],
                'lat' : rawdata[4],
                'lon' : rawdata[5],
                'hight' : rawdata[6],
                'vn' : rawdata[7],
                've' : rawdata[8],
                'vd' : rawdata[9],
                'roll' : rawdata[10],
                'pitch' : rawdata[11],
                'heading' : rawdata[12]
            }
        elif type == 1:
            self.curinsresult = {
                'week' : rawdata[0],
                'timestamp': rawdata[1]/1000,
                'insstatus': rawdata[2],
                'inspostype': rawdata[3],
                'lat' : rawdata[4],
                'lon' : rawdata[5],
                'hight' : rawdata[6],
                'vn' : rawdata[7],
                've' : rawdata[8],
                'vd' : rawdata[9],
                'roll' : rawdata[12],
                'pitch' : rawdata[13],
                'heading' : rawdata[14]
            }

        if fmod(self.curinsresult['timestamp'], 1) < 0.01:
            if self.lastinsresult != None:
                estcheckdata = self.addestcheckdata(self.curinsresult, self.lastinsresult)
                self.addestdata2patterns(estcheckdata)

            self.lastinsresult = self.curinsresult

    def getresult(self):
        if fmod(self.curinsresult['timestamp'], 1) < 0.01:
            return self.liveresult
        else:
            return None

    def getpatterns(self):
        return self.patterns


if __name__ == '__main__':
        f_testins = open('E:\\workspace\\pythondriver\\code\\python-openimu\\mountangle\\data\\novatel_example\\user_2021_03_30_16_18_11_i1.csv', 'r')
        
        drivestatus = DriveStatus()

        run_logger = logging.getLogger(__file__)
        run_logger.setLevel(logging.DEBUG)
        logfile = os.path.join("E:\\workspace\\pythondriver\\code\\python-openimu\\mountangle\\data\\novatel_example\\", 'run_logger.txt')
        fh = logging.FileHandler(logfile, mode='w')
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        run_logger.addHandler(fh)
        run_logger.addHandler(ch)
        
        # run_logger.info("run {0}".format(f_testins))

        while True:
            line = f_testins.readline()
            if line == None or line == '':
                break
            line = line.strip().replace(' ', '')
            linesplit = line.split(',')
            insdatamap = map(float, linesplit)
            insdata = list(insdatamap)
            insdata[1] = insdata[1] * 1000

            drivestatus.addrawdata(insdata)
            linerun_result = drivestatus.getresult()
            if linerun_result != None:
                run_logger.debug("{0}".format(linerun_result))

        pattern_result = drivestatus.getpatterns()
        run_logger.debug("{0}".format(pattern_result))

        while True:
            print('end')
            time.sleep(1)

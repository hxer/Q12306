#!/usr/bin/env python
#-*- coding:utf-8 -*-

"""
by janes, 2015.12.3
"""

from __future__ import unicode_literals
from __future__ import print_function
import logging
import sys
import time

from common import *
from mail import Mail

from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(filename="queryticket.log",
    level=logging.DEBUG,
    format='%(asctime)s|%(filename)s|%(funcName)s|line:%(lineno)d%(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M'
)


def printItem(items, name):
    msgs = items.get(name, "")
    if isinstance(msgs, list):
        for msg in msgs:
          print(msg)
    else:
        print(msgs)


class BookQuery(Base12306):
    """
    """
    def __init__(self, cfg):
        """
            params:
                cfg: class Config
        """
        Base12306.__init__(self)
        self.stations = self.getstations()
        self.conf = self.readConfig(cfg)
        if not self.conf:
            logging.error("read conf error, system exiting")
            sys.exit()

    def querytickets(self, train_date):
        """
        """
        # parameters必须按如下指定顺序排列，否则返回结果为 -1
        parameters = [
            ('leftTicketDTO.train_date', train_date),
            ('leftTicketDTO.from_station', self.stations[ self.conf['from_city_name']]),
            ('leftTicketDTO.to_station', self.stations[ self.conf['to_city_name']]),
            ('purpose_codes', self.conf['purpose_codes']),
        ]
        response = self.geturl(self.urls['bookquery'],params=parameters)
        if 200 != response.status_code and len(response.content) < 10:
            logging.error("request error code: %s, content: %s",
                response.status_code,response.content)
        try:
            jdata = response.json()
        except Exception as e:
            logging.error("parse json error: %s",e)
            return None
        else:
            return self.parsejson(jdata)


    def parsejson(self, jdata):
        """
        """
        traindict = dict()
        if 'data' not in jdata.keys():
            err_msg = jdata.get('messages', 'Not get error messages')
            logging.error(err_msg)
        else:
            # jdata['data'] is list
            for train in jdata['data']:
                train = train['queryLeftNewDTO']
                if (train['station_train_code'] in self.conf['station_train_code']
                    or 'all' in self.conf['station_train_code']):
                    traindict[train['station_train_code']] = self.get_validseat(train)
        return traindict

    def get_validseat(self, train):
        """
        """
        return {seat:self.getnum(train[seat+'_num']) for seat in self.conf['seat_type'] if self.getnum(train[seat+'_num']) != '0'}

    def getnum(self, seatnum):
        """
        """
        return '0' if '无' in seatnum or '--' in seatnum else seatnum


def sendmail(cfg_file, subject, msg):
    """
    """
    cfg = Config(cfg_file)
    to_mail_list = cfg.to_mail_list
    from_mail = "xxx@163.com"
    passwd = "xxxx"
    mail = Mail(from_mail, passwd)
    mail.sendplain(to_mail_list, subject, msg)

def task(cfg_file):
    """
    """
    cfg = Config(cfg_file)
    seatname = {value:key for key, value in SEATTYPE.items()}
    msg = ''
    qticket = BookQuery(cfg)
    for train_date in qticket.conf['train_dates']:
        traindict = qticket.querytickets(train_date)
        if traindict:
            for train_code in traindict.keys():
                if traindict[train_code]:
                    msg = msg + train_date + '\t' + train_code
                    for seat, strnum in traindict[train_code].items():
                        msg = msg + '\n\t' + seatname[seat] + ': ' + strnum
                    msg += '\n'
                info_msg = "{0}\t{1}\t{2}".format(train_date, train_code, traindict[train_code])
                logging.info(info_msg)
        time.sleep(20)
    if msg:
        print(msg)
        sendmail(cfg_file, '抢火车票了...from janes', msg)

if __name__=="__main__":
    debug = True
    cfg_files = ["config.ini"]
    if not debug:
        sched = BlockingScheduler()
        for cfg_file in cfg_files:
            sched.add_job(task, args=(cfg_file,), trigger="cron", hour='6-23', minute='0-59/10')
        try:
            sched.start()
        except:
            sched.shutdown()
    else:
        task(cfg_files[0])
        print("finished")

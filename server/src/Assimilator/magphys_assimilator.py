#! /usr/bin/env python

import Assimilator
import os, re, signal, sys, time, hashlib
import boinc_path_config
from Boinc import database, boinc_db, boinc_project_path, configxml, sched_messages
from xml.dom.minidom import parseString
import xml.dom

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, REAL, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
class WorkUnitResult(Base):
    __tablename__ = 'work_unit_result'
    
    wuresult_id = Column(Integer, primary_key=True)
    point_name = Column(String(100))
    i_sfh = Column(Float)
    i_ir = Column(Float)
    chi2 = Column(Float)
    redshift = Column(Float)
    fmu_sfh = Column(Float)
    fmu_ir = Column(Float)
    mu = Column(Float)
    tauv = Column(Float)
    s_sfr = Column(Float)
    m = Column(Float)
    ldust = Column(Float)
    t_w_bc = Column(Float)
    t_c_ism = Column(Float)
    xi_c_tot = Column(Float)
    xi_pah_tot = Column(Float)
    xi_mir_tot = Column(Float)
    x_w_tot = Column(Float)
    tvism = Column(Float)
    mdust = Column(Float)
    sfr = Column(Float)
    i_opt = Column(Float)
    dmstar = Column(Float)
    dfmu_aux = Column(Float)
    dz = Column(Float)
    
class WorkUnitFilter(Base):
    __tablename__ = 'work_unit_filter'
    
    wufilter_id = Column(Integer, primary_key=True)
    wuresult_id = Column(Integer, ForeignKey('work_unit_result.wuresult_id'))
    filter_name = Column(String(100))
    observed_flux = Column(Float)
    observational_uncertainty = Column(Float)
    flux_bfm = Column(Float)
    
    work_unit = relationship("WorkUnitResult", backref=backref('filters', order_by=wufilter_id))
    
class WorkUnitParameter(Base):
    __tablename__ = 'work_unit_parameter'
    
    wuparameter_id = Column(Integer, primary_key=True)
    wuresult_id = Column(Integer, ForeignKey('work_unit_result.wuresult_id'))
    parameter_name = Column(String(100))
    percentile2_5 = Column(Float)
    percentile16 = Column(Float)
    percentile50 = Column(Float)
    percentile84 = Column(Float)
    percentile97_5 = Column(Float)
    
    work_unit = relationship("WorkUnitResult", backref=backref('parameters', order_by=wuparameter_id))

class WorkUnitHistogram(Base):
    __tablename__ = 'work_unit_histogram'
    
    wuhistogram_id = Column(Integer, primary_key=True)
    wuparameter_id = Column(Integer, ForeignKey('work_unit_parameter.wuparameter_id'))
    x_axis = Column(Float)
    hist_value = Column(Float)
    
    parameter = relationship("WorkUnitParameter", backref=backref('histograms', order_by=wuhistogram_id))
    
class WorkUnitUser(Base):
    __tablename__ = 'work_unit_user'
    
    wuuser_id = Column(Integer, primary_key=True)
    wuresult_id = Column(Integer, ForeignKey('work_unit_result.wuresult_id'))
    userid = Column(Integer)
    create_time = Column(TIMESTAMP)
    
    work_unit = relationship("WorkUnitResult", backref=backref('users', order_by=wuuser_id))
            
class MagphysAssimilator(Assimilator.Assimilator):
    
    def __init__(self):
        Assimilator.Assimilator.__init__(self)
        #super(MagphysAssimilator, self).__init__(self)
        
        login = "mysql://root:@localhost/magphys_as"
        try:
             f = open(os.path.expanduser("~/Magphys.Profile") , "r")
             for line in f:
                 if line.startswith("url="):
                   login = line[4:]
             f.close()
        except IOError as e:
            pass
            
        engine = create_engine(login)
        self.Session = sessionmaker(bind=engine)
    
    def get_output_file_infos(self, result, list):
        dom = parseString(result.xml_doc_in)
        for node in dom.getElementsByTagName('file_name'):
            list.append(node.firstChild.nodeValue)
        
    def getResult(self, session, pointName):
        pxresult = session.query(WorkUnitResult).filter("point_name=:name").params(name=pointName).first()
        doAdd = False
        if (pxresult == None):
            pxresult = WorkUnitResult()
        else:
            for filter in pxresult.filters:
                session.delete(filter)
            for parameter in pxresult.parameters:
                for histogram in parameter.histograms:
                    session.delete(histogram)
                session.delete(parameter)
            for user in pxresult.users:
                session.delete(user)
        pxresult.point_name = pointName;
        pxresult.filters = []
        pxresult.parameters = []
        return pxresult
    
    def saveResult(self, session, pxresult, results):
        for result in results:
            usr = WorkUnitUser()
            usr.userid = result.userid
            #usr.create_time = 
            pxresult.users.append(usr)
            
        if pxresult.wuresult_id == None:
            session.add(pxresult)
    
    def processResult(self, session, outFile, results):
        """
        Read the output file, add the values to the WorkUnitResult row, and insert the filter,
        parameter and histogram rows.
        """
        f = open(outFile , "r")
        lineNo = 0
        pointName = None
        pxresult = None
        parameter = None
        percentilesNext = False
        histogramNext = False
        skynetNext = False
        for line in f:
            lineNo = lineNo + 1
            
            if line.startswith(" ####### "):
                if pxresult:
                    self.saveResult(session, pxresult, results)
                values = line.split()
                pointName = values[1]
                print pointName
                pxresult = self.getResult(session, pointName)
                lineNo = 0
                percentilesNext = False;
                histogramNext = False
                skynetNext = False
            elif pxresult:
                if lineNo == 2:
                    filterNames = line.split()
                    for filterName in filterNames:
                        if filterName != '#':
                            filter = WorkUnitFilter()
                            filter.filter_name = filterName
                            pxresult.filters.append(filter)
                elif lineNo == 3:
                    idx = 0
                    values = line.split()
                    for value in values:
                        filter = pxresult.filters[idx]
                        filter.observed_flux = float(value)
                        idx = idx + 1
                elif lineNo == 4:
                    idx = 0
                    values = line.split()
                    for value in values:
                        filter = pxresult.filters[idx]
                        filter.observational_uncertainty = float(value)
                        idx = idx + 1
                elif lineNo == 9:
                    values = line.split()
                    pxresult.i_sfh = float(values[0])
                    pxresult.i_ir = float(values[1])
                    pxresult.chi2 = float(values[2])
                    pxresult.redshift = float(values[3])
                    #for value in values:
                    #    print value
                elif lineNo == 11:
                    values = line.split()
                    pxresult.fmu_sfh = float(values[0])
                    pxresult.fmu_ir = float(values[1])
                    pxresult.mu = float(values[2])
                    pxresult.tauv = float(values[3])
                    pxresult.s_sfr = float(values[4])
                    pxresult.m = float(values[5])
                    pxresult.ldust = float(values[6])
                    pxresult.t_w_bc = float(values[7])
                    pxresult.t_c_ism = float(values[8])
                    pxresult.xi_c_tot = float(values[9])
                    pxresult.xi_pah_tot = float(values[10])
                    pxresult.xi_mir_tot = float(values[11])
                    pxresult.x_w_tot = float(values[12])
                    pxresult.tvism = float(values[13])
                    pxresult.mdust = float(values[14])
                    pxresult.sfr = float(values[15])
                elif lineNo == 13:
                    idx = 0
                    values = line.split()
                    for value in values:
                        filter = pxresult.filters[idx]
                        filter.flux_bfm = float(value)
                        idx = idx + 1
                elif lineNo > 13:
                    if line.startswith("# ..."):
                        parts = line.split('...')
                        parameterName = parts[1].strip()
                        parameter = WorkUnitParameter()
                        parameter.parameter_name = parameterName;
                        pxresult.parameters.append(parameter)
                        percentilesNext = False;
                        histogramNext = True
                        skynetNext = False
                    elif line.startswith("#....percentiles of the PDF......") and parameter != None:
                        percentilesNext = True;
                        histogramNext = False
                        skynetNext = False
                    elif line.startswith(" #...theSkyNet"):
                        percentilesNext = False;
                        histogramNext = False
                        skynetNext = True
                    elif percentilesNext:
                        values = line.split()
                        parameter.percentile2_5 = float(values[0])
                        parameter.percentile16 = float(values[1])
                        parameter.percentile50 = float(values[2])
                        parameter.percentile84 = float(values[3])
                        parameter.percentile97_5 = float(values[4])
                        percentilesNext = False;
                    elif histogramNext:
                        hist = WorkUnitHistogram()
                        values = line.split()
                        hist.x_axis = float(values[0])
                        hist.hist_value = float(values[1])
                        parameter.histograms.append(hist)
                    elif skynetNext:
                        values = line.split()
                        pxresult.i_opt = float(values[0])
                        pxresult.i_ir = float(values[1])
                        pxresult.dmstar = float(values[2])
                        pxresult.dfmu_aux = float(values[3])
                        pxresult.dz = float(values[4])
                        skynetNext = False
                    
        f.close()
        if pxresult:
            self.saveResult(session, pxresult, results)
        
    def assimilate_handler(self, wu, results, canonical_result):
        """
        Process the Results.
        """

        if (wu.canonical_resultid):
            file_list = []
            self.get_output_file_infos(canonical_result, file_list)
            
            outFile = None;
            for file in file_list:
                print file
                outFile = file
                    
            if (outFile):
                session = self.Session()
                self.processResult(session, outFile, results)
                session.commit()
            else:
                self.logCritical("The output file was not found\n")
        else:
            report_errors(wu)
            return -1
            
        return 0;
    
if __name__ == '__main__':
    asm = MagphysAssimilator()
    asm.run()
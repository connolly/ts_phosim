#!/usr/bin/env python

import os
import argparse
import numpy as np

from lsst.ts.wep.Utility import FilterType, CamType, runProgram
from lsst.ts.wep.ctrlIntf.WEPCalculationFactory import WEPCalculationFactory
from lsst.ts.wep.ctrlIntf.RawExpData import RawExpData

from lsst.ts.ofc.Utility import InstName
from lsst.ts.ofc.ctrlIntf.OFCCalculationFactory import OFCCalculationFactory

from lsst.ts.phosim.telescope.TeleFacade import TeleFacade
from lsst.ts.phosim.PhosimCmpt import PhosimCmpt
from lsst.ts.phosim.SkySim import SkySim
from lsst.ts.phosim.Utility import getPhoSimPath, getAoclcOutputPath
from lsst.ts.phosim.PlotUtil import plotFwhmOfIters


def main(phosimDir, numPro, iterNum, baseOutputDir, isEimg=False,
         useMinDofIdx=False, inputSkyFilePath="", m1m3ForceError=0.05):

    # Prepare the calibration products (only for the amplifier images)
    sensorNameList = _getComCamSensorNameList()
    if (not isEimg):
        fakeFlatDir = _makeCalibs(baseOutputDir, sensorNameList)

    # Make the ISR directory
    isrDirName = "input"
    isrDir = os.path.join(baseOutputDir, isrDirName)
    _makeDir(isrDir)

    # Test star magnitude
    starMag = 15

    # Survey parameters
    filterType = FilterType.REF
    raInDeg = 0.0
    decInDeg = 0.0
    rotAngInDeg = 0.0

    # Prepare the components
    phosimCmpt = _preparePhosimCmpt(phosimDir, filterType, raInDeg, decInDeg,
                                    rotAngInDeg, numPro, isEimg,
                                    m1m3ForceError)

    wepCalc = _prepareWepCalc(isrDir, filterType, raInDeg, decInDeg,
                              rotAngInDeg, isEimg)

    tele = phosimCmpt.getTele()
    defocalDisInMm = tele.getDefocalDistInMm()
    wepCalc.setDefocalDisInMm(defocalDisInMm)

    ofcCalc = _prepareOfcCalc(filterType, rotAngInDeg)

    # Ingest the calibration products (only for the amplifier images)
    if (not isEimg):
        wepCalc.ingestCalibs(fakeFlatDir)

    # Only use 10 hexapod positions and first 3 bending modes of M1M3 and M2
    if (useMinDofIdx):
        _useMinDofIdx(ofcCalc)

    # Set the telescope state to be the same as the OFC
    state0 = ofcCalc.getStateAggregated()
    phosimCmpt.setDofInUm(state0)

    # Do the iteration
    obsId = 9006000
    opdZkFileName = "opd.zer"
    wfsZkFileName = "wfs.zer"
    opdPssnFileName = "PSSN.txt"
    outputDirName = "pert"
    outputImgDirName = "img"
    iterDefaultDirName = "iter"
    dofInUmFileName = "dofPertInNextIter.mat"
    skyInfoFileName = "skyComCamInfo.txt"
    for iterCount in range(iterNum):

        # Set the observation Id
        phosimCmpt.setSurveyParam(obsId=obsId)

        # The iteration directory
        iterDirName = "%s%d" % (iterDefaultDirName, iterCount)

        # Set the output directory
        outputDir = os.path.join(baseOutputDir, iterDirName, outputDirName)
        phosimCmpt.setOutputDir(outputDir)

        # Set the output image directory
        outputImgDir = os.path.join(baseOutputDir, iterDirName,
                                    outputImgDirName)
        phosimCmpt.setOutputImgDir(outputImgDir)

        # Generate the OPD image
        argString = phosimCmpt.getComCamOpdArgsAndFilesForPhoSim()
        phosimCmpt.runPhoSim(argString)

        # Analyze the OPD data
        phosimCmpt.analyzeComCamOpdData(zkFileName=opdZkFileName,
                                        pssnFileName=opdPssnFileName)

        # Get the PSSN from file
        pssn = phosimCmpt.getOpdPssnFromFile(opdPssnFileName)
        print("Calculated PSSN is %s." % pssn)

        # Get the GQ effective FWHM from file
        gqEffFwhm = phosimCmpt.getOpdGqEffFwhmFromFile(opdPssnFileName)
        print("GQ effective FWHM is %.4f." % gqEffFwhm)

        # Set the FWHM data
        listOfFWHMSensorData = phosimCmpt.getListOfFwhmSensorData(
            opdPssnFileName, sensorNameList)
        ofcCalc.setFWHMSensorDataOfCam(listOfFWHMSensorData)

        # Prepare the faked sky
        if (inputSkyFilePath == ""):
            # According to the OPD field positions
            metr = phosimCmpt.getOpdMetr()
            skySim = _prepareSkySim(metr, starMag)
            print("Use the default OPD field positions to be star positions.")
            print("The star magnitude is chosen to be %.2f." % starMag)
        else:
            skySim = _prepareSkySimBySkyFile(inputSkyFilePath)

        # Output the sky information
        outputSkyInfoFilePath = os.path.join(outputDir, skyInfoFileName)
        skySim.exportSkyToFile(outputSkyInfoFilePath)
        wepCalc.setSkyFile(outputSkyInfoFilePath)

        # Assign the entra- and intra-focal observation Id
        extraObsId = obsId + 1
        intraObsId = obsId + 2

        # Generate the defocal images
        simSeed = 1000
        argStringList = phosimCmpt.getComCamStarArgsAndFilesForPhoSim(
            extraObsId, intraObsId, skySim, simSeed=simSeed,
            cmdSettingFileName="starDefault.cmd",
            instSettingFileName="starSingleExp.inst")
        for argString in argStringList:
            phosimCmpt.runPhoSim(argString)

        # Repackage the images based on the image type
        if (isEimg):
            phosimCmpt.repackageComCamEimgFromPhoSim()
        else:
            phosimCmpt.repackageComCamAmpImgFromPhoSim()

        # Collect the defocal images
        intraRawExpData = RawExpData()
        intraRawExpDir = os.path.join(outputImgDir,
                                      phosimCmpt.getIntraFocalDirName())
        intraRawExpData.append(intraObsId, 0, intraRawExpDir)

        extraRawExpData = RawExpData()
        extraRawExpDir = os.path.join(outputImgDir,
                                      phosimCmpt.getExtraFocalDirName())
        extraRawExpData.append(extraObsId, 0, extraRawExpDir)

        # Calculate the wavefront error and DOF
        listOfWfErr = wepCalc.calculateWavefrontErrors(
            intraRawExpData, extraRawExpData=extraRawExpData)
        ofcCalc.calculateCorrections(listOfWfErr)

        # Record the wfs error with the same order as OPD for the comparison
        phosimCmpt.reorderAndSaveWfErrFile(listOfWfErr, sensorNameList,
                                           zkFileName=wfsZkFileName)

        # Set the new aggregated DOF to phosimCmpt
        dofInUm = ofcCalc.getStateAggregated()
        phosimCmpt.setDofInUm(dofInUm)

        # Save the DOF file
        phosimCmpt.saveDofInUmFileForNextIter(
            dofInUm, dofInUmFileName=dofInUmFileName)

        # Add the observation ID by 10 for the next iteration
        obsId += 10

    # Summarize the FWHM
    pssnFiles = [os.path.join(baseOutputDir, "%s%d" % (iterDefaultDirName, num),
                 outputImgDirName, opdPssnFileName) for num in range(iterNum)]
    saveToFilePath = os.path.join(baseOutputDir, "fwhmIters.png")
    plotFwhmOfIters(pssnFiles, saveToFilePath=saveToFilePath)


def _getComCamSensorNameList():

    sensorNameList = ["R22_S00", "R22_S01", "R22_S02", "R22_S10", "R22_S11",
                      "R22_S12", "R22_S20", "R22_S21", "R22_S22"]
    return sensorNameList


def _makeCalibs(outputDir, sensorNameList):

    fakeFlatDirName = "fake_flats"
    fakeFlatDir = os.path.join(outputDir, fakeFlatDirName)
    _makeDir(fakeFlatDir)

    detector = " ".join(sensorNameList)
    _genFakeFlat(fakeFlatDir, detector)

    return fakeFlatDir


def _makeDir(directory):

    if (not os.path.exists(directory)):
        os.makedirs(directory)


def _genFakeFlat(fakeFlatDir, detector):

    currWorkDir = os.getcwd()

    os.chdir(fakeFlatDir)
    _makeFakeFlat(detector)
    os.chdir(currWorkDir)


def _makeFakeFlat(detector):

    command = "makeGainImages.py"
    argstring = "--detector_list %s" % detector
    runProgram(command, argstring=argstring)


def _preparePhosimCmpt(phosimDir, filterType, raInDeg, decInDeg, rotAngInDeg,
                       numPro, isEimg, m1m3ForceError):

    # Set the Telescope facade class
    tele = TeleFacade()
    tele.addSubSys(addCam=True, addM1M3=True, addM2=True)
    tele.setPhoSimDir(phosimDir)

    # Prepare the phosim component
    phosimCmpt = PhosimCmpt(tele)

    # Set the telescope survey parameters
    boresight = (raInDeg, decInDeg)
    zAngleInDeg = 27.0912
    phosimCmpt.setSurveyParam(filterType=filterType, boresight=boresight,
                              zAngleInDeg=zAngleInDeg, rotAngInDeg=rotAngInDeg)

    # Update the setting file if needed
    settingFile = phosimCmpt.getSettingFile()
    if (numPro > 1):
        settingFile.updateSetting("numPro", numPro)
    if isEimg:
        settingFile.updateSetting("e2ADC", 0)

    # Set the seed number for M1M3 surface
    seedNum = 6
    phosimCmpt.setSeedNum(seedNum)

    # Set the M1M3 force error
    phosimCmpt.setM1M3ForceError(m1m3ForceError)

    return phosimCmpt


def _prepareWepCalc(isrDirPath, filterType, raInDeg, decInDeg, rotAngInDeg,
                    isEimg):

    wepCalc = WEPCalculationFactory.getCalculator(CamType.ComCam, isrDirPath)
    wepCalc.setFilter(filterType)
    wepCalc.setBoresight(raInDeg, decInDeg)
    wepCalc.setRotAng(rotAngInDeg)

    if (isEimg):
        settingFile = wepCalc.getSettingFile()
        settingFile.updateSetting("imageType", "eimage")

    return wepCalc


def _prepareOfcCalc(filterType, rotAngInDeg):

    ofcCalc = OFCCalculationFactory.getCalculator(InstName.COMCAM)
    ofcCalc.setFilter(filterType)
    ofcCalc.setRotAng(rotAngInDeg)
    ofcCalc.setGainByPSSN()

    return ofcCalc


def _prepareSkySim(opdMetr, starMag):

    skySim = SkySim()

    starId = 0
    raInDegList, declInDegList = opdMetr.getFieldXY()
    for raInDeg, declInDeg in zip(raInDegList, declInDegList):
        # It is noted that the field position might be < 0. But it is not the
        # same case for ra (0 <= ra <= 360).
        if (raInDeg < 0):
            raInDeg += 360.0
        skySim.addStarByRaDecInDeg(starId, raInDeg, declInDeg, starMag)
        starId += 1

    return skySim


def _prepareSkySimBySkyFile(inputSkyFilePath):

    skySim = SkySim()

    absSkyFilePath = os.path.abspath(inputSkyFilePath)
    skySim.addStarByFile(absSkyFilePath)

    return skySim


def _useMinDofIdx(ofcCalc):

    ztaac = ofcCalc.getZtaac()

    m1m3Bend = np.zeros(20, dtype=int)
    m1m3Bend[0: 3] = 1

    m2Bend = np.zeros(20, dtype=int)
    m2Bend[0: 3] = 1

    ztaac.setZkAndDofInGroups(m1m3Bend=m1m3Bend, m2Bend=m2Bend)


if __name__ == "__main__":

    # Set the parser
    parser = argparse.ArgumentParser(
        description="Run AOS closed-loop simulation (default is amp files).")
    parser.add_argument("--numOfProc", type=int, default=1,
                        help="number of processor to run PhoSim (default: 1)")
    parser.add_argument("--iterNum", type=int, default=5,
                        help="number of closed-loop iteration (default: 5)")
    parser.add_argument("--output", type=str, default="",
                        help="output directory")
    parser.add_argument('--eimage', default=False, action='store_true',
                        help='Use the eimage files')
    parser.add_argument('--minDof', default=False, action='store_true',
                        help='Use 10 hexapod positions and first 3 bending modes of M1M3 and M2')
    parser.add_argument("--skyFile", type=str, default="",
                        help="Star Id, ra, dec, and magnitude")
    parser.add_argument("--m1m3FErr", type=float, default=0.05,
                        help="Ratio of M1M3 actuator force error between 0 and 1 (default: 0.05)")
    args = parser.parse_args()

    # Run the simulation
    phosimDir = getPhoSimPath()

    if (args.output == ""):
        outputDir = getAoclcOutputPath()
    else:
        outputDir = args.output
    os.makedirs(outputDir, exist_ok=True)

    main(phosimDir, args.numOfProc, args.iterNum, outputDir,
         isEimg=args.eimage, useMinDofIdx=args.minDof,
         inputSkyFilePath=args.skyFile, m1m3ForceError=args.m1m3FErr)

import os
import unittest
import numpy as np

from lsst.ts.phosim.telescope.M2Sim import M2Sim

from lsst.ts.phosim.Utility import getModulePath


class TestM2Sim(unittest.TestCase):
    """ Test the M2Sim class."""

    def setUp(self):

        self.testM2Data = os.path.join(getModulePath(), "tests", "testData",
                                       "testM2Func")
        self.outputDir = os.path.join(getModulePath(), "output")

    @classmethod
    def setUpClass(cls):
        """Only do the instantiation for one time for the slow speed."""

        cls.m2 = M2Sim()

    def testInit(self):

        self.assertEqual(self.m2.getInnerRinM(), 0.9)
        self.assertEqual(self.m2.getOuterRinM(), 1.71)

    def testGetActForce(self):

        forceInN = self.m2.getActForce()
        self.assertEqual(forceInN.shape, (156, 156))

    def testGetPrintthz(self):

        zAngleInDeg = 27.0912
        zAngleInRadian = np.deg2rad(zAngleInDeg)
        printthzInUm = self.m2.getPrintthz(zAngleInRadian)

        ansFilePath = os.path.join(self.testM2Data, "M2printthz.txt")
        ansPrintthzInUm = np.loadtxt(ansFilePath)
        self.assertLess(np.sum(np.abs(printthzInUm-ansPrintthzInUm)), 1e-10)

    def testGetTempCorr(self):

        m2TzGrad = -0.0675
        m2TrGrad = -0.1416
        tempCorrInUm = self.m2.getTempCorr(m2TzGrad, m2TrGrad)

        ansFilePath = os.path.join(self.testM2Data, "M2tempCorr.txt")
        ansTempCorrInUm = np.loadtxt(ansFilePath)
        self.assertLess(np.sum(np.abs(tempCorrInUm-ansTempCorrInUm)), 1e-10)

    def testGetMirrorResInMmInZemax(self):

        numTerms = 28
        self._setSurfAlongZ()
        zcInMmInZemax = self.m2.getMirrorResInMmInZemax()[3]

        ansFilePath = os.path.join(self.testM2Data, "sim6_M2zlist.txt")
        ansZcInUmInZemax = np.loadtxt(ansFilePath)
        ansZcInMmInZemax = ansZcInUmInZemax*1e-3

        delta = np.sum(np.abs(zcInMmInZemax[0:numTerms] -
                              ansZcInMmInZemax[0:numTerms]))
        self.assertLess(delta, 1e-9)

    def _setSurfAlongZ(self):

        zAngleInDeg = 27.0912
        zAngleInRadian = np.deg2rad(zAngleInDeg)
        printthzInUm = self.m2.getPrintthz(zAngleInRadian)

        m2TzGrad = -0.0675
        m2TrGrad = -0.1416
        tempCorrInUm = self.m2.getTempCorr(m2TzGrad, m2TrGrad)

        mirrorSurfInUm = printthzInUm + tempCorrInUm
        self.m2.setSurfAlongZ(mirrorSurfInUm)

    def testWriteMirZkAndGridResInZemax(self):

        resFile = self._writeMirZkAndGridResInZemax()
        content = np.loadtxt(resFile)

        ansFilePath = os.path.join(self.testM2Data, "sim6_M2res.txt")
        ansContent = np.loadtxt(ansFilePath)

        self.assertLess(np.sum(np.abs(content[0, :]-ansContent[0, :])), 1e-9)
        self.assertLess(np.sum(np.abs(content[1:, 0]-ansContent[1:, 0])), 1e-9)

        os.remove(resFile)

    def _writeMirZkAndGridResInZemax(self):

        self._setSurfAlongZ()
        resFile = os.path.join(self.outputDir, "M2res.txt")
        self.m2.writeMirZkAndGridResInZemax(resFile=resFile)

        return resFile

    def testShowMirResMap(self):

        resFile = self._writeMirZkAndGridResInZemax()
        writeToResMapFilePath = os.path.join(self.outputDir, "M2resMap.png")

        self.m2.showMirResMap(resFile,
                              writeToResMapFilePath=writeToResMapFilePath)
        self.assertTrue(os.path.isfile(writeToResMapFilePath))

        os.remove(resFile)
        os.remove(writeToResMapFilePath)


if __name__ == "__main__":

    # Run the unit test
    unittest.main()

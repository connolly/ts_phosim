import numpy as np
from lsst.ts.wep.SourceProcessor import SourceProcessor

import matplotlib.pyplot as plt
plt.switch_backend('Agg')


def plotResMap(zfInMm, xfInMm, yfInMm, outerRinMm, resFile=None,
               writeToResMapFilePath=None, dpi=None):
    """Plot the mirror residue map.

    Parameters
    ----------
    zfInMm : numpy.ndarray
        Surface map in mm.
    xfInMm : numpy.ndarray
        X position in mm.
    yfInMm : numpy.ndarray
        Y position in mm.
    outerRinMm : float
        Outer radius in mm.
    resFile : str, optional
        File path of the grid surface residue map. (the default is None.)
    writeToResMapFilePath : str, optional
        File path to save the residue map. If None, the figure will be showed.
        (the default is None.)
    dpi : int, optional
        The resolution in dots per inch. (the default is None.)
    """

    # Plot the figure
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))

    # The input data to gridSamp.m is in mm (zemax default)
    sc = ax[1].scatter(xfInMm, yfInMm, s=25, c=zfInMm*1e6, marker=".",
                       edgecolor="none")
    ax[1].axis("equal")
    ax[1].set_title("Surface map on FEA grid (nm)")
    ax[1].set_xlim([-outerRinMm, outerRinMm])
    ax[1].set_ylim([-outerRinMm, outerRinMm])
    ax[1].set_xlabel("x (mm)")

    if (resFile is not None):

        # Get the data
        data = np.loadtxt(resFile)
        NUM_X_PIXELS, NUM_Y_PIXELS, delxInMm, delyInMm = data[0, :]
        NUM_X_PIXELS = int(NUM_X_PIXELS)
        NUM_Y_PIXELS = int(NUM_Y_PIXELS)

        # Get the zp data
        zpTemp = data[1:, 0]
        zp = np.zeros((NUM_X_PIXELS, NUM_Y_PIXELS))
        for jj in range(1, NUM_X_PIXELS + 1):
            for ii in range(1, NUM_Y_PIXELS + 1):
                zp[NUM_X_PIXELS+1-jj-1, ii-1] = zpTemp[(jj-1)*NUM_X_PIXELS +
                                                       (ii-1)]

        # Minimum x and y
        minx = -0.5*(NUM_X_PIXELS-1)*delxInMm
        miny = -0.5*(NUM_Y_PIXELS-1)*delyInMm

        xx = np.linspace(minx, -minx, NUM_X_PIXELS)
        yy = np.linspace(miny, -miny, NUM_Y_PIXELS)
        xp, yp = np.meshgrid(xx, yy)

        xp = xp.reshape((NUM_X_PIXELS*NUM_Y_PIXELS, 1))
        yp = yp.reshape((NUM_X_PIXELS*NUM_Y_PIXELS, 1))
        zp = zp.reshape((NUM_X_PIXELS*NUM_Y_PIXELS, 1))

        sc = ax[0].scatter(xp, yp, s=25, c=zp*1e6, marker=".",
                           edgecolor="none")

    ax[0].axis("equal")
    ax[0].set_title("grid input to ZEMAX (nm)")
    ax[0].set_xlim([-outerRinMm, outerRinMm])
    ax[0].set_ylim([-outerRinMm, outerRinMm])
    ax[0].set_xlabel("x (mm)")
    ax[0].set_ylabel("y (mm)")

    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.1, 0.03, 0.8])
    fig.colorbar(sc, cax=cbar_ax)

    _saveFig(plt, saveToFilePath=writeToResMapFilePath, dpi=dpi)


def _saveFig(plt, saveToFilePath=None, dpi=None):
    """Save the figure.

    Parameters
    ----------
    plt : module
        Module of matplotlib.pyplot.
    saveToFilePath : str, optional
        File path to save the figure. If None, the figure will be showed. (the
        default is None.)
    dpi : int, optional
        The resolution in dots per inch. (the default is None.)
    """

    if (saveToFilePath is not None):
        plt.savefig(saveToFilePath, dpi=dpi)
        plt.close()
    else:
        plt.show()


def showFieldMap(fieldX=None, fieldY=None, saveToFilePath=None, dpi=None):
    """Show the field map in degree.

    Parameters
    ----------
    fieldX : numpy.ndarray, optional
        Field x in degree. (the default is None.)
    fieldY : numpy.ndarray, optional
        Field y in degree. (the default is None.)
    saveToFilePath : str, optional
        File path to save the figure. (the default is None.)
    dpi : int, optional
        The resolution in dots per inch. (the default is None.)
    """

    # Declare the figure
    plt.figure()

    # Get the focal plane information
    sourProc = SourceProcessor()

    # Plot the CCD boundary
    for sensorName in sourProc.sensorDimList.keys():

        # Get the CCD corner field points in degree
        pointXinDeg, pointYinDeg = _getCCDBoundInDeg(sourProc, sensorName)

        # Plot the boundary
        pointXinDeg.append(pointXinDeg[0])
        pointYinDeg.append(pointYinDeg[0])
        plt.plot(pointXinDeg, pointYinDeg, "b")

    # Plot the field X, Y position
    if (fieldX is not None) and (fieldY is not None):
        plt.plot(fieldX, fieldY, "ro")

    # Plot the 3.5 degree circle
    circle = plt.Circle((0, 0), 1.75, color="g", fill=False)
    plt.gcf().gca().add_artist(circle)

    # Do the labeling
    plt.xlabel("Field X (deg)")
    plt.ylabel("Field Y (deg)")

    # Label four corner rafts for the identification
    plt.text(-1.5, -1.5, "R00")
    plt.text(1.5, -1.5, "R40")
    plt.text(1.5, 1.5, "R44")
    plt.text(-1.5, 1.5, "R04")

    # Set the axis limit
    plt.xlim(-2, 2)
    plt.ylim(-2, 2)

    # Set the same scale
    plt.axis("equal")

    _saveFig(plt, saveToFilePath=saveToFilePath, dpi=dpi)


def _getCCDBoundInDeg(sourProc, sensorName):
    """Get the CCD four corners in degree in counter clockwise direction.

    Parameters
    ----------
    sourProc : SourceProcessor
        SourceProcessor object.
    sensorName : str
        Sensor name

    Returns
    -------
    list
        Corner points x in degree.
    list
        Corner points y in degree.
    """

    # Set the sensor on sourProc
    sourProc.config(sensorName=sensorName)

    # Get the dimension of CCD
    pixDimX, pixDimY = sourProc.sensorDimList[sensorName]

    # Define four corner points in the counter-clockwise direction
    pixelXlist = [0, pixDimX, pixDimX, 0]
    pixelYlist = [0, 0, pixDimY, pixDimY]

    # Transform from pixel to field degree
    fieldXinDegList = []
    fieldYinDeglist = []

    for ii in range(len(pixelXlist)):

        fieldX, fieldY = sourProc.camXYtoFieldXY(pixelXlist[ii],
                                                 pixelYlist[ii])
        fieldXinDegList.append(fieldX)
        fieldYinDeglist.append(fieldY)

    return fieldXinDegList, fieldYinDeglist


def plotFwhmOfIters(pssnFiles, saveToFilePath=None, dpi=None):
    """Plot the FWHM of iteration.

    FWHM: Full width at half maximum.
    PSSN: Normalized point source sensitivity.

    Parameters
    ----------
    pssnFiles : list
        List of PSSN files.
    saveToFilePath : str, optional
        File path to save the figure. If None, the figure will be showed. (the
        default is None.)
    dpi : int, optional
        The resolution in dots per inch. (the default is None.)
    """

    # Collect the FWHM data. The row is the FWHM for each field. The final row
    # is the GQ FWHM. The column is the iterations.
    numOfIter = len(pssnFiles)

    numOfFwhmData = 0
    fwhmDataAll = np.array([])
    for pssnFile in pssnFiles:

        fwhmData = np.loadtxt(pssnFile)[1, :]
        if (numOfFwhmData == 0):
            numOfFwhmData = len(fwhmData)

        fwhmDataAll = np.append(fwhmDataAll, fwhmData)

    reshapedFwhmData = fwhmDataAll.reshape((numOfIter, numOfFwhmData)).T

    # Plot the figure
    plt.figure()
    plt.plot(reshapedFwhmData[:-1, :].T, "bx-")
    plt.plot(reshapedFwhmData[-1, :], "ro-", label="GQ FWHM_eff")
    plt.xlabel("Iteration")
    plt.ylabel("Arcsec")
    plt.legend()

    _saveFig(plt, saveToFilePath=saveToFilePath, dpi=dpi)


if __name__ == "__main__":
    pass

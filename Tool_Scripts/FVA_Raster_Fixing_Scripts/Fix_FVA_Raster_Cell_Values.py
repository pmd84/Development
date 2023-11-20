
import arcpy
import sys
from sys import argv
import os
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd

def check_out_spatial_analyst():
    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
            arcpy.AddMessage("Checked out Spatial Extension")
        else:
            raise LicenseError
    except LicenseError:
        arcpy.AddMessage("Spatial Analyst license is unavailable")
    except:
        arcpy.AddMessage("Exiting")
        sys.exit()

def find_diff_files(QC_Output_Folder):
    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Finding Cell Value Difference Points in QC Folder #####")

    cellDiff1_0 = os.path.join(QC_Output_Folder, "cellDiff1_0_pts.shp")
    cellDiff2_1 = os.path.join(QC_Output_Folder, "cellDiff2_1_pts.shp")
    cellDiff3_2 = os.path.join(QC_Output_Folder, "cellDiff3_2_pts.shp")

    for cellDiffFiles in [cellDiff1_0, cellDiff2_1, cellDiff3_2]:
        if not arcpy.Exists(cellDiffFiles):
            arcpy.AddWarning("{} does not exist in QC Output folder location. Ensure QC tool has been run".format(cellDiffFiles))
            sys.exit()
        else:
            arcpy.AddMessage("Found {0}".format(cellDiffFiles))

    return cellDiff1_0, cellDiff2_1, cellDiff3_2


if __name__ == "__main__":
    
    #Make sure spatial analyst is checked out
    check_out_spatial_analyst()

    #Get tool input parameters
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    QC_Output_Folder = arcpy.GetParameterAsText(1)

    #Get file paths for extent difference polygons
    diffFva0_1, diffFva1_2, diffFva2_3 = find_celldiff_files(QC_Output_Folder)
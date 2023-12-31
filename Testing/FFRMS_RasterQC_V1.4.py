#-------------------------------------------------------------------------------
# Name:        FFRMS_Raster_QC_Riverine.py
# Purpose:     This tool is developed to automate raster QC checklist on FFRMS FVA rasters. 
#              All STARR II PTS Zone3 partners are authorized to use this tool for raster QC checks. 
# Author:      Rachel Fan, GISP
#              rachel.fan@stantec.com
# Version:     1.4
# Updated:     11/29/2023
# Created:     09/23/2023
# Copyright:   (c) rfan2023

#-------------------------------------------------------------------------------

import arcpy
import arcpy.sa as sa
import os
from datetime import datetime, timedelta
import sys
import traceback
import shutil
import re
import csv
import glob
   
import numpy
import math
import time
import jinja2
import pandas as pd
from arcpy.sa import *


def check_extention():
    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
            print ("Checked out \"Spatial\" Extension")
        else:
            #raise LicenseError
            print ("Spatial Analyst license is unavailable")
    #except LicenseError:
        #print ("Spatial Analyst license is unavailable")
    except:
        print ("Exiting")

def printError():  # Function to print out error messages
    """Prints out error messages using ArcPy."""
    tb = sys.exc_info()[1]
    tbinfo = traceback.format_tb(tb)[0]
    pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
    msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(1) + "\n"
    arcpy.AddError(pymsg)
    arcpy.AddError(msgs)

def retrieveConfig(sheet):  # Function to retrieve configuration data from config excel file
    """Retrieves configuration data from NPDES Key excel file."""
    # Use pandas to read excel file
    df = pd.read_excel(configFile, sheet)
    df = df[['Desc', 'Value']]
    configDict = df.set_index('Desc').to_dict(orient='index')
    return configDict
    
def find_variable_part(file, suffix):
    prefix_len = len(file) - len(suffix)
    return file[:prefix_len], file[prefix_len:-len('.tif')]

def log_message(message):
        arcpy.AddMessage(message)
        log.write(message + "\n")
        
def compareExtent(raster0, raster1, raster2, raster3,tempFolder, shapefilesFolder): #Function to compare the extent of 00FVA, 01FVA, 02 FVA and 03FVA 
    """compare raster extent between each adjecent freeboard value set: 00FVA vs 01FVA, 02FVA vs 03FVA, 02FVA vs 03FVA"""
    arcpy.env.workspace = tempFolder
    arcpy.env.compression = "LZW"
     
    #convert raster to polygon
    polyFva0 = os.path.join(tempFolder, "FVA0.shp")
    raster0_int = arcpy.sa.Int(arcpy.Raster(raster0))
    arcpy.conversion.RasterToPolygon(raster0_int, polyFva0, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART") #direct output shp to temp folder
          
    polyFva1 = os.path.join(tempFolder, "FVA1.shp")
    raster1_int = arcpy.sa.Int(arcpy.Raster(raster1))
    arcpy.conversion.RasterToPolygon(raster1_int, polyFva1, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
    
    polyFva2 = os.path.join(tempFolder, "FVA2.shp")
    raster2_int = arcpy.sa.Int(arcpy.Raster(raster2))
    arcpy.conversion.RasterToPolygon(raster2_int, polyFva2, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
    
    polyFva3 = os.path.join(tempFolder, "FVA3.shp")
    raster3_int = arcpy.sa.Int(arcpy.Raster(raster3))
    arcpy.conversion.RasterToPolygon(raster3_int, polyFva3, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")    
    
    #create extent difference shapefile by erasing the lower values from higher values
    clipFva1_0 = os.path.join(tempFolder, "clipFva1_0.shp")
    arcpy.analysis.Erase(polyFva1, polyFva0, clipFva1_0)
    diffFva1_0 = os.path.join(tempFolder, "diffFva1_0.shp")
    arcpy.management.MultipartToSinglepart(clipFva1_0, diffFva1_0)
    arcpy.management.AddField(diffFva1_0, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva1_0, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    #detect if lower freeboard values have larger extent by reversely erasing. Warning message is added if it occurs.
    clipFva0_1 = os.path.join(tempFolder, "clipFva0_1.shp")
    arcpy.analysis.Erase(polyFva0, polyFva1, clipFva0_1)
    diffFva0_1 = os.path.join(shapefilesFolder, "diffFva0_1.shp")
    arcpy.management.MultipartToSinglepart(clipFva0_1, diffFva0_1)
    arcpy.management.AddField(diffFva0_1, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva0_1, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    # Get the count of features in the shapefile
    feature_count = int(arcpy.GetCount_management(diffFva0_1).getOutput(0))

    # Check if there are any records
    if feature_count > 0:
        diff0_1_sts = "Fail! See " + diffFva0_1 + " in Output folder for details. "
        #Define a parameter to pass this "Pass or Fail" value out of the function, and use it in Function createReport
        print("Warning! FFRMS FVA 1 raster extent is less than WSE raster extent. See diffFva0_1.shp in Output folder for details. ")
    else:
        diff0_1_sts = "Pass"
        print("Extent compare FVA01 vs FVA00 Pass!")

    clipFva2_1 = os.path.join(tempFolder, "clipFva2_1.shp")
    arcpy.analysis.Erase(polyFva2, polyFva1, clipFva2_1)
    diffFva2_1 = os.path.join(tempFolder, "diffFva2_1.shp")
    arcpy.management.MultipartToSinglepart(clipFva2_1, diffFva2_1)
    arcpy.management.AddField(diffFva2_1, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva2_1, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    #detect if lower freeboard values have larger extent by reversely erasing. Warning message is added if it occurs.
    clipFva1_2 = os.path.join(tempFolder, "clipFva1_2.shp")
    arcpy.analysis.Erase(polyFva1, polyFva2, clipFva1_2)
    diffFva1_2 = os.path.join(shapefilesFolder, "diffFva1_2.shp")
    arcpy.management.MultipartToSinglepart(clipFva1_2, diffFva1_2)
    arcpy.management.AddField(diffFva1_2, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva1_2, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    # Get the count of features in the shapefile
    feature_count1 = int(arcpy.GetCount_management(diffFva1_2).getOutput(0))

    # Check if there are any records
    if feature_count1 > 0:
        #Define a parameter to pass this "Pass or Fail" value out of the function, and use it in Function createReport
        diff1_2_sts = "Fail! See " + diffFva1_2 + " in Output folder for details. "
        print("Warning! FFRMS FVA 2 raster extent is less than FFRMS FVA 1 raster extent. See diffFva1_2.shp in Output folder for details. ")#Please refine the wording as needed. 
    else:
        diff1_2_sts = "Pass"
        print("Extent compare FVA02 vs FVA01 Pass!")

    clipFva3_2 = os.path.join(tempFolder, "clipFva3_2.shp")
    arcpy.analysis.Erase(polyFva3, polyFva2, clipFva3_2)
    diffFva3_2 = os.path.join(tempFolder, "diffFva3_2.shp")
    arcpy.management.MultipartToSinglepart(clipFva3_2, diffFva3_2)
    arcpy.management.AddField(diffFva3_2, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva3_2, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    #detect if lower freeboard values have larger extent by reversely erasing. Warning message is added if it occurs.
    clipFva2_3 = os.path.join(tempFolder, "clipFva2_3.shp")
    arcpy.analysis.Erase(polyFva2, polyFva3, clipFva2_3)
    diffFva2_3 = os.path.join(shapefilesFolder, "diffFva2_3.shp")
    arcpy.management.MultipartToSinglepart(clipFva2_3, diffFva2_3)
    arcpy.management.AddField(diffFva2_3, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva2_3, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    # Get the count of features in the shapefile
    feature_count2 = int(arcpy.GetCount_management(diffFva2_3).getOutput(0))

    # Check if there are any records
    if feature_count2 > 0:
        #Define a parameter to pass this "Pass or Fail" value out of the function, and use it in Function createReport
        diff2_3_sts = "Fail! See " + diffFva2_3 + " in Output folder for details. "
        print("Warning! FFRMS FVA 3 raster extent is less than FFRMS FVA 2 raster extent. See diffFva2_3.shp in Output folder for details. ")#Please refine the wording as needed. 
    else:
        diff2_3_sts = "Pass"
        print("Extent compare FVA03 vs FVA02 Pass!")   
        
    return diff0_1_sts, diff1_2_sts, diff2_3_sts

def compareExtent02(raster0, raster02, tempFolder, shapefilesFolder):
    arcpy.env.workspace = tempFolder
    arcpy.env.compression = "LZW"
    
    #convert raster to polygon
    polyFva0 = os.path.join(tempFolder, "FVA0.shp")
    raster0_int = arcpy.sa.Int(arcpy.Raster(raster0))
    arcpy.conversion.RasterToPolygon(raster0_int, polyFva0, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART") #direct output shp to temp folder
    
    polyFva02 = os.path.join(tempFolder, "FVA02.shp")
    raster02_int = arcpy.sa.Int(arcpy.Raster(raster02))
    arcpy.conversion.RasterToPolygon(raster02_int, polyFva02, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART") #direct output shp to temp folder
    #print("Raster 0.2% to Polygon done at " + polyFva02)
    
    clipFva0_02 = os.path.join(tempFolder, "clipFva0_02.shp")
    arcpy.analysis.Erase(polyFva0, polyFva02, clipFva0_02)
    diffFva0_02 = os.path.join(shapefilesFolder, "diffFva0_02.shp")
    arcpy.management.MultipartToSinglepart(clipFva0_02, diffFva0_02)
    arcpy.management.AddField(diffFva0_02, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva0_02, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    clipFva02_0 = os.path.join(tempFolder, "clipFva02_0.shp")
    arcpy.analysis.Erase(polyFva02, polyFva0, clipFva02_0)
    diffFva02_0 = os.path.join(tempFolder, "diffFva02_0.shp")
    arcpy.management.MultipartToSinglepart(clipFva02_0, diffFva02_0)
    arcpy.management.AddField(diffFva02_0, "Area", "DOUBLE")
    #calculate area of each record and add it back to the Area field
    with arcpy.da.UpdateCursor(diffFva02_0, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area = row[0].area
            row[1] = area
            cursor.updateRow(row)

    # Get the count of features in the shapefile
    feature_count_02 = int(arcpy.GetCount_management(diffFva0_02).getOutput(0))

    # Check if there are any records
    if feature_count_02 > 0:
        diff02_0_sts = "Fail! See " + diffFva0_02 + " in Output folder for details. "
        #Define a parameter to pass this "Pass or Fail" value out of the function, and use it in Function createReport
        print("Warning! FFRMS FVA00 raster extent is less than 0.2 PCT raster extent. See diffFva0_02.shp in Output folder for details. ")
    else:
        diff02_0_sts = "Pass"
        print("Extent compare FVA00 vs 0.2 PCT Pass!")
        
    return diff02_0_sts

def compareCellvalue(raster0, raster1, raster2, raster3, tempFolder, shapefilesFolder):
    """run cell size compare on each raster"""
    try:
        
        minus1 = RasterCalculator([raster0, raster1], ["x","y"], "y-x", "UnionOf","FirstOf")
        #minus1.save(os.path.join(tempFolder, "minus1"))

        minus2 = RasterCalculator([raster1, raster2], ["x","y"], "y-x", "UnionOf","FirstOf")
        #minus2.save(os.path.join(tempFolder, "minus2"))
        
        minus3 = RasterCalculator([raster2, raster3], ["x","y"], "y-x", "UnionOf","FirstOf")
        #minus3.save(os.path.join(tempFolder, "minus3.tif"))
        print("Minus raster calculation are complete.")

        reclas1 = arcpy.sa.Reclassify(minus1, "Value", RemapRange([[-1,0.95,1],[0.95,1.05,0],[1.05,10,1]]))
        reclas1.save(os.path.join(tempFolder, "reclassify1"))
        #arcpy.management.CopyRaster(reclas1, os.path.join(tempFolder,"reclass1.tif"))
        print("1/3 reclassify tasks is finished.")
        
        reclas2 = arcpy.sa.Reclassify(minus2, "Value", RemapRange([[-1,0.95,1],[0.95,1.05,0],[1.05,10,1]]))
        reclas2.save(os.path.join(tempFolder, "reclassify2"))
        #arcpy.management.CopyRaster(reclas2, os.path.join(tempFolder,"reclass2.tif"))
        print("2/3 reclassify tasks is finished.")
        
        reclas3 = arcpy.sa.Reclassify(minus3, "Value", RemapRange([[-1,0.95,1],[0.95,1.05,0],[1.05,10,1]]))
        reclas3.save(os.path.join(tempFolder, "reclassify3"))
        #arcpy.management.CopyRaster(reclas3, os.path.join(tempFolder,"reclass3.tif"))
        print("3/3 reclassify tasks is finished.")
        
        #print("Reclassify complete.") 
    except:
        print("Could not compare the cell values.")
    return reclas1, reclas2, reclas3

    
def compareCellvalue02(raster0, raster02, tempFolder, shapefilesFolder):
    """run cell size compare on each raster"""
    try:
        
        minus1 = RasterCalculator([raster02, raster0], ["x","y"], "y-x", "UnionOf","FirstOf")
        #minus1.save(os.path.join(tempFolder, "minus02"))

        reclas02 = arcpy.sa.Reclassify(minus1, "Value", RemapRange([[-1,0.95,1],[0.95,1.05,0],[1.05,10,1]]))
        reclas02.save(os.path.join(tempFolder, "reclassify02"))
        print("4/4 reclassify tasks is finished.")
        
        #print("reclassify02 is generated.") 
    except:
        print("Could not compare the cell values.")
    return reclas02  

def convertToshp(reclas1, reclas2, reclas3, tempFolder, shapefilesFolder):
    '''convert raster minus result to shapefile using reclassify'''
    try:
        cellDiff1_0 = os.path.join(tempFolder, "cellDiff1_0.shp")
        reclas1_poly = os.path.join(tempFolder, "reclas1_poly.shp")
        arcpy.conversion.RasterToPolygon(reclas1, cellDiff1_0, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
        #arcpy.management.Dissolve(reclas1_poly, cellDiff1_0, "gridcode", None, "MULTI_PART","DISSOLVE_LINES","")
        #print("cellDiff1_0 created! ")
        
        cellDiff2_1 = os.path.join(tempFolder, "cellDiff2_1.shp")
        reclas2_poly = os.path.join(tempFolder, "reclas2_poly.shp")
        arcpy.conversion.RasterToPolygon(reclas2, reclas2_poly, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
        arcpy.management.Dissolve(reclas2_poly, cellDiff2_1, "gridcode", None, "MULTI_PART","DISSOLVE_LINES","")
        #print("cellDiff2_1 created! ")
        
        cellDiff3_2 = os.path.join(tempFolder, "cellDiff3_2.shp")
        reclas3_poly = os.path.join(tempFolder, "reclas3_poly.shp")
        arcpy.conversion.RasterToPolygon(reclas3, reclas3_poly, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
        arcpy.management.Dissolve(reclas3_poly, cellDiff3_2, "gridcode", None, "MULTI_PART","DISSOLVE_LINES","")
        #print("cellDiff3_2 created! ")
        
    except:
        print("Could not convert to shapefiles!")
        printError()
    return cellDiff1_0, cellDiff2_1, cellDiff3_2
    
def convertToshp02(reclas02, tempFolder, shapefilesFolder):
    '''convert raster minus result to shapefile using reclassify'''
    try:
        cellDiff0_02 = os.path.join(tempFolder, "cellDiff0_02.shp")
        reclas1_poly = os.path.join(tempFolder, "reclas02_poly.shp")
        arcpy.conversion.RasterToPolygon(reclas02, cellDiff0_02, "NO_SIMPLIFY","","MULTIPLE_OUTER_PART")
        #print("cellDiff0_02 created! ")
        
    except:
        print("Could not convert to shapefiles!")
        printError()
    return cellDiff0_02

def extractCellValue(cellDiff1_0, in_raster0, in_raster1, tempFolder, shapefilesFolder):
    '''convert raster minus result to shapefile using reclassify'''
    try:
        templayer = os.path.join(tempFolder, "templayer.lyr")
        arcpy.management.MakeFeatureLayer(cellDiff1_0, templayer)        # Run SelectLayerByAttribute to determine which features to delete
        arcpy.management.SelectLayerByAttribute(templayer, "NEW_SELECTION", '"gridcode" = 1')
        cellDiff1_0_cp = os.path.join(tempFolder, "cellDiff1_0_cp.shp")
        arcpy.CopyFeatures_management(templayer, cellDiff1_0_cp)
        cellDiff1_0_cp_multi = os.path.join(tempFolder, "cellDiff1_0_cp_multi.shp")
        arcpy.management.MultipartToSinglepart(cellDiff1_0_cp, cellDiff1_0_cp_multi)
        
        points_records_no = int(arcpy.GetCount_management(cellDiff1_0_cp_multi).getOutput(0))
        if points_records_no == 0:
            cellDiff1_0_pts = os.path.join(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp')
            arcpy.CreateFeatureclass_management(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp', "POINT")
            
        else:       
            cellDiff1_0_pts = os.path.join(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp')
            arcpy.management.FeatureToPoint(cellDiff1_0_cp_multi, cellDiff1_0_pts, "INSIDE")
            FieldName_lower = re.search(r"\d+FVA", str(in_raster0)).group()
            FieldName_higher = re.search(r"\d+FVA", str(in_raster1)).group()
            #print(str(FieldName_lower),str(FieldName_higher))

            arcpy.sa.ExtractMultiValuesToPoints(cellDiff1_0_pts, [[in_raster0,FieldName_lower], [in_raster1,FieldName_higher]], "NONE")
            #print('ExtractMultiValuesToPoints is done')
            arcpy.management.AddField(cellDiff1_0_pts, "ValueDiff", "FLOAT")
            #print("Add field is done")
            field1 = str(FieldName_lower)
            field2 = str(FieldName_higher)
            arcpy.management.CalculateField(cellDiff1_0_pts, "ValueDiff", f"!{field2}! - !{field1}!") 
            #print('calculate field done')
    except:
        print("Could not convert to points!")
        printError()
    return cellDiff1_0_pts

def extractCellValue02(cellDiff1_0, in_raster0, in_raster1, tempFolder, shapefilesFolder):
    '''convert raster minus result to shapefile using reclassify'''
    try:
        templayer = os.path.join(tempFolder, "templayer.lyr")
        arcpy.management.MakeFeatureLayer(cellDiff1_0, templayer)        # Run SelectLayerByAttribute to determine which features to delete
        arcpy.management.SelectLayerByAttribute(templayer, "NEW_SELECTION", '"gridcode" = 1')
        cellDiff1_0_cp = os.path.join(tempFolder, "cellDiff1_0_cp.shp")
        arcpy.CopyFeatures_management(templayer, cellDiff1_0_cp)
        cellDiff1_0_cp_multi = os.path.join(tempFolder, "cellDiff1_0_cp_multi.shp")
        arcpy.management.MultipartToSinglepart(cellDiff1_0_cp, cellDiff1_0_cp_multi)

        points_records_no = int(arcpy.GetCount_management(cellDiff1_0_cp_multi).getOutput(0))
        if points_records_no == 0:
            cellDiff1_0_pts = os.path.join(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp')
            arcpy.CreateFeatureclass_management(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp', "POINT")
            
        else:       
            cellDiff1_0_pts = os.path.join(shapefilesFolder, f'cellDiff{str (cellDiff1_0)[-7:-4]}_pts.shp')
            arcpy.management.FeatureToPoint(cellDiff1_0_cp_multi, cellDiff1_0_pts, "INSIDE")
            
            FieldName_lower = "0_" + re.search(r"\d+PCT", str(in_raster0)).group()
            FieldName_higher = re.search(r"\d+FVA", str(in_raster1)).group()
            #print(str(FieldName_lower),str(FieldName_higher))

            arcpy.sa.ExtractMultiValuesToPoints(cellDiff1_0_pts, [[in_raster0,FieldName_lower], [in_raster1,FieldName_higher]], "NONE")
            arcpy.management.AddField(cellDiff1_0_pts, "ValueDiff", "FLOAT")
            field1 = str(FieldName_lower)
            field2 = str(FieldName_higher)
            arcpy.management.CalculateField(cellDiff1_0_pts, "ValueDiff", f"!{field2}! - !{field1}!") 
            #print('calculate field done')
        
    except:
        print("Could not convert to points!")
        printError()
    return cellDiff1_0_pts
        
def reportCellComp(cellDiffPts):
    '''convert raster minus result to shapefile using reclassify'''
    try:
        # Get the count of features in the shapefile
        feature_count = int(arcpy.GetCount_management(cellDiffPts).getOutput(0))

        # Check if there are any records
        if feature_count > 0:
            if cellDiffPts[-10:-9] == "_":
                higherfva = cellDiffPts[-11:-10]
                lowerfva = cellDiffPts[-9:-8]
                celldiff1_0_sts = "Warning! See cellDiff" + higherfva + "_" + lowerfva + " _pts.shp in Output folder for details. "
                #Define a parameter to pass this "Pass or Fail" value out of the function, and use it in Function createReport
                print("Warning! FVA0" + higherfva + " have cells lower than those in FVA0" + lowerfva + ". See cellDiff" + higherfva + "_" + lowerfva + "_pts.shp in Output folder for details.")
            else:
                celldiff1_0_sts = "Warning! See cellDiff_02_pts.shp in Output folder for details."
                print("Warning! 02PCT have cells lower than those in FVA00")
        else:
            celldiff1_0_sts = "Pass"

            if cellDiffPts[-10:-9] == "_":
                higherfva = cellDiffPts[-11:-10]
                lowerfva = cellDiffPts[-9:-8]
                print("Pass! All cells in FVA0" + higherfva + " are higher than those in FVA0" + lowerfva)
            else:
                print("Pass! All cells in 02PCT are higher than those in FVA00")
                
    except:
        print("Could not convert to points!")
    return celldiff1_0_sts

def getRasterProperties(in_Raster):
    
    r = sa.Raster(in_Raster)
    # check spatial references are defined
    if r.spatialReference:
        sr_name = r.spatialReference.name
    else:
        sr_name = 'Not Defined'
	
    if r.spatialReference.VCS:
        vcs_name = r.spatialReference.VCS.name
        vcs_unit = r.spatialReference.VCS.linearUnitName 
    else:
        vcs_name = 'Not Defined'
        vcs_unit = 'Not Defined'
    

    raster_properties = [
        r.name, #QC R3
        r.pixelType,#QC R4
        round(r.meanCellHeight,5),  #QC R6
        sr_name,    #QC R7
        vcs_name, #QC R8
        vcs_unit #QC R8 unit
    ]
    return raster_properties

def generate_csv(in_raster0, in_raster1, in_raster2,in_raster3, in_raster02, output_csv):
    # Output CSV file

    # Write the data to the CSV file
    try:
        
        csvheader = ['Name',
            'Pixel_Type',
            'Cell_Size',
            'Spatial_Reference',
            'Vertical_Datum',
            'Vertical_Unit',
            '',
            '',
            '3 FVA rasters extents compare',
            '3 FVA rasters cells value compare',
            'pbl(still developing)'       
            ]

        qclist = ['R3',
            'R4',
            'R6',
            'R7',
            'R8',
            'R8',
            '',
            'R11',
            'R14',
            'R17'
            ]          
    except:
        print("Could not create CSV")
    
    with open(output_csv, 'w', newline='') as csv_file:
        # Validate if every QC item has been checked.
        # Write header
        try:
            csv_file.write('AttributeName,QC checklist item,FVA0 Raster properties, FVA1 Raster properties, FVA2 Raster properties, FVA3 Raster properties, 0.2PCT Raster properties\n')

            # Write data rows for column 1 and column 2
            csv_writer = csv.writer(csv_file)
            #
            for item1, item2, item3, item4, item5, item6, item7 in zip(csvheader,qclist, in_raster0,in_raster1,in_raster2,in_raster3, in_raster02):
                #row_str = f'{column1_data[i][0], {column1_data[1][i]}}\n'
                csv_writer.writerow([item1, item2,item3, item4, item5,item6, item7])
            print("Data written to CSV:", output_csv)
        except:
            print("Could not write to CSV")

def generate_csv_wo02(in_raster0, in_raster1, in_raster2,in_raster3, output_csv):
    # Output CSV file

    # Write the data to the CSV file
    try:
        
        csvheader = ['Name',
            'Pixel_Type',
            'Cell_Size',
            'Spatial_Reference',
            'Vertical_Datum',
            'Vertical_Unit',
            '',
            '',
            '3 FVA rasters extents compare',
            '3 FVA rasters cells value compare',
            'pbl(still developing)'       
            ]

        qclist = ['R3',
            'R4',
            'R6',
            'R7',
            'R8',
            'R8'
            '',
            '',
            'R11',
            'R14',
            'R17'
            ]          
    except:
        print("Could not create CSV")
   
    with open(output_csv, 'w', newline='') as csv_file:
        # Write header
        try:
            csv_file.write('AttributeName,QC checklist item,FVA0 Raster properties, FVA1 Raster properties, FVA2 Raster properties, FVA3 Raster properties\n')

            # Write data rows for column 1 and column 2
            csv_writer = csv.writer(csv_file)
            for item1, item2, item3, item4, item5, item6 in zip(csvheader,qclist, in_raster0,in_raster1,in_raster2,in_raster3):
                #row_str = f'{column1_data[i][0], {column1_data[1][i]}}\n'
                csv_writer.writerow([item1, item2,item3, item4, item5,item6])
            print("Data written to CSV:", output_csv)
        except:
            print("Could not write to CSV")
            

def get_unique_filename(folder, filename):
    base, extension = os.path.splitext(filename)
    index = 0
    while True:
        new_filename = f"{base}_{index}{extension}" if index >0 else filename
        file_path = os.path.join(folder, new_filename)
        if not os.path.exists(file_path):
            return file_path
        index +=1
            
#-------------------------------------------------------------------------------
# Main functions start from here
#-------------------------------------------------------------------------------

#Record start time using current time
start_time = time.time()
current_time = time.strftime("%m-%d %X",time.localtime())
print("Raster QC tool has started")

# Check Spatial Analyst extention
check_extention()

#Define input and output parameters
arcpy.env.overwriteOutput = True
#arcpy.env.workspace = tempFolder
arcpy.env.compression = "LZW"
exception_occured = False

scriptPath = os.path.dirname(__file__)
configFile = os.path.join(scriptPath, 'FFRMS_RasterQC_Configuration.xlsx')

try:
    config = retrieveConfig("RasterCompare")

    # Assuming the folder path is provided in the config file
    rasters_folder = config['Rasters folder path']['Value']  # Example: "D:/CA_06049_Rasters/"
    #print(rasters_folder)

    # Get a list of all files in the folder
    all_files = os.listdir(rasters_folder)
    #print(all_files)

    raster_suffix = "CA_06049_10N_00FVA_RIV_03m.tif"
    raster0 = None
    raster1 = None
    raster2 = None
    raster3 = None
    raster02 = None



    # Find the files that match the modified naming convention for raster0 and raster1
    for file in all_files:
        if file.endswith('.tif') and len(file) == len(raster_suffix):
            prefix, middle, suffix = file[:8], file[13:18], file[26:]
              
            if raster0 is None and middle == '00FVA':
                raster0 = os.path.join(rasters_folder, file)
            elif raster1 is None and middle == '01FVA':
                raster1 = os.path.join(rasters_folder, file)
            elif raster2 is None and middle == '02FVA':
                raster2 = os.path.join(rasters_folder, file)
            elif raster3 is None and middle == '03FVA':
                raster3 = os.path.join(rasters_folder, file)

    #print(raster0)
    print('raster0 is read at ' + raster0)
    print('raster1 is read at ' + raster1)
    print('raster2 is read at ' + raster2)
    print('raster3 is read at ' + raster3)

    for file in all_files:
        if file.endswith('.tif') and len(file) == len(raster_suffix)+1:
            raster02 = os.path.join(rasters_folder, file)

    if pd.notna(raster02):
        print("All 5 rasters have been read by the tool!")
    else:
        print("No valid 0.2 % raster was found. Tool will only QC 4 existing rasters.")

    # Extract prefix and study type from imported raster0
    prefixCSV = raster0[-30:-22]
    studytypeCSV = raster0[-11:-8]

    print('Prefix is read as '+prefixCSV)
    print('Study Type is read as '+studytypeCSV)

    # Name the tool created folders, csv and log using prefix and study type   
    tempFolderName = 'Temp_'+ prefixCSV + '_' + studytypeCSV
    tempFolder = os.path.join(scriptPath, tempFolderName)
    if not os.path.exists(tempFolder):
        os.makedirs(tempFolder)

    outputFolderName = 'Output_'+ prefixCSV + '_' + studytypeCSV
    outputFolder = os.path.join(scriptPath, outputFolderName)
    if not os.path.exists(outputFolder):
        os.makedirs(outputFolder)

    shpFolderName = 'Shapefiles_'+ prefixCSV + '_' + studytypeCSV
    shapefilesFolder = os.path.join(outputFolder, shpFolderName)
    if not os.path.exists(shapefilesFolder):
        os.makedirs(shapefilesFolder)

    initCSVname = f"{prefixCSV}_{studytypeCSV}_Raster_QC_Results.csv"
    OutputCSV = get_unique_filename(outputFolder, initCSVname)

    logName = f"{prefixCSV}_{studytypeCSV}_Tool_log.txt"
    logFile = os.path.join(outputFolder,logName)

    print("Temp folder is at " + tempFolder)
    print("Output folder is at " + outputFolder)
    print("Shapefiles folder is at " + shpFolderName)
    print("Output CSV is at " + OutputCSV)
    print("Log file is at " + logFile)

    print('')
    print('********************************')
    print('Import config file successfully.')
    print('Folder structure has been set up.')
    print('********************************')
    
except:

    print('')
    print('********************************')
    print('Error in reading configure file...')
    print('********************************')
    
    exception_occured = True

with open(logFile, "w") as log:
    print("Start geoprocessing at ",current_time)
    current_time = time.strftime("%m-%d %X",time.localtime())
    log_message("Start processing at " + current_time + "\n")

    
    if not exception_occured:
        try:
            
            print('')
            print('********************************')
            print('Initializing compare extent')
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Compare extent started at " + current_time)
            
            diff0_1_sts, diff1_2_sts, diff2_3_sts = compareExtent(raster0, raster1, raster2, raster3, tempFolder, shapefilesFolder)
            if pd.notna(raster02):
                diff02_0_sts = compareExtent02(raster0, raster02, tempFolder, shapefilesFolder)
            
            print('Compare raster extent successfully completed.')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Compare extent finished at " + current_time + "\n")

        except:

            print('')
            print('********************************')
            print('Error in compare extent...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Compare extent failed at" + current_time + "\n")
            exception_occured = True
            
    if not exception_occured:
        try:

            print('')
            print('********************************')
            print('Initializing comparing cell values')
            rec_start_time = time.time()
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Compare cell value started at " + current_time)
            
            reclas1, reclas2, reclas3 = compareCellvalue(raster0, raster1, raster2, raster3, tempFolder, shapefilesFolder)
            if pd.notna(raster02):
                #print("Run compare cell value between 0_2PCT and FVA00")
                reclas02 = compareCellvalue02(raster0, raster02, tempFolder, shapefilesFolder)
            
            print('Comparing cell values successfully completed.')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Compare cell value finished at " + current_time + "\n")

            rec_finish_time = time.time()
            time_period = str(timedelta(seconds=(rec_finish_time - rec_start_time)))

        except:

            print('')
            print('********************************')
            print('Error in comparing cell values...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Compare cell value failed at " + current_time + "\n")
            exception_occured = True

    
    if not exception_occured:
        try:

            print('')
            print('********************************')
            print('Initializing exporting cell value difference shapefiles')
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Create cell value diff shapefiles started at " + current_time)

            #run convertToShp to convert reclassified rasters to shapefiles
            cellDiff1_0, cellDiff2_1, cellDiff3_2 = convertToshp(reclas1, reclas2, reclas3, tempFolder, shapefilesFolder)
            if pd.notna(raster02):
                cellDiff0_02 = convertToshp02(reclas02, tempFolder, shapefilesFolder)
            print('Convert highlighted cell values to Shapefile is complete')

            #extract cell values from both lower and higher FVA rasters to result shapefiles
            cellDiff1_0_pts = extractCellValue(cellDiff1_0, raster0, raster1, tempFolder, shapefilesFolder) 
            cellDiff2_1_pts = extractCellValue(cellDiff2_1, raster1, raster2, tempFolder, shapefilesFolder)
            cellDiff3_2_pts = extractCellValue(cellDiff3_2, raster2, raster3, tempFolder, shapefilesFolder)
            if pd.notna(raster02):
                cellDiff0_02_pts = extractCellValue02(cellDiff0_02, raster02, raster0, tempFolder, shapefilesFolder)
            print('Cell value difference points shapefiles are created')
            print('********************************')

            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Create cell value diff shapefiles finished at " + current_time + "\n")

        except:

            print('')
            print('********************************')
            print('Error in exporting cell value difference shapefiles...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Create cell value diff shapefiles failed at" + current_time + "\n")
            exception_occured = True

    if not exception_occured:
        try:

            print('')
            print('********************************')
            print('Initializing identifying cell value comparison status')
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Identify cell value comparison status started at" + current_time)

            #get the PASS/FAIL status of cell value comparison result 
            celldiff1_0_sts = reportCellComp(cellDiff1_0_pts) 
            celldiff2_1_sts = reportCellComp(cellDiff2_1_pts)
            celldiff3_2_sts = reportCellComp(cellDiff3_2_pts)
            if pd.notna(raster02):
                celldiff0_02_sts = reportCellComp(cellDiff0_02_pts)
            #print('Function reportCellComp is complete')
             
            print('Cell value comparison status has been identified and saved.')
            print('********************************')
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Identify cell value comparison status finished at " + current_time + "\n")

        except:

            print('')
            print('********************************')
            print('Error in identifying cell value comparison status...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Create cell value diff shapefiles failed at" + current_time + "\n")
            exception_occured = True
            

    if not exception_occured:

        try:

            print('')
            print('********************************')
            print('Initializing extracting properties of FVA rasters based on QC checklist')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Read Raster properties started at " + current_time)
                
            raster0_properties = getRasterProperties(raster0)
            raster1_properties = getRasterProperties(raster1)
            raster2_properties = getRasterProperties(raster2)
            raster3_properties = getRasterProperties(raster3)

            if pd.notna(raster02):
                raster02_properties = getRasterProperties(raster02)
            
            print('Raster properties of FVA rasters successfully extracted.')
            print('********************************')
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Read Raster properties finished at " + current_time + "\n")


        except:

            print('')
            print('********************************')
            print('Error in extracting of FVA rasters properties...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Read Raster properties failed at" + current_time + "\n")
            exception_occured = True


    if not exception_occured:
        try:
            print('')
            print('********************************')
            print('Initializing creating QC result csv')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Create QC spreadsheet started at " + current_time)
            
            raster0_properties.extend(("","01FVA vs 00FVA", diff0_1_sts, celldiff1_0_sts, "TBD"))
            raster1_properties.extend(("","02FVA vs 01FVA", diff1_2_sts, celldiff2_1_sts,  "TBD"))
            raster2_properties.extend(("","03FVA vs 02FVA",diff2_3_sts, celldiff3_2_sts,  "TBD"))
            if pd.notna(raster02):
                raster3_properties.extend(("","","", "", ""))
                raster02_properties.extend(("","02PCT vs 00FVA", diff02_0_sts, celldiff0_02_sts, ""))
            else:
                raster3_properties.extend(("","","", "", ""))

            
            if pd.notna(raster02):
                generate_csv(raster0_properties,raster1_properties,raster2_properties,raster3_properties, raster02_properties, OutputCSV)
            else:
                generate_csv_wo02(raster0_properties,raster1_properties,raster2_properties,raster3_properties, OutputCSV)
            
            print('QC result csv successfully created.')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Success! Create QC spreadsheet finished at" + current_time + "\n")
     
            

        except:

            print('')
            print('********************************')
            print('Error in creating QC result csv...')
            print('********************************')
            
            current_time = time.strftime("%m-%d %X",time.localtime())
            log_message("Fail...Create QC spreadsheet failed at" + current_time + "\n")
            exception_occured = True


    print('')
    print('********************************')
    arcpy.CheckInExtension("Spatial")
    print("Spatial Extension checked in")   
    finish_time = time.time()
    time_period = str(timedelta(seconds=(finish_time - start_time)))
    print("Finish processing at", current_time)
    print("The tool has been running for", time_period)
    
    current_time = time.strftime("%m-%d %X",time.localtime())
    log_message("Finish processing at " +  current_time)
    log_message("The tool has been running for " + time_period)


import arcpy
import sys
from sys import argv
import os
import os.path as pth
import json
import requests
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd
from arcpy import AddMessage as msg
from arcpy import AddWarning as warn
from arcpy import AddError as err

def title_text(string):
    """
    The title_text function takes a string and returns a pretty msged title in ArcGIS Details Output.

    :param string: The string to be converted to title text
    :return: msged message on arcgis details output
    """
    msg(u'\u200B')
    msg(f'+-----{string}-----+') 

if __name__ == '__main__':

    # Gather Parameter inputs from tool
    FVA_S_XS_Feature = arcpy.GetParameterAsText(0)
    FVA_L_XS_Elev_Table = arcpy.GetParameterAsText(1)
    Output_XS_Features = arcpy.GetParameterAsText(2)

    layer_file = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\tools\Development\Tool_Scripts\Other_GIS_Tools\XS_02PCT.lyrx"

    # Set the workspace
    arcpy.env.workspace = os.path.dirname(Output_XS_Features)
    arcpy.env.overwriteOutput = True

    #print number of features in s_xs and L_XS_Elev_Table
    msg(f'Total Number of features in S_XS_Feature: {arcpy.GetCount_management(FVA_S_XS_Feature)}')
    msg(f'Total Number of features in L_XS_Elev_Table: {arcpy.GetCount_management(FVA_L_XS_Elev_Table)}')

    # Create temp layer for the XS feature
    temp_XS_layer = "temp_XS_layer"
    arcpy.MakeFeatureLayer_management(FVA_S_XS_Feature, temp_XS_layer)

    #create subset of elev table where "EVENT_TYP" = "0.2 Percent Chance"
    msg("Creating subset of elevations table where EVENT_TYP = 0.2 Percent Chance")
    elev_table_02 = arcpy.TableToTable_conversion(FVA_L_XS_Elev_Table, arcpy.env.workspace, "temp_table", "EVENT_TYP = '0.2 Percent Chance'")
    msg(f'Number of 0.2% features in L_XS_Elev Table: {arcpy.GetCount_management(elev_table_02)}')
    
    #Join the XS feature to the elevations table on XS_LN_ID and XS_LN_ID
    msg("Joining XS feature to elevations table")
    arcpy.management.JoinField(temp_XS_layer, "XS_LN_ID", elev_table_02, "XS_LN_ID", "WSEL")

    #drop all entries where WSEL is null or -8888 or -9999
    msg("Dropping all entries where WSEL is null or -8888")
    arcpy.management.SelectLayerByAttribute(temp_XS_layer, "NEW_SELECTION", "WSEL IS NOT NULL AND WSEL <> -8888 AND WSEL <> -9999")
    arcpy.management.CopyFeatures(temp_XS_layer, Output_XS_Features)

    msg(f'Number of features in output XS features with valid 0.2% WSEL values: {arcpy.GetCount_management(Output_XS_Features)}')

    #set symbology so that output features are yellow and labeled with "0.2% WSEL = " + WSEL
    msg("Setting symbology")
    arcpy.management.ApplySymbologyFromLayer(Output_XS_Features, layer_file)

    #Delete temp files
    msg("Cleaning up temp files")
    arcpy.Delete_management(temp_XS_layer)
    arcpy.Delete_management(arcpy.env.workspace + "\\temp_table")
    msg("Process Complete")


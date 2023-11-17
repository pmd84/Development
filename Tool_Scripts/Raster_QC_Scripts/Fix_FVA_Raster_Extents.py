
import arcpy
import sys
from sys import argv
import os
import json
import requests
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd

def check_out_extension():
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

def Convert_Rasters_to_Polygon(FFRMS_Geodatabase):
    # 1.    Find the FVA0 and FVA03 raster in the geodatabase
    # 2.	turn float grid to Integer (INT tool)
    # 3.	Raster to Polygon, choose simplify polygon option
    # 4.	Merge to a single multipart feature class

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Converting FVA rasters to polygon #####")

    arcpy.env.workspace = FFRMS_Geodatabase

    #Create dictionary of all available FVA rasters
    raster_dict = {}
    expected_values = ["00FVA", "01FVA", "02FVA", "03FVA"]

    for raster in arcpy.ListRasters():
        try:
            Freeboard_Val = raster.split("_")[3]
        except IndexError:
            continue

        if Freeboard_Val in expected_values:
            arcpy.AddMessage("FVA{}_raster: {}".format(Freeboard_Val[:2], raster))
            raster_dict[Freeboard_Val] = raster

    for Freeboard_Val in expected_values:
        if Freeboard_Val not in raster_dict:
            arcpy.AddWarning("{} Raster Not Found".format(Freeboard_Val))

    #Loop through all available rasters
    for FVA_value, FVA_raster in raster_dict.items():
        try:
            arcpy.AddMessage("Converting {0} to polygon".format(FVA_raster))
            raster_name = os.path.basename(FVA_raster)

            #Convert to Int
            FVA_raster_int = Int(FVA_raster)

            #Convert to Polygon
            conversion_type = "MULTIPLE_OUTER_PART"
            output_location = FFRMS_Geodatabase #! Make in_memory after testing
            output_temp_polygon = os.path.join(output_location, "{0}_polygon".format(raster_name))
            FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                        simplify="SIMPLIFY", create_multipart_features=conversion_type)
            
            #Dissolve
            output_dissolved_polygon = os.path.join(output_location, "FVA{0}_polygon".format(FVA_value))
            try:
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

            except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
                arcpy.AddMessage("Failed to dissolve {0} to polygon".format(FVA_raster))
                arcpy.AddMessage("Reparing geometry and trying again")

                FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
                arcpy.management.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

        except Exception as e: #Dissolve still failed after repairing geometry
            arcpy.AddWarning("Failed to convert {0} to polygon".format(FVA_raster))
            arcpy.AddWarning(e)
            sys.exit()

    arcpy.AddMessage("FVA polygons successfully created")

    FVA_Polygon_Dict = {}
    if "00FVA" in raster_dict:
        FVA_Polygon_Dict["00FVA"] = os.path.join(output_location, "FVA00_polygon")

    if "01FVA" in raster_dict:
        FVA_Polygon_Dict["01FVA"] = os.path.join(output_location, "FVA01_polygon")

    if "02FVA" in raster_dict:
        FVA_Polygon_Dict["02FVA"] = os.path.join(output_location, "FVA02_polygon")

    if "03FVA" in raster_dict:
        FVA_Polygon_Dict["03FVA"] = os.path.join(output_location, "FVA03_polygon")

    return FVA_Polygon_Dict

def Find_FVA_Rasters(FFRMS_Geodatabase):

    arcpy.AddMessage(u"\u200B")
    arcpy.AddMessage("##### Finding FVA Rasters in Geodatabase #####")

    arcpy.env.workspace = FFRMS_Geodatabase

    #Create dictionary of all available FVA rasters
    raster_dict = {}
    expected_values = ["00FVA", "01FVA", "02FVA", "03FVA"]

    for raster in arcpy.ListRasters():
        try:
            Freeboard_Val = raster.split("_")[3]
        except IndexError:
            continue

        if Freeboard_Val in expected_values:
            arcpy.AddMessage("FVA{}_raster: {}".format(Freeboard_Val[:2], raster))
            raster_dict[Freeboard_Val] = raster

    for Freeboard_Val in expected_values:
        if Freeboard_Val not in raster_dict:
            arcpy.AddWarning("{} Raster Not Found".format(Freeboard_Val))

    return raster_dict

def Check_FVA_Raster_Difference(lower_FVA, higher_FVA, diff_polygon):
    #Check if there are any differences between the two FVA rasters
    #If there are no differences, no changes are needed to the higher FVA raster
    #If there are differences, changes are needed to the higher FVA raster
    arcpy.AddMessage("Comparing {} to {} rasters".format(lower_FVA, higher_FVA))

    #End tool of no difference polygons exist for a specific FVA comparison
    if not arcpy.Exists(diff_polygon):
        arcpy.AddWarning("{} does not exist.".format(diff_polygon))
        arcpy.AddMessage("No changes to {} raster needed".format(higher_FVA))
        return False

    #Get count of each difference polygon
    count = arcpy.GetCount_management(diff_polygon)
    arcpy.AddMessage("There are {0} features with differences between {1} and {2}".format(count, lower_FVA, higher_FVA))

    if count == 0:
        arcpy.AddMessage("No difference polygons found in {}".format(diff_polygon))
        arcpy.AddMessage("No changes to {} raster needed".format(higher_FVA))
        return False
    else:
        arcpy.AddMessage("Changes to {} raster needed".format(higher_FVA))
        return True

def Convert_Polygon_to_Raster(diff_polygon, Temp_File_Output_Location):
    arcpy.AddMessage("Converting {} to raster".format(diff_polygon))
    diff_raster = os.path.join(Temp_File_Output_Location, "Diff_{0}_{1}_raster".format(lower_FVA, higher_FVA))

    #merge all polygons into a single multipart feature class
    merged_polygon = arcpy.MakeFeatureLayer_management(diff_polygon, "polygon_layer")
    merged_polygon = os.path.join(Temp_File_Output_Location, "Merged_{0}_{1}_diff_polygon".format(lower_FVA, higher_FVA))
    arcpy.Merge_management(inputs=diff_polygon, output=merged_polygon)

    #Convert to raster with all values equal to 1 and cell size equal to 3
    diff_raster = arcpy.FeatureToRaster_conversion(in_features=merged_polygon, field="FID", 
                                                    out_raster=diff_raster, cell_size=3)
    
    return diff_raster

def Add_FVA_Values_To_Raster(diff_raster, lower_FVA, higher_FVA, Temp_File_Output_Location):
    #multiply the error grid times the lower FVA grid to get the FVA value at those locations. 
    #Then grid math to add 1 foot to get the missing higher FVA values

    lower_FVA_Raster = raster_dict[lower_FVA]
    raster_calc = RasterCalculator([diff_raster, lower_FVA_Raster], ["x","y"], "(x*y)+1")
    Add_raster = os.path.join(Temp_File_Output_Location, "Add_to_{0}_raster".format(higher_FVA))
    arcpy.management.CopyRaster(raster_calc, Add_raster)
    
    return Add_raster

if __name__ == "__main__":
    
    #Make sure spatial analyst is checked out
    check_out_extension()

    #Get tool input parameters
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)
    QC_Output_Folder = arcpy.GetParameterAsText(1)

    #Get file paths
    diffFva0_1 = os.path.join(QC_Output_Folder, "diffFva0_1.shp")
    diffFva1_2 = os.path.join(QC_Output_Folder, "diffFva1_2.shp")
    diffFva2_3 = os.path.join(QC_Output_Folder, "diffFva2_3.shp")
    Temp_File_Output_Location = FFRMS_Geodatabase #! Make in_memory after testing

    #Set Environment
    arcpy.env.workspace = FFRMS_Geodatabase
    arcpy.env.overwriteOutput = True

    #Find Rasters in Geodatabase and create dictionary - Keys are FVA values, Values are Raster path
    raster_dict = Find_FVA_Rasters(FFRMS_Geodatabase)

    #Loop through the raster comparision polygons
    for i, diff_polygon in enumerate([diffFva0_1, diffFva1_2, diffFva2_3]):

        lower_FVA = "FVA0{}".format(i)
        higher_FVA = "FVA0{}".format(i+1)

        #Check if there are any differences between the two FVA rasters - if not, skip this FVA comparison
        if not Check_FVA_Raster_Difference(lower_FVA, higher_FVA, diff_polygon):
            continue

        #Convert difference polygons to raster        
        diff_raster = Convert_Polygon_to_Raster(diff_polygon, Temp_File_Output_Location)
        
        #Create new values for diff_raster by setting them equal to lower FVA value + 1 
        Add_raster = Add_FVA_Values_To_Raster(diff_raster, lower_FVA, higher_FVA, Temp_File_Output_Location)
        
        #Mosaic the new raster with the higher FVA raster
        arcpy.AddMessage("Mosaicing additional data to {} raster".format(Add_raster, higher_FVA_Raster))
        higher_FVA_Raster = raster_dict[higher_FVA]
        arcpy.management.Mosaic(inputs=Add_raster,
                                target=higher_FVA_Raster, 
                                mosaic_type="BLEND", 
                                colormap= "LAST", 
                                background_value =-99999,
                                nodata_value =-99999)
        



        

        
    

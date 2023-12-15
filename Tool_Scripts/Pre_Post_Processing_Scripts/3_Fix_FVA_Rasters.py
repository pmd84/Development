
import arcpy
import numpy as np
import sys
from sys import argv
import os
from arcpy import env
from arcpy.sa import *
import shutil
import pandas as pd
from arcpy import management as mgmt
from arcpy import AddMessage as msg
from arcpy import AddWarning as warn
from os import path as pth

def setup_workspace():

    """
    The setup_workspace function creates a lib directory in the current working directory,
    and then creates a file geodatabase called temp.gdb within that lib directory.

    :return: Nothing
    """

    title_text("Setting up Temporary Directory")

    msg("Current Working Directory: {}".format(cur_dir))

    # Ensure that required directories exist
    msg("Making temp folder within Curent Working Directory")
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)

    # Create file geodatabase
    msg("Creating temp.gdb within temp folder")
    if not os.path.exists(temp_gdb):
        mgmt.CreateFileGDB(temp_dir, 'temp.gdb', 'CURRENT')

def title_text(string):
    """
    The title_text function takes a string and returns a pretty msged title in ArcGIS Details Output.

    :param string: The string to be converted to title text
    :return: msged message on arcgis details output
    """
    msg(u'\u200B')
    msg(f'+-----{string}-----+') 
    
def check_out_spatial_analyst():
    """
    The check_out_spatial_analyst function checks out the spatial analyst extension.

    :return: Nothing
    """
    class LicenseError(Exception):
        pass

    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
            msg("Checked out Spatial Extension")
        else:
            raise LicenseError
    except LicenseError:
        msg("Spatial Analyst license is unavailable")
    except:
        msg("Exiting")
        exit()

def find_diff_files(QC_Output_Folder):
    """
    The find_diff_files function finds the difference polygons created by the QC tool.

    :param QC_Output_Folder: The folder where the QC tool output is located
    :return: The file paths for the difference polygons
    """
    
    title_text("Finding Extent Difference Polygons in QC Folder")
    
    diffFva0_1 = os.path.join(QC_Output_Folder, "diffFva0_1.shp")
    diffFva1_2 = os.path.join(QC_Output_Folder, "diffFva1_2.shp")
    diffFva2_3 = os.path.join(QC_Output_Folder, "diffFva2_3.shp")

    if not arcpy.Exists(diffFva0_1):
        diffFva0_1 = os.path.join(QC_Output_Folder, "diffFva1_0.shp") #Fixes descripancy between QC tool versions
    
    for diffFiles in [diffFva0_1, diffFva1_2, diffFva2_3]:
        if not arcpy.Exists(diffFiles):
            warn("{} does not exist in QC Output folder location. Ensure QC tool has been run".format(pth.basename(diffFiles)))
            exit()
        else:
            msg("Found {0}".format(pth.basename(diffFiles)))

    return diffFva0_1, diffFva1_2, diffFva2_3

def find_cellDiff_files(QC_Output_Folder):
    """
    The find_cellDiff_files function finds the cell difference points created by the QC tool.

    :param QC_Output_Folder: The folder where the QC tool output is located
    :return: The file paths for the cell difference points
    """

    title_text("Finding Cell Difference Points in QC Folder")

    cellDiff1_0 = pth.join(QC_Output_Folder, "cellDiff1_0_pts.shp")
    cellDiff2_1 = pth.join(QC_Output_Folder, "cellDiff2_1_pts.shp")
    cellDiff3_2 = pth.join(QC_Output_Folder, "cellDiff3_2_pts.shp")

    for cellDiffFiles in [cellDiff1_0, cellDiff2_1, cellDiff3_2]:
        if not arcpy.Exists(cellDiffFiles):
            warn("{} does not exist in QC Output folder location. Ensure QC tool has been run".format(pth.basename(cellDiffFiles)))
            exit()
        else:
            msg("Found {0}".format(pth.basename(cellDiffFiles)))

    return cellDiff1_0, cellDiff2_1, cellDiff3_2

def Convert_Rasters_to_Polygon(FFRMS_Geodatabase, temp_gdb):
    """
    The Convert_Rasters_to_Polygon function converts the FVA rasters to polygon features.

    :param FFRMS_Geodatabase: The geodatabase where the FVA rasters are located
    :param temp_gdb: The location where the temporary files will be saved

    :return: A dictionary of the FVA polygons. Keys are FVA values, Values are polygon path

    :process: 
    1.  Find the FVA0 and FVA03 raster in the geodatabase
    2.	turn float grid to Integer (INT tool)
    3.	Raster to Polygon, choose simplify polygon option
    4.	Merge to a single multipart feature class

    #NOTE: This function is not currently used by this script
    """

    title_text("Converting FVA Rasters to Polygon")

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
            msg("FVA{}_raster: {}".format(Freeboard_Val[:2], raster))
            raster_dict[Freeboard_Val] = raster

    for Freeboard_Val in expected_values:
        if Freeboard_Val not in raster_dict:
            warn("{} Raster Not Found".format(Freeboard_Val))

    #Loop through all available rasters
    for FVA_value, FVA_raster in raster_dict.items():
        try:
            raster_name = os.path.basename(FVA_raster)
            msg("Converting {0} to polygon".format(raster_name))

            #Convert to Int
            FVA_raster_int = Int(FVA_raster)

            #Convert to Polygon
            conversion_type = "MULTIPLE_OUTER_PART"
            output_temp_polygon = os.path.join(temp_gdb, "{0}_polygon".format(raster_name))
            FVA_polygon = arcpy.RasterToPolygon_conversion(in_raster=FVA_raster_int, out_polygon_features=output_temp_polygon, 
                                                        simplify="SIMPLIFY", create_multipart_features=conversion_type)
            
            #Dissolve
            output_dissolved_polygon = os.path.join(temp_gdb, "FVA{0}_polygon".format(FVA_value))
            try:
                mgmt.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

            except Exception as e: #If Dissolve Fails, try repairing geometry and dissolving again
                msg("Failed to dissolve {0} to polygon".format(FVA_raster))
                msg("Reparing geometry and trying again")

                FVA_polygon = arcpy.RepairGeometry_management(FVA_polygon)
                mgmt.Dissolve(in_features=FVA_polygon, out_feature_class=output_dissolved_polygon)

        except Exception as e: #Dissolve still failed after repairing geometry
            warn("Failed to convert {0} to polygon".format(FVA_raster))
            warn(e)
            exit()

    msg("FVA polygons successfully created")

    FVA_Polygon_Dict = {}
    if "00FVA" in raster_dict:
        FVA_Polygon_Dict["00FVA"] = os.path.join(temp_gdb, "FVA00_polygon")

    if "01FVA" in raster_dict:
        FVA_Polygon_Dict["01FVA"] = os.path.join(temp_gdb, "FVA01_polygon")

    if "02FVA" in raster_dict:
        FVA_Polygon_Dict["02FVA"] = os.path.join(temp_gdb, "FVA02_polygon")

    if "03FVA" in raster_dict:
        FVA_Polygon_Dict["03FVA"] = os.path.join(temp_gdb, "FVA03_polygon")

    return FVA_Polygon_Dict

def Find_FVA_Rasters(FFRMS_Geodatabase):

    """
    The Find_FVA_Rasters function finds the FVA rasters in the FFRMS geodatabase.

    :param FFRMS_Geodatabase: The geodatabase where the FVA rasters are located

    :return: A dictionary of the FVA rasters. Keys are FVA values, Values are raster path

    :process:
    1.  Find all rasters in the geodatabase
    2.  Create dictionary of all available FVA rasters
    3.  Check if all expected FVA rasters are in the geodatabase
    4.  Return dictionary of FVA rasters
    
    """

    title_text("Finding FVA Rasters in Geodatabase")

    #Get current workspace
    current_workspace = arcpy.env.workspace

    #Set workspace to FFRMS Geodatabase to find Rasters
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
            msg("FVA{}_raster: {}".format(Freeboard_Val[:2], raster))
            raster_dict[Freeboard_Val] = pth.join(FFRMS_Geodatabase,raster)

    for Freeboard_Val in expected_values:
        if Freeboard_Val not in raster_dict:
            arcpy.AddError("{} Raster Not Found".format(Freeboard_Val))

    raster_list = [raster_dict["00FVA"], raster_dict["01FVA"], raster_dict["02FVA"], raster_dict["03FVA"]]

    #Reset workspace
    arcpy.env.workspace = current_workspace

    return raster_list, raster_dict

def Check_FVA_Difference_Polygon(lower_FVA, higher_FVA, diff_polygon):
    """
    The Check_FVA_Difference_Polygon function checks if there are any differences between the two FVA rasters.

    :param lower_FVA: The lower FVA raster
    :param higher_FVA: The higher FVA raster
    :param diff_polygon: The difference polygon created by the QC tool

    :return: True if there are differences between the two FVA rasters, False if there are no differences

    :process:
    1.  Count the number of features within the difference polygon feature class
    2.  If there are no features, no changes are needed to the higher FVA raster, return False
    3.  If there are features, changes are needed to the higher FVA raster, return True
    """

    title_text("Checking {} to {} rasters".format(lower_FVA, higher_FVA))

    #End tool of no difference polygons exist for a specific FVA comparison
    if not arcpy.Exists(diff_polygon):
        warn("{} does not exist.".format(diff_polygon))
        msg("No changes to {} raster needed".format(higher_FVA))
        return False

    #Get count of each difference polygon
    count = int(arcpy.GetCount_management(diff_polygon)[0])
    msg("There are {0} features with differences between {1} and {2}".format(count, lower_FVA, higher_FVA))
                     
    if count == 0:
        msg("No difference polygons found in {}".format(diff_polygon))
        msg("No changes to {} raster needed".format(higher_FVA))
        return False
    else:
        msg("Changes to {} raster needed".format(higher_FVA))
        return True

def Convert_Polygon_to_Raster(diff_polygon, lower_FVA, higher_FVA, temp_gdb):
    """
    The Convert_Polygon_to_Raster function converts the difference polygon to a raster.

    :param diff_polygon: The difference polygon created by the QC tool
    :param lower_FVA: The lower FVA raster
    :param higher_FVA: The higher FVA raster
    :param temp_gdb: The location where the temporary files will be saved

    :return: The difference raster

    :process:
    1.  Merge all difference polygons into a single multipart feature class
    2.  Convert to raster with all values equal to 1 and cell size equal to 3
    """
    
    polygon_name = os.path.basename(diff_polygon)
    msg("Converting difference polygon to raster".format(polygon_name))
    diff_raster = os.path.join(temp_gdb, "Diff_{0}_{1}_raster".format(lower_FVA, higher_FVA))

    #merge all polygons into a single multipart feature class
    arcpy.MakeFeatureLayer_management(diff_polygon, "diff_layer")
    merged_polygon = os.path.join(temp_gdb, "Merged_{0}_{1}_diff_polygon".format(lower_FVA, higher_FVA))
    arcpy.Merge_management(inputs="diff_layer", output=merged_polygon)

    #print out fields of merged polygon
    fields = arcpy.ListFields(merged_polygon)

    #If there is not a field called "gridcode", add one, numeric
    if "gridcode" not in [field.name for field in fields]:
        arcpy.AddField_management(merged_polygon, "gridcode", "SHORT")

    #create update cursor and change all values in "gridcode" field to 1
    with arcpy.da.UpdateCursor(merged_polygon, "gridcode") as cursor:
        for row in cursor:
            row[0] = 1
            cursor.updateRow(row)

    #Convert to raster with all values equal to 1 and cell size equal to 3
    diff_raster = arcpy.FeatureToRaster_conversion(in_features=merged_polygon, field="gridcode", 
                                                    out_raster=diff_raster, cell_size=3)
    
    return diff_raster

def Add_FVA_Value_To_Raster(diff_raster, lower_FVA, higher_FVA, raster_dict, temp_gdb):
    """
    Process: Create new values for diff_raster by setting them equal to lower FVA value + 1

    :param diff_raster: The difference raster
    :param lower_FVA: The lower FVA raster
    :param higher_FVA: The higher FVA raster

    :return: The difference raster with the new values

    :process:
    1.  Create new values for diff_raster by setting them equal to lower FVA value + 1
    2.  Round the raster to one decimal place
    3.  Save raster portion to add to temp location

    """

    lower_FVA_Raster = raster_dict[lower_FVA]
    raster_calc = RasterCalculator([arcpy.Raster(diff_raster), arcpy.Raster(lower_FVA_Raster)], ["x","y"], "(x*y)+1")
    raster_calc_rounded = RasterCalculator([raster_calc], ["x"], "Float(Int(x*10.0 + 0.5)/10.0)")

    # #Save raster portion to add to temp location
    # Add_raster = os.path.join(temp_gdb, "Add_to_{0}_raster".format(higher_FVA))
    # try:
    #     mgmt.CopyRaster(raster_calc_rounded, Add_raster)
    # except:
    #     Add_raster = raster_calc_rounded

    Add_raster = raster_calc_rounded
    return Add_raster

def Mosaic_to_Higher_FVA_Raster(higher_FVA, Add_raster):
    """
    The Mosaic_to_Higher_FVA_Raster function mosaics the new raster with the higher FVA raster.

    :param higher_FVA: The higher FVA raster
    :param Add_raster: The difference raster with the new values

    :return: The updated higher FVA raster

    :process:
    1.  Get the higher FVA raster path
    2.  Mosaic the new raster with the higher FVA raster
    """

    higher_FVA_Raster = raster_dict[higher_FVA]
    msg("Mosaicing additional data to {} raster".format(os.path.basename(higher_FVA_Raster)))
    mgmt.Mosaic(inputs=Add_raster,
                            target=higher_FVA_Raster, 
                            mosaic_type="LAST", #ArcPro Guidance suggests this when mosaicing to existing dataset
                            colormap= "FIRST", 
                            background_value =-99999,
                            nodata_value =-99999)
    return higher_FVA_Raster

def Check_Raster_Properties(higher_FVA_Raster):
    """
    The Check_Raster_Properties function check pixel size of updated raster

    :param higher_FVA_Raster: The updated higher FVA raster

    :return: Nothing

    :process:
    1.  Check pixel size of new raster
    2.  If pixel size is not 32_BIT_FLOAT, msg warning message
    3.  If pixel size is 32_BIT_FLOAT, msg message
    """
    
    #check pixel size of new raster
    pixel_type = arcpy.GetRasterProperties_management(higher_FVA_Raster, "VALUETYPE").getOutput(0)
    if pixel_type != "9":
        warn("Output raster is not 32_BIT_FLOAT.  Please check the output raster for inconsistencies.")
    else:
        msg("Output raster is 32_BIT_FLOAT")

def convert_raster_to_polygon(raster, temp_gdb, index, verbose=True):
    """Converts a raster to a polygon shapefile."""
    poly_file = os.path.join(temp_gdb, f"FVA0{index}")
    raster_int = arcpy.sa.Int(arcpy.Raster(raster))

    if verbose:
        msg("Converting FVA0{} raster to polygon".format(index))
    
    arcpy.conversion.RasterToPolygon(raster_int, poly_file, "NO_SIMPLIFY", "", "MULTIPLE_OUTER_PART")
    return poly_file

def determine_extent_difference(poly_higher, poly_lower, temp_gdb, index_higher, index_lower):
    """
    Determines extent difference between two polygons.

    :param poly_higher: The higher FVA polygon
    :param poly_lower: The lower FVA polygon
    :param temp_gdb: The location where the temporary files will be saved
    :param index_higher: The index of the higher FVA polygon
    :param index_lower: The index of the lower FVA polygon

    :return: "Pass" if there are no differences between the two FVA polygons, "Fail" if there are differences

    :process:
    1.  Clip the higher FVA polygon from the lower FVA polygon - leftover polygons are the extent differences
    2.  Convert multipart polygons to singlepart polygons
    3.  Get count of singlepart polygons
    4.  If count is greater than 0, there are extent differences. Return "Fail"
    5.  If count is 0, there are no extent differences. Return "Pass"
    
    """

    msg("Determining extent difference between FVA0{0} and FVA0{1}".format(index_higher, index_lower))

    clip_file = os.path.join(temp_gdb, f"clipFva{index_higher}_{index_lower}")
    diff_file = os.path.join(temp_gdb, f"diffFva{index_higher}_{index_lower}")

    arcpy.analysis.Erase(poly_lower, poly_higher, clip_file)
    arcpy.management.MultipartToSinglepart(clip_file, diff_file)

    feature_count = int(arcpy.GetCount_management(diff_file).getOutput(0))

    if feature_count > 0:
        msg("Differences found between FVA0{0} and FVA0{1} rasters - Fixing...".format(index_higher, index_lower))
        return "Fail"
    else:
        msg(f"FVA0{index_higher} and FVA0{index_lower} extent comparison Pass!")
        return "Pass"

def create_difference_raster(FVA_higher_raster_path, FVA_lower_raster_path):
    #Find where the lower FVA is higher than the upper FVA.

    #Create Raster instance
    FVA_lower_raster = arcpy.Raster(FVA_lower_raster_path)
    FVA_higher_raster = arcpy.Raster(FVA_higher_raster_path)
    
    #Determine differences
    min_raster = arcpy.sa.Minus(FVA_higher_raster,FVA_lower_raster)

    #Check if there are any differences below 0 between the two FVA rasters
    min_diff_val = arcpy.Raster(min_raster).minimum
    msg(f'Smallest difference between rasters is {min_diff_val}')

    return min_diff_val, min_raster

def set_difference_raster_to_lower_FVA_values(min, FVA_lower_raster_path):
    
    lower_FVA_raster = arcpy.Raster(FVA_lower_raster_path)

    con = arcpy.sa.Con(
        in_conditional_raster=min,
        in_true_raster_or_constant=lower_FVA_raster,
        in_false_raster_or_constant=None,
        where_clause="VALUE < 0")
    return con
    
def update_cells_and_mosaic(con, target_raster_path, adjustment):
    raster_FVA = os.path.basename(target_raster_path).split('_')[3]
    if adjustment != 0:
        msg(f'Fixing {raster_FVA} raster values by adding {adjustment} foot to FVA00')

    plus = arcpy.sa.Plus(con, adjustment)

    # Mosaic Raster Calculation result into a copy of the h_fva raster.
    msg(f'Mosaicing fixed cells into the {raster_FVA} raster')
        #mosaic the fixed values into existing higher FVA raster
    mgmt.Mosaic(
        inputs=plus,
        target=target_raster_path,
        mosaic_type="LAST",
        colormap="FIRST",
        background_value=-99999,
        nodata_value=-99999,
        onebit_to_eightbit="NONE",
        mosaicking_tolerance=0,
        MatchingMethod="NONE"
    )

def save_difference_raster(temp_gdb, higher_FVA, lower_FVA, min):
    #save persistent differences to temp gdb
    output_name = f"diff_{higher_FVA}_{lower_FVA}"
    output_path = pth.join(temp_gdb, output_name)
    msg(f'Difference raster path: {output_path}')
    arcpy.CopyRaster_management(min, output_path)

def fix_raster_using_median_values(target_raster_path, min_raster, temp_gdb, save=False):

    FVA_Val = os.path.basename(target_raster_path).split('_')[3]
    target_raster = arcpy.Raster(target_raster_path)

    # Step 1: Set Null on target_raster based on negative_raster
    msg("removing bad values from raster")
    negative_raster = SetNull(min_raster, min_raster, "VALUE > 0") #Sets all values in dif raster > 0 to null
    raster_without_negatives = SetNull(~IsNull(negative_raster), target_raster) #Removes negative difference cells from target raster
    output_1 = f"raster_without_negatives_{FVA_Val}"

    # Step 2: Create and round the median raster
    msg("creating and rounding median raster")
    median_raster = FocalStatistics(raster_without_negatives, NbrRectangle(10,10, "CELL"), "MEDIAN")
    median_raster_rounded = arcpy.sa.Float(Int(median_raster * 10.0 + 0.5) / 10.0)
    output_2 = f"median_raster_rounded_{FVA_Val}"

    # Step 3: Create a subset of the rounded median raster
    raster_median_insert = SetNull(IsNull(negative_raster), median_raster_rounded)
    #raster_median_subset = Con(~IsNull(negative_raster), median_raster_rounded)
    output_3 = f"median_raster_rounded_subset_{FVA_Val}"

    #mosaic
    msg("Mosaicing fixed cells into raster")
    update_cells_and_mosaic(raster_median_insert, target_raster_path, 0)  # Apply the adjusted con raster

    if save:
        msg("Saving rasters to temp gbd")
        raster_list = [raster_without_negatives, median_raster_rounded, raster_median_insert]
        output_list = [output_1, output_2, output_3]
        for raster, output in zip(raster_list, output_list):
            msg(f"Saving {output} to temp gdb")
            try:
                mgmt.CopyRaster(raster, pth.join(temp_gdb, output))
            except:
                try:
                    msg("Could not copy, attempting save")
                    raster.save(pth.join(temp_gdb, output))
                except:
                    warn(f"Failed to save {output} to temp gdb")
            
def calc_fva_diff2(raster_list, temp_gdb):
    title_text("Fixing cell values")

    failed = False
    for i in range(1, len(raster_list)): 
        lower_FVA = "0{}FVA".format(i-1)
        higher_FVA = "0{}FVA".format(i)

        FVA_lower_raster_path = raster_list[i-1]
        FVA_higher_raster_path = raster_list[i]
        FVA0_raster_path = raster_list[0]

        title_text("Calculating FVA Difference between {} and {}".format(lower_FVA, higher_FVA))
        msg(f"Higher Raster: {pth.basename(FVA_higher_raster_path)}")
        msg(f"Lower Raster: {pth.basename(FVA_lower_raster_path)}")

        #Determine if there are any negative differences, and provide difference raster
        min_diff_val, min = create_difference_raster(FVA_higher_raster_path, FVA_lower_raster_path)
        if min_diff_val >= 0:
            msg('No difference values less than 0 found - no changes will be made to {} raster'.format(higher_FVA))
            msg('Moving on to next FVA comparison')
            continue
        msg(f'Cell Value Descrepancies found between {lower_FVA} and {higher_FVA} - Fixing...')
        
        #Set starting point to always fix FVA01 Raster first
        con = set_difference_raster_to_lower_FVA_values(min, FVA0_raster_path) #Set diff to FVA00 values

        #Fix all FVA rasters below the current higher FVA
        if i == 1: #FVA01 is highest raster
            title_text("Fixing FVA01 Raster")
            update_cells_and_mosaic(con, raster_list[i], 1) #Update FVA01

        elif i == 2: #FVA02 is highest raster
            title_text("Fixing FVA01 and FVA02 Raster")
            update_cells_and_mosaic(con, raster_list[i-1], 1)   #Update FVA01 first
            update_cells_and_mosaic(con, raster_list[i], 2)   #Update FVA02 first

            msg("Looking for persisting differences between FVA02 and FVA01 Rasters")
            min_diff_val_fixed1, min_fixed1 = create_difference_raster(raster_list[i], raster_list[i-1]) #compare FVA02 and FVA01
            if min_diff_val_fixed1 <= 0: #if there are any negative values - fix them
                msg("Found persistent cell difference issues - fixing using median values of surrounding cells")
                fix_raster_using_median_values(raster_list[i-1], min_fixed1, temp_gdb, save=False)
                fix_raster_using_median_values(raster_list[i], min_fixed1, temp_gdb, save=False)

        elif i == 3: #FVA03 is highest raster
            title_text("Fixing FVA01, FVA02, and FVA03 Rasters")
            update_cells_and_mosaic(con, raster_list[i-2], 1)   #Update FVA01
            update_cells_and_mosaic(con, raster_list[i-1], 2)   #Update FVA02
            update_cells_and_mosaic(con, raster_list[i], 3)     #Update FVA03

            msg("Looking for persisting differences between FVA03 and FVA02 Rasters")
            min_diff_val_fixed_2, min_fixed2 = create_difference_raster(raster_list[i], raster_list[i-1]) #compare FVA02 and FVA01
            if min_diff_val_fixed_2 <= 0: #if there are any negative values - fix them
                msg("Found persistent cell difference issues - fixing using median values of surrounding cells")
                fix_raster_using_median_values(raster_list[i-2], min_fixed2, temp_gdb, save=False)
                fix_raster_using_median_values(raster_list[i-1], min_fixed2, temp_gdb, save=False)
                fix_raster_using_median_values(raster_list[i], min_fixed2, temp_gdb, save=False)

        #Check to see if this actually fixed the problem!
        min_diff_val_fixed_final, min_fixed_final = create_difference_raster(FVA_higher_raster_path, FVA_lower_raster_path)
        if min_diff_val_fixed_final >= 0:
            msg('No difference values less than 0 found - {0} Raster has been fixed!'.format(higher_FVA))
            msg('Moving on to next FVA comparison')
        else:
            warn('Differences still exist - Raster has not been completely fixed. Please check difference raster for inconsistencies')
            output_name = f"diff_{higher_FVA}_{lower_FVA}_final"
            output_path = pth.join(temp_gdb, output_name)
            msg(f'Difference raster path: {output_path}')
            failed = True
            try:
                arcpy.CopyRaster_management(min_fixed_final, output_path)
            except:
                msg("Could not copy raster to temp gdb")
            msg('Moving on to next FVA comparison')
    
    title_text("Finished fixing cell values")

    return failed
        
def calc_fva_diff(l_fva_raster_path, h_fva_raster_path, temp_gdb):

    """
    The calc_fva_diff function takes two rasters, a low and high FVA raster,
    and calculates the difference between them. The result is mosaic'd into
    a copy of the high FVA raster.

    :param l_fva: Specify the path to the lower fva raster
    :param h_fva: Specify the path to the higher fva raster
    :param output_workspace: Save the output raster to a location of your choice
    :return: The updated FVA raster with the corrected values

    :process:
    1.  Determine whether or not to fix the rasters based on the fix_rasters_dict
    2.  Find where the lower FVA is higher than the upper FVA, create difference raster
    3.  Save the difference raster plus 1 foot
    4.  Fix the higher FVA values
    5.  Mosaic Raster Calculation result into a copy of the h_fva raster.
    """

    l_FVA_val = os.path.basename(l_fva_raster_path).split('_')[3]
    h_FVA_val = os.path.basename(h_fva_raster_path).split('_')[3]

    h_fva_raster = arcpy.Raster(h_fva_raster_path)
    l_fva_raster = arcpy.Raster(l_fva_raster_path)

    title_text("Calculating FVA Difference between {} and {}".format(l_FVA_val, h_FVA_val))

    msg(f"Higher Raster: {h_fva_raster_path}")
    msg(f"Lower Raster: {l_fva_raster_path}")

    #Find where the lower FVA is higher than the upper FVA.
    msg('Identifying differences')
    min = arcpy.sa.Minus(h_fva_raster,l_fva_raster)

    #Check if there are any differences below 0 between the two FVA rasters - if not, skip this FVA comparison
    min_diff_val = arcpy.Raster(min).minimum
    msg(f'Minimum value of difference raster is {min_diff_val}')
    
    if min_diff_val >= 0:
        msg('No difference values less than 0 found - no changes will be made to {} raster'.format(h_FVA_val))
        msg('Moving on to next FVA comparison')
        return h_fva_raster_path
    
    msg('Cell Value Descrepancies found - Fixing...')
    
    con = arcpy.sa.Con(
        in_conditional_raster=min,
        in_true_raster_or_constant=l_fva_raster,
        in_false_raster_or_constant=None,
        where_clause="VALUE < 0")

    msg('Fixing higher FVA values by adding 1 foot to lower FVA values')
    plus = arcpy.sa.Plus(con, 1)

    # Mosaic Raster Calculation result into a copy of the h_fva raster.
    msg('Mosaicing fixed results into the higher FVA raster')

    #mosaic the fixed values into existing higher FVA raster
    mgmt.Mosaic(
        inputs=plus,
        target=h_fva_raster_path,
        mosaic_type="LAST",
        colormap="FIRST",
        background_value=-99999,
        nodata_value=-99999,
        onebit_to_eightbit="NONE",
        mosaicking_tolerance=0,
        MatchingMethod="NONE"
    )

    #Test one more time to see if differences have been fixed
    msg('Checking if differences have been fixed')
    h_fva_raster_fixed = arcpy.Raster(h_fva_raster_path)

    msg('Identifying differences')
    min_fixed = arcpy.sa.Minus(h_fva_raster_fixed,l_fva_raster)

    #Check if there are any differences below 0 between the two FVA rasters - if not, skip this FVA comparison
    min_diff_val_fixed = arcpy.Raster(min_fixed).minimum
    msg(f'Minimum value of difference raster is {min_diff_val_fixed}')
    if min_diff_val_fixed >= 0:
        msg('No difference values less than 0 found - {0} Raster has been fixed!'.format(h_FVA_val))
        msg('Moving on to next FVA comparison')
    else:
        msg('Differences still exist - Raster has not been fixed. Please check raster for inconsistencies')
        msg('Moving on to next FVA comparison')

    return h_fva_raster_path

def check_and_fix_raster_extent_differences(temp_gdb, raster_list):
    """
    Checks and fixes the extent differences between FVA rasters.

    Parameters:
    temp_gdb (str): Location to store temporary files.
    raster_list (list): List of raster files.

    Returns:
    None
    """

    title_text("Converting FVA Rasters to Polygon")
    poly_files = [convert_raster_to_polygon(raster, temp_gdb, i) for i, raster in enumerate(raster_list)]
    
    for i in range(len(raster_list) - 1):
    
        lower_FVA = "0{}FVA".format(i)
        higher_FVA = "0{}FVA".format(i+1)
        lower_polygon = poly_files[i]
        higher_polygon = poly_files[i+1]

        title_text(f"Comparing {lower_FVA} to {higher_FVA} rasters")

        #Check if there are any differences between the two FVA rasters - if not, skip this FVA comparison
        #Function also creates difference polygon
        if determine_extent_difference(poly_files[i+1], poly_files[i], temp_gdb, i+1, i) == "Pass":
            continue

        #Convert difference polygons to raster
        diff_polygon = os.path.join(temp_gdb, f"diffFva{i+1}_{i}")
        diff_raster = Convert_Polygon_to_Raster(diff_polygon, lower_FVA, higher_FVA, temp_gdb)

        #Create new values for diff_raster by setting them equal to lower FVA value + 1
        Add_raster = Add_FVA_Value_To_Raster(diff_raster, lower_FVA, higher_FVA, raster_dict, temp_gdb)

        #Mosaic the new raster with the higher FVA raster - Needs more testing
        higher_FVA_Raster = Mosaic_to_Higher_FVA_Raster(higher_FVA, Add_raster)

        #Ensure output raster is 32_BIT_FLOAT
        Check_Raster_Properties(higher_FVA_Raster)

        #Update higher FVA Polygon based on new raster extents
        convert_raster_to_polygon(higher_FVA_Raster, temp_gdb, i+1, verbose=False)

        #Delete temporary raster
        mgmt.Delete(Add_raster)  

if __name__ == "__main__":
    
    # Set up temp workspace
    cur_dir = fr'{os.getcwd()}' #working directory of script / toolbox
    temp_dir = fr'{cur_dir}\temp'
    temp_gdb = fr'{temp_dir}\temp.gdb'

    #Get tool input parameters
    FFRMS_Geodatabase = arcpy.GetParameterAsText(0)

    #Set Environment
    check_out_spatial_analyst()
    setup_workspace()
    arcpy.env.workspace = temp_gdb
    arcpy.env.overwriteOutput = True

    #Find Rasters in Geodatabase and create dictionary - Keys are FVA values, Values are Raster path
    raster_list, raster_dict = Find_FVA_Rasters(FFRMS_Geodatabase)
 
    ## PART 1: FIXING RASTER EXTENTS
    check_and_fix_raster_extent_differences(temp_gdb, raster_list)
    
    ## PART 2: FIXING CELL VALUES
    failed = calc_fva_diff2(raster_list, temp_gdb)

    #Delete temporary files
    if not failed:
        msg("All FVAs pass - deleting temporary files")
        mgmt.Delete(temp_gdb)
        shutil.rmtree(temp_dir)
    else:
        warn("Not all FVAs pass - review temp geodatabse for discrepancies")
        warn(f"Temp GDB location: {temp_gdb}")

    title_text('Script Complete')

    

    
        



        

        
    

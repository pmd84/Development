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
import zipfile

def title_text(string):
    """
    The title_text function takes a string and returns a pretty msged title in ArcGIS Details Output.

    :param string: The string to be converted to title text
    :return: msged message on arcgis details output
    """
    msg(u'\u200B')
    msg(f'+-----{string}-----+') 

def check_path(path):
    if not pth.exists(path):
        return False
    else:
        return True
    
def find_comments_shapefile(comments_shapefile_location):
    
    msg(f'Looking for comments shapefile in {comments_shapefile_location}')
    comments_shapefile = None
    for file in os.listdir(comments_shapefile_location):
        if "riv_sme_comment" in file and file.endswith(".shp"):
            msg(f'Found comments shapefile: {pth.basename(file)}')
            comments_shapefile = file
            break
    if comments_shapefile is None:
        err(f'No comments shapefile found in {huc_input_folder}. Please check and try again')
        sys.exit()
    return comments_shapefile

def check_target_folder(target_folder, huc_number):
    if not pth.exists(target_folder):
        msg(f'Creating target folder for huc: {huc_number}')
        os.makedirs(target_folder)
    else:
        #check if folder is empty
        if len(os.listdir(target_folder)) == 0:
            msg(f'Target folder for huc: {huc_number} is empty. Proceeding')
        else:
            err(f'Target folder for huc: {huc_number} already exists. Manually delete if you wish to overwrite')
            sys.exit()

if __name__ == '__main__':

    # Gather Parameter inputs from tool
    huc_number = arcpy.GetParameterAsText(0)
    huc_input_folder = arcpy.GetParameterAsText(1)
    huc_output_folder = arcpy.GetParameterAsText(2)
    aoi_erase_area_gdb = arcpy.GetParameterAsText(3)
    comments_shapefile_location = arcpy.GetParameterAsText(4)

    title_text("Checking paths")
    comments_shapefile = find_comments_shapefile(comments_shapefile_location)

    # Set the target folder
    all_hucs_approved_folder = r"\\us0525-ppfss01\shared_projects\203432303012\FFRMS_Zone3\final_deliverables\HUCs_Approved"
    target_folder = pth.join(all_hucs_approved_folder, huc_number)

    # Check if the target folder exists, create it if not
    check_target_folder(target_folder, huc_number)
    
    #set naming conventions
    proper_output_name = f'FVA_Output_{huc_number}'
    proper_inputs_name = f'FVA_Inputs_{huc_number}'
    proper_comments_name = f'riv_sme_comment_{huc_number}'
    proper_gdb_name = f'AOIs_Erase_Areas_{huc_number}.gdb'

    #Set target zip names
    target_inputs_zip = f'{proper_inputs_name}.zip'
    target_outputs_zip = f'{proper_output_name}.zip'
    target_gdb_zip = f'{proper_gdb_name}.zip'
    target_comments_zip = f'{proper_comments_name}.zip'

    #rename all files if needed
    title_text("Renaming files")
    if pth.basename(huc_input_folder) != proper_inputs_name:
        msg(f'Renaming {huc_input_folder} to {proper_inputs_name}')
        try:
            os.rename(huc_input_folder, pth.join(pth.dirname(huc_input_folder), proper_inputs_name))
            huc_input_folder = pth.join(pth.dirname(huc_input_folder), proper_inputs_name)
        except:
            err(f'Error renaming {huc_input_folder} to {proper_inputs_name}. Make sure file is not in use and try again.')
            sys.exit()
    else:       
        msg(f'No need to rename {huc_input_folder}')

    if pth.basename(huc_output_folder) != proper_output_name:
        msg(f'Renaming {huc_output_folder} to {proper_output_name}')
        try:
            os.rename(huc_output_folder, pth.join(pth.dirname(huc_output_folder), proper_output_name))
            huc_output_folder = pth.join(pth.dirname(huc_output_folder), proper_output_name)
        except:
            err(f'Error renaming {huc_output_folder} to {proper_output_name}. Make sure file is not in use and try again.')
            sys.exit()
    else:
        msg(f'No need to rename {huc_output_folder}')

    if pth.basename(aoi_erase_area_gdb) != proper_gdb_name:
        msg(f'Renaming {aoi_erase_area_gdb} to {proper_gdb_name}')
        try:
            os.rename(aoi_erase_area_gdb, pth.join(pth.dirname(aoi_erase_area_gdb), proper_gdb_name))
            aoi_erase_area_gdb = pth.join(pth.dirname(aoi_erase_area_gdb), proper_gdb_name)
        except:
            err(f'Error renaming {aoi_erase_area_gdb} to {proper_gdb_name}. Make sure file is not in use and try again.')
            sys.exit()
    else:
        msg(f"No need to rename {aoi_erase_area_gdb}")

    comment_files = [f for f in os.listdir(comments_shapefile_location) if "riv_sme_comment" in f and not f.endswith(".zip")]
    if pth.basename(comments_shapefile) != f"{proper_comments_name}.shp":
        msg(f'Renaming {comments_shapefile} to {proper_comments_name}')

        for file in comment_files:
            if file.endswith('.shp.xml'):
                extension = '.shp.xml'
        else:
            extension = pth.splitext(file)[1]
            proper_comments_name_with_extension = f'{huc_number}_riv_sme_comment{extension}'

        try:
            os.rename(
                pth.join(comments_shapefile_location, file),
                pth.join(pth.dirname(comments_shapefile), proper_comments_name_with_extension)
            )
            comments_shapefile = pth.join(comments_shapefile_location, proper_comments_name_with_extension)
        except Exception as e:
            err(f'Error renaming {comments_shapefile} to {proper_comments_name_with_extension}. Make sure file is not in use and try again. Exception: {e}')
            sys.exit()
    else:
        msg(f"No need to rename {comments_shapefile}")
    
    comment_files = [f for f in os.listdir(comments_shapefile_location) if "riv_sme_comment" in f and not f.endswith(".zip")]

    #zip all files
    title_text("Zipping files")
    msg(f'Zipping input folder to {target_inputs_zip}')
    shutil.make_archive(pth.join(target_folder, proper_inputs_name), 'zip', pth.dirname(huc_input_folder), proper_inputs_name)

    msg(f'Zipping output folder to {target_outputs_zip}')
    shutil.make_archive(pth.join(target_folder, proper_output_name), 'zip', pth.dirname(huc_output_folder), proper_output_name)

    msg(f'Zipping gdb folder to {target_gdb_zip}')
    shutil.make_archive(pth.join(target_folder, proper_gdb_name), 'zip', pth.dirname(aoi_erase_area_gdb), proper_gdb_name)

    msg(f'Zipping comments shapefile to {target_comments_zip}')
    with zipfile.ZipFile(pth.join(target_folder, target_comments_zip), 'w') as zipf:
        for file in comment_files:
            zipf.write(pth.join(comments_shapefile_location, file), file)
    
    #check if all zips were created
    if not pth.exists(pth.join(target_folder, target_inputs_zip)):
        warn(f'Zip file {target_inputs_zip} not created. Manually zip and move to {target_folder}')
    if not pth.exists(pth.join(target_folder, target_outputs_zip)):
        warn(f'Zip file {target_outputs_zip} not created. Manually zip and move to {target_folder}')
    if not pth.exists(pth.join(target_folder, target_gdb_zip)):
        warn(f'Zip file {target_gdb_zip} not created. Manually zip and move to {target_folder}')
    if not pth.exists(pth.join(target_folder, target_comments_zip)):
        warn(f'Zip file {target_comments_zip} not created. Manually zip and move to {target_folder}')

    #check that zip files are not empty
    if pth.getsize(pth.join(target_folder, target_inputs_zip)) == 0:
        warn(f'Zip file {target_inputs_zip} is empty. Manually zip and move to {target_folder}')
    if pth.getsize(pth.join(target_folder, target_outputs_zip)) == 0:
        warn(f'Zip file {target_outputs_zip} is empty. Manually zip and move to {target_folder}')
    if pth.getsize(pth.join(target_folder, target_gdb_zip)) == 0:
        warn(f'Zip file {target_gdb_zip} is empty. Manually zip and move to {target_folder}')
    if pth.getsize(pth.join(target_folder, target_comments_zip)) == 0:
        warn(f'Zip file {target_comments_zip} is empty. Manually zip and move to {target_folder}')

    msg(f'All zips created and moved to {target_folder}.')
    msg(f'HUC {huc_number} is ready for approval')

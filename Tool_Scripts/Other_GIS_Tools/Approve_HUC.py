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
import re

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
        if "comment" in file and file.endswith(".shp"):
            msg(f'Found comments shapefile: {pth.basename(file)}')
            comments_shapefile = file
            break
    if comments_shapefile is None:
        err(f'No comments shapefile found in {comments_shapefile_location}. Please check and try again')
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
            warn(f'Target folder for huc: {huc_number} already exists. Manually delete if you wish to overwrite')

def contains_word(var_value, word):
    """
    Checks if the variable value contains the given word, accounting for case insensitivity,
    and both singular and plural forms. The word can appear anywhere in the value.

    Args:
    - value: The string to check.
    - word: The word to match against, in singular form.

    Returns:
    - True if the word is contained in the value, False otherwise.
    """
    # Normalize the word to lowercase for case-insensitive comparison
    normalized_word = word.lower()

    # Create a pattern that matches the word in singular or plural form,
    # anywhere in the string, and is case-insensitive.
    # The pattern now doesn't use start ^ and end $ anchors.
    pattern = rf"{normalized_word}s?"

    # Use re.IGNORECASE to make the regular expression case-insensitive
    return bool(re.search(pattern, var_value, re.IGNORECASE))

def rename_folder(folder, value):
    if not contains_word(pth.basename(folder), value): #checks directory name for value
        new_folder_name = f"{folder}_{value}s"
        msg(f'Renaming {folder} to {new_folder_name}')
        try:
            os.rename(folder, new_folder_name)
            folder = pth.join(pth.dirname(folder), new_folder_name) #update folder path to account for new name
        except:
            warn(f'Error renaming {folder} to {new_folder_name}. Make sure file is not in use and try again.')
    else:
        msg(f'No need to rename {folder}')

    return folder
    

def zip_folder(folder, target_folder, target_zip_name):
    """
    Zip the contents of a folder to a target zip file.

    Args:
        folder (str): The path to the folder to be zipped.
        target_folder (str): The path to the target folder where the zip file will be created.
        target_zip_name (str): The name of the zip file to be created.

    Returns:
        None
    """

    msg(f'Zipping {pth.basename(folder)} to {target_zip_name}')

    target_zip_path = pth.join(target_folder, target_zip_name)
    if check_path(target_zip_path):
        warn(f'Zip file {target_zip_path} already exists. Manually delete if you wish to overwrite')
    else:
        target = (pth.splitext(target_zip_path)[0]) #remove .zip extension from target folder path for shutil.make_archive
        shutil.make_archive(target, 'zip', pth.dirname(folder), pth.basename(folder))
    return

def zip_files(files, target_folder, target_zip_name):
    """
    Zips the specified files into a target zip file.

    Args:
        files (list): List of file names to be zipped.
        target_folder (str): Path to the target folder where the zip file will be created.
        target_zip_name (str): Name of the target zip file.

    Returns:
        None
    """

    msg(f'Zipping files to {target_zip_name}')
    with zipfile.ZipFile(pth.join(target_folder, target_zip_name), 'w') as zipf:
        for file in files:
            zipf.write(pth.join(comments_shapefile_location, file), file)
    return
    
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
    
    #Set target zip names
    target_inputs_zip_name = f'FVA_Inputs_{huc_number}.zip'
    target_outputs_zip_name = f'FVA_Output_{huc_number}.zip'
    target_gdb_zip_name = f'AOIs_Erase_Areas_{huc_number}.zip'
    target_comments_zip_name = f'riv_sme_comment_{huc_number}.zip'

    comment_files = [f for f in os.listdir(comments_shapefile_location) if "comment" in f and not f.endswith(".zip")]

    #rename files if they don't have the proper word in them
    title_text("Renaming folders")
    huc_input_folder = rename_folder(huc_input_folder, "input")
    huc_output_folder= rename_folder(huc_output_folder, "output")

    #zip all files
    title_text("Zipping files")
    zip_folder(huc_input_folder, target_folder, target_inputs_zip_name)
    zip_folder(huc_output_folder, target_folder, target_outputs_zip_name)
    zip_folder(aoi_erase_area_gdb, target_folder, target_gdb_zip_name)
    zip_files(comment_files, target_folder, target_comments_zip_name)

    # msg(f'Zipping comments shapefile to {target_comments_zip}')
    # with zipfile.ZipFile(pth.join(target_folder, target_comments_zip), 'w') as zipf:
    #     for file in comment_files:
    #         zipf.write(pth.join(comments_shapefile_location, file), file)
    
    def check_zips(target_folder, target_zip_name):
        if not pth.exists(pth.join(target_folder, target_zip_name)):
            warn(f'Zip file {target_zip_name} not created. Manually zip and move to {target_folder}')
        if pth.getsize(pth.join(target_folder, target_zip_name)) == 0:
            warn(f'Zip file {target_zip_name} is empty. Manually zip and move to {target_folder}')
        return
    
    check_zips(target_folder, target_inputs_zip_name)
    check_zips(target_folder, target_outputs_zip_name)
    check_zips(target_folder, target_gdb_zip_name)
    check_zips(target_folder, target_comments_zip_name)

    msg(f'All zips created and moved to {target_folder}.')
    msg(f'HUC {huc_number} is ready for approval')


 # #rename all files if needed
    # title_text("Renaming files")
    # if pth.basename(huc_input_folder) != proper_inputs_name:
    #     msg(f'Renaming {huc_input_folder} to {proper_inputs_name}')
    #     try:
    #         os.rename(huc_input_folder, pth.join(pth.dirname(huc_input_folder), proper_inputs_name))
    #         huc_input_folder = pth.join(pth.dirname(huc_input_folder), proper_inputs_name)
    #     except:
    #         err(f'Error renaming {huc_input_folder} to {proper_inputs_name}. Make sure file is not in use and try again.')
    #         sys.exit()
    # else:       
    #     msg(f'No need to rename {huc_input_folder}')

    # if pth.basename(huc_output_folder) != proper_output_name:
    #     msg(f'Renaming {huc_output_folder} to {proper_output_name}')
    #     try:
    #         os.rename(huc_output_folder, pth.join(pth.dirname(huc_output_folder), proper_output_name))
    #         huc_output_folder = pth.join(pth.dirname(huc_output_folder), proper_output_name)
    #     except:
    #         err(f'Error renaming {huc_output_folder} to {proper_output_name}. Make sure file is not in use and try again.')
    #         sys.exit()
    # else:
    #     msg(f'No need to rename {huc_output_folder}')

    # if pth.basename(aoi_erase_area_gdb) != proper_gdb_name:
    #     msg(f'Renaming {aoi_erase_area_gdb} to {proper_gdb_name}')
    #     try:
    #         os.rename(aoi_erase_area_gdb, pth.join(pth.dirname(aoi_erase_area_gdb), proper_gdb_name))
    #         aoi_erase_area_gdb = pth.join(pth.dirname(aoi_erase_area_gdb), proper_gdb_name)
    #     except:
    #         err(f'Error renaming {aoi_erase_area_gdb} to {proper_gdb_name}. Make sure file is not in use and try again.')
    #         sys.exit()
    # else:
    #     msg(f"No need to rename {aoi_erase_area_gdb}")

    # comment_files = [f for f in os.listdir(comments_shapefile_location) if "comment" in f and not f.endswith(".zip")]
    # if pth.basename(comments_shapefile) != f"{proper_comments_name}.shp":
    #     msg(f'Renaming {comments_shapefile} to {proper_comments_name}')

    #     for file in comment_files:
    #         if file.endswith('.shp.xml'):
    #             extension = '.shp.xml'
    #     else:
    #         extension = pth.splitext(file)[1]
    #         proper_comments_name_with_extension = f'{huc_number}_riv_sme_comment{extension}'

    #     try:
    #         os.rename(
    #             pth.join(comments_shapefile_location, file),
    #             pth.join(pth.dirname(comments_shapefile), proper_comments_name_with_extension)
    #         )
    #         comments_shapefile = pth.join(comments_shapefile_location, proper_comments_name_with_extension)
    #     except Exception as e:
    #         err(f'Error renaming {comments_shapefile} to {proper_comments_name_with_extension}. Make sure file is not in use and try again. Exception: {e}')
    #         sys.exit()
    # else:
    #     msg(f"No need to rename {comments_shapefile}")
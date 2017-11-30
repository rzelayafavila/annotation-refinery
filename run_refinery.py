import os
import sys
import json
import argparse
from ConfigParser import SafeConfigParser

from download_files import download_all_files
from process_kegg import process_kegg_sets
from process_go import process_go_terms
from process_do import process_do_terms
from tribe_loader import get_oauth_token, load_to_tribe, get_changed_genesets

# Import and set logger
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def process_all_organism_genesets(organism_ini_file, download_folder,
                                  secrets_file=None):
    """
    Downloads and processes files for all geneset types (such as GO and
    KEGG) specified in the .ini config file for a given organism.

    Arguments:
    organism_ini_file -- A string, location of the INI configuration
    file for an organism.

    download_folder -- A string, location of the folder where all files
    containing geneset info (downloaded from GO, KEGG, etc. servers) will
    be saved to.

    secrets_file (Optional) -- A string of the secrets.ini file location.
    This is optional, but it must be included if the files required
    to process any genesets specified in the organism_ini_file require
    a password or a secret API key to be downloaded.

    Returns:
    all_genesets -- A Python list of all the genesets specified to be
    processed in the organism_ini_file. Each geneset in this list is a
    Python dictionary.
    """

    logger.info('Starting to download all files for organism "*.ini" file %s',
                organism_ini_file)
    download_all_files(organism_ini_file, download_folder,
                       secrets_location=secrets_file)
    logger.info('Finished downloading all files for organism "*.ini" file %s',
                organism_ini_file)

    all_genesets = []

    species_config_file = SafeConfigParser()
    species_config_file.read(organism_ini_file)

    if species_config_file.has_section('GO'):
        logger.info('Starting to process GO terms for "*.ini" file %s',
                    organism_ini_file)
        all_go_terms = process_go_terms(organism_ini_file, download_folder)
        all_genesets.extend(all_go_terms)
        logger.info('Finished processing GO terms for "*.ini" file %s',
                    organism_ini_file)

    if species_config_file.has_section('KEGG'):
        logger.info('Starting to process KEGG terms for "*.ini" file %s',
                    organism_ini_file)
        all_kegg_sets = process_kegg_sets(organism_ini_file, download_folder)
        all_genesets.extend(all_kegg_sets)
        logger.info('Finished processing KEGG terms for "*.ini" file %s',
                    organism_ini_file)

    if species_config_file.has_section('DO'):
        logger.info('Starting to process DO terms for "*.ini" file %s',
                    organism_ini_file)
        all_do_terms = process_do_terms(organism_ini_file)
        all_genesets.extend(all_do_terms)
        logger.info('Finished processing DO terms for "*.ini" file %s',
                    organism_ini_file)

    return all_genesets


def main(ini_file_path):

    if not os.path.isfile(ini_file_path):
        logger.error('Main INI configuration file not found in this path: ' +
                     ini_file_path)
        sys.exit(1)

    main_config_file = SafeConfigParser()
    main_config_file.read(ini_file_path)

    if not main_config_file.has_option('download_folder',
                                       'BASE_DOWNLOAD_FOLDER'):
        logger.error('Main configuration file must have a "download_folder" '
                     'section, which must contain a "BASE_DOWNLOAD_FOLDER" '
                     'parameter where download folders will be created for '
                     'each species. Common annotation files for all species'
                     ' will also be saved here.')
        sys.exit(1)

    download_folder = main_config_file.get('download_folder',
                                           'BASE_DOWNLOAD_FOLDER')

    secrets_file = None
    if main_config_file.has_option('main', 'SECRETS_FILE'):
        secrets_file = main_config_file.get('main', 'SECRETS_FILE')

    process_to = main_config_file.get('main', 'PROCESS_TO')

    if main_config_file.has_option('Tribe parameters', 'TRIBE_PUBLIC'):
        tribe_public = main_config_file.getboolean('Tribe parameters',
                                                   'TRIBE_PUBLIC')
    else:
        tribe_public = False

    if main_config_file.has_option('Tribe parameters', 'PREFER_UPDATE'):
        prefer_update = main_config_file.getboolean('Tribe parameters',
                                                    'PREFER_UPDATE')
    else:
        prefer_update = False

    if main_config_file.has_option('Tribe parameters', 'TRIBE_URL'):
        tribe_url = main_config_file.get('Tribe parameters', 'TRIBE_URL')
    else:
        tribe_url = False

    species_dir = main_config_file.get('species files', 'SPECIES_DIR')
    species_files = main_config_file.get('species files', 'SPECIES_FILES')

    # Make a list of the locations of all species files:
    species_files = [filename.strip() for filename in species_files.split(',')]

    for species_file in species_files:

        # Build full species_file path
        species_file = os.path.join(species_dir, species_file)

        all_org_genesets = process_all_organism_genesets(
            species_file, download_folder, secrets_file)

        if process_to == 'Tribe':
            if not tribe_url:
                logger.error('"Tribe parameters" section needs "TRIBE_URL" '
                             'option to be able to save to Tribe.')
                sys.exit(1)

            tribe_token = get_oauth_token(tribe_url, secrets_file)
            changed_genesets = get_changed_genesets(
                species_file, secrets_file, all_org_genesets)

            logger.info('Starting to save gene sets to Tribe')
            if changed_genesets == []:
                logger.info('Annotations have not changed in any gene sets '
                            'for species_file %s.', species_file)
            for geneset in changed_genesets:
                geneset['public'] = tribe_public
                load_to_tribe(ini_file_path, geneset, tribe_token,
                              prefer_update=prefer_update)
            logger.info('Finished saving gene sets to Tribe')

        elif process_to == 'JSON file':
            json_filepath = main_config_file.get('main', 'JSON_FILE')

            with open(json_filepath, "w") as outfile:
                json.dump(all_org_genesets, outfile, indent=2)


if __name__ == "__main__":

    # Logging level can be input as an argument to logging.basicConfig()
    # function to get more logging output (e.g. level=logging.INFO)
    # The default level is logging.WARNING
    logging.basicConfig()

    parser = argparse.ArgumentParser(
        description='Package to download and process knowledge in annotations '
        'databases, convert to JSON, output as a Python list or save to Tribe'
        ' webserver if desired.')

    parser.add_argument(
        '-i', '--INI_file', required=True, dest='ini_file_path',
        help='Main INI configuration file containing settings to run refinery.'
        ' Please consult our README for additional documentation.')

    args = parser.parse_args()
    ini_file_path = args.ini_file_path

    main(ini_file_path)

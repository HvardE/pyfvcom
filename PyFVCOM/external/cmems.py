import copernicusmarine as cm
from PyFVCOM.preproc import Model
from datetime import timedelta

def download_cmems(model: Model):
    '''
    Docstring for download_cmems
    
    :param model: a pyfvcom preproc model instance, we use grid extent and time period to download relevant
                  forcing data from cmems
    '''
    data = 'cmems_mod_glo_phy_my_0.083deg_P1D-m'
    _ = cm.subset(
        dataset_id = data,
        start_datetime = model.start,
        end_datetime = model.end + timedelta(days = 3),
        minimum_longitude = model.grid.lon.min() - 0.3, maximum_longitude = model.grid.lon.max() + 0.3, 
        minimum_latitude = model.grid.lat.min() - 0.3, maximum_latitude = model.grid.lat.max() + 0.3,
    )

def fvcom_cmems_translation():
    fvcom_cmems_names = {
        'v': ['CUR', 'vo'], 
        'u': ['CUR', 'uo'],
        'salinity': ['SAL', 'so'], 
        'temp': ['TEM', 'thetao'],
        'zeta': ['SSH', 'zos']
    }

    modes = {
        'salinity': 'nodes',
        'temp': 'nodes',
        'u': 'elements',
        'v': 'elements',
        'zeta': 'surface'
    }
    return fvcom_cmems_names, modes
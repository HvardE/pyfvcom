import cdsapi
import os
import xarray as xr
import numpy as np
from metpy.calc import relative_humidity_from_dewpoint, specific_humidity_from_dewpoint
from metpy.units import units

from ..preproc import Model

def get_era5(model: Model):
    '''
    Download ERA5 data using the cdsapi
    
    model: pyfvcom.preproc.Model instance
    '''
    variables = [
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "2m_temperature",
        "2m_dewpoint_temperature",
        "surface_pressure",
        "surface_net_solar_radiation",
        "surface_thermal_radiation_downwards",
        "total_cloud_cover",
        "total_precipitation",
        "evaporation",
        "land_sea_mask"
    ]
    dataset = "reanalysis-era5-single-levels"

    # Figure out if we need to download the full year, or if a few months will suffice
    years = np.array([min(model.time.datetime).year, max(model.time.datetime).year])
    months = np.array([min(model.time.datetime).month, max(model.time.datetime).month + 1])
    if max(months) == 13:
        years[1] += 1
    if np.diff(years) == 0:
        year = [str(years[0])]
        month = [f'{m:02d}' for m in range(months[0], months[1] + 1)]
    else:
        year = [str(y) for y in range(years[0], years[1]+1)]
        month = [f'{m:02d}' for m in range(1, 13)]

    # Format the request dictionary
    for variable in variables:
        request = {
            "product_type": ["reanalysis"],
            "variable": [variable],
            "year": year,
            "month": month,
            "day": [
                "01", "02", "03",
                "04", "05", "06",
                "07", "08", "09",
                "10", "11", "12",
                "13", "14", "15",
                "16", "17", "18",
                "19", "20", "21",
                "22", "23", "24",
                "25", "26", "27",
                "28", "29", "30",
                "31"
            ],
            "time": [
                "00:00", "01:00", "02:00",
                "03:00", "04:00", "05:00",
                "06:00", "07:00", "08:00",
                "09:00", "10:00", "11:00",
                "12:00", "13:00", "14:00",
                "15:00", "16:00", "17:00",
                "18:00", "19:00", "20:00",
                "21:00", "22:00", "23:00"
            ],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": [model.grid.lat.max(), model.grid.lon.min(), model.grid.lat.min(), model.grid.lon.max()]
        }
        
        client = cdsapi.Client()
        client.retrieve(dataset, request).download()

def process_era5_download(folder, era5_file = 'ERA5.nc'):
    '''
    Process the data downloaded from ERA5 so that it can be used to create FVCOM forcing files
    
    :param folder: folder the era5 data is stored with
    '''
    # Combine all files to one
    files = [folder + f for f in os.listdir(folder) if len(f) > 26 and '.nc' in f]
    df = xr.open_mfdataset(files)

    # Rename netCDF attributes
    df = df.rename_dims({'valid_time': 'time', 'longitude': 'lon', 'latitude': 'lat'})
    df = df.rename_vars({'valid_time': 'time', 'longitude': 'lon', 'latitude': 'lat'})

    # Calculate specific and relative humidity
    spechum = specific_humidity_from_dewpoint(
        df.sp.compute().data * units.hPa, df.t2m.compute().data * units.K
    ).to('kg/kg')

    relhum = relative_humidity_from_dewpoint(
        df.t2m.compute().data * units.K, df.d2m.compute().data * units.K
    ).to('percent')

    # Dump to the dataset
    df['SPQ'] = (('time', 'lat', 'lon'), spechum)
    df['relative_humidity'] = (('time', 'lat', 'lon'), relhum)
        
    # Return the accumulated data as a speed
    tp = _de_accumulate(df['tp'].compute().data, df['time'].compute().data)
    e  = _de_accumulate(df['e'].compute().data, df['time'].compute().data)

    # Dump the data to the netCDF file
    df.tp.data = tp
    df.e.data  = e

    # Update the attributes to better 
    df['tp'] = df.tp.assign_attrs(units = 'm/s')
    df['tp'] = df.tp.assign_attrs(long_name = 'precipitation rate')
    df['e']  = df.e.assign_attrs(units = 'm/s')
    df['e']  = df.e.assign_attrs(long_name = 'evaporation rate')

    # Dump the data to a netCDF file which can be read by .add_surface_forcing()
    df.to_netcdf(era5_file)

def _de_accumulate(acc, time):
    '''
    For hourly accumulated data
    '''
    # time difference in seconds
    dt = np.diff(time) / np.timedelta64(1, 's')
    
    # Assume the first timestep was as long as the next one, and that the first timestep was the first value
    dt = np.insert(dt, 0, dt[0], axis = 0)

    return acc / dt[:, None, None]

def get_fvcom_era5_names():
    '''
    Translate the variable names in the ERA5 file to FVCOM name conventions
    '''
    fvcom_era5 = {
        'vwind_speed': 'v10',
        'uwind_speed': 'u10',
        'short_wave': 'ssr', 
        'long_wave': 'strd',
        'evap': 'e', 
        'precip': 'tp',
        'cloud_cover': 'tcc',
        'air_pressure': 'sp',
        'air_temperature': 't2m',
        'relative_humidity': 'relative_humidity',
        'SPQ': 'SPQ',
    }
    # Tag what type of grid point we will interpolate stuff to
    elemdata = ['U10', 'V10', 'uwind_speed', 'vwind_speed']
    modes = {}
    for var in fvcom_era5:
        if var in elemdata:
            modes[var] = 'elements'
        else:
            modes[var] = 'nodes'

    return fvcom_era5, modes

"""
Script to extract a collection of Sentinel-2 scenes for a
custom area of interest (AOI).

The script shows how to use the EOdal Mapper class that takes over
data handling such as

* querying of spatio-temporal metadata catalogs to identify
available Sentinel-2 scenes
* merging data from different Sentinel-2 tiles if required
* re-projection of imagery from one UTM zone into another if required
* removal of black-filled (i.e., no-data) scenes

This script works by retrieving Sentinel-2 scenes from
Microsoft Planetary Computer (https://planetarycomputer.microsoft.com).
This requires no authentication required. Alternatively, the same code
can be used to read data from a local EOdal Sentinel archive or a different
STAC provider.

Copyright (C) 2022/23 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from datetime import datetime
from pathlib import Path
from shapely.geometry import box
from typing import List

from eodal.config import get_settings
from eodal.core.scene import SceneCollection
from eodal.core.sensors.sentinel2 import Sentinel2
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs


Settings = get_settings()
# set to False to use a local data archive
Settings.USE_STAC = True


def preprocess_sentinel2_scenes(
    ds: Sentinel2,
    target_resolution: int,
) -> Sentinel2:
    """
    Resample Sentinel-2 scenes and mask clouds, shadows, and snow
    based on the Scene Classification Layer (SCL).

    NOTE:
        Depending on your needs, the pre-processing function can be
        fully customized using the full power of EOdal and its
        interfacing libraries!

    :param target_resolution:
        spatial target resolution to resample all bands to.
    :returns:
        resampled, cloud-masked Sentinel-2 scene.
    """
    # resample scene
    ds.resample(inplace=True, target_resolution=target_resolution)
    # mask clouds, shadows, and snow
    ds.mask_clouds_and_shadows(inplace=True)
    return ds


if __name__ == '__main__':

    import os
    cwd = Path(__file__).parents[1]
    os.chdir(cwd)

    # user-inputs
    # -------------------------- Collection -------------------------------
    collection: str = 'sentinel2-msi'

    # ------------------------- Time Range ---------------------------------
    time_start: datetime = datetime(2022, 6, 10)  		# year, month, day (incl.)
    time_end: datetime = datetime(2022, 6, 15)   		# year, month, day (incl.)

    # ---------------------- Spatial Feature  ------------------------------
    bbox = box(*[6.5738, 46.4565, 7.2628, 47.2190])
    feature = Feature(
        name='lake_neuchatel',
        geometry=bbox,
        epsg=4326,
        attributes={}
    )

    # ------------------------- Metadata Filters ---------------------------
    metadata_filters: List[Filter] = [
        Filter('cloudy_pixel_percentage', '<', 25),
        Filter('processing_level', '==', 'Level-2A')
    ]

    # query the scenes available (no I/O of scenes, this only fetches metadata)
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters)

    # to enhance reproducibility and provide proper documentation, the MapperConfigs
    # can be saved as yaml (and also then be loaded again from yaml)
    mapper_configs.to_yaml('data/sample_mapper_call.yaml')

    # now, a new Mapper instance is created
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()
    # the metadata is loaded into a GeoPandas GeoDataFrame
    mapper.metadata

    # optional: get the least cloudy scene
    # to apply it uncomment the statement below. This
    # will return just a single scene no matter how long the time period chosen.
    # mapper.metadata = mapper.metadata[
    #       mapper.metadata.cloudy_pixel_percentage ==
    #       mapper.metadata.cloudy_pixel_percentage.min()].copy()

    # we tell EOdal how to load the Sentinel-2 scenes using `Sentinel2.from_safe`
    # and pass on some kwargs, e.g., the selection of bands we want to read.
    # Moreover, we tell EOdal to mask out clouds and shadows using the
    # Scene Classification Layer (SCL) which is part of the L2A product.
    # Therefore, we set the `read_scl` flag to True.
    scene_kwargs = {
        'scene_constructor': Sentinel2.from_safe,
        'scene_constructor_kwargs': {'band_selection':
                                     ['B02', 'B03', 'B04', 'B08'],
                                     'read_scl': True},
        'scene_modifier': preprocess_sentinel2_scenes,
        'scene_modifier_kwargs': {'target_resolution': 10}
    }

    # load the scenes available from STAC
    mapper.load_scenes(scene_kwargs=scene_kwargs)
    # the data loaded into `mapper.data` as a EOdal SceneCollection
    mapper.data

    # plot scenes in collection
    f_scenes = mapper.data.plot(band_selection=['blue', 'green', 'red'])

    # EOdal SceneCollections can be made persistent by storing them as serialized
    # pickled objects on disk (and can be loaded from there)
    fpath = Path('data/sample_mapper_data.pkl')
    with open(fpath, 'wb+') as dst:
        dst.write(mapper.data.to_pickle())

    # read data from pickled file object into SceneCollection
    scoll = SceneCollection.from_pickle(stream=fpath)

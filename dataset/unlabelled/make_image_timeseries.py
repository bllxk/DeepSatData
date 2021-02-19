"""
For a set of extracted image crops, make a timeseries for all locations
"""
import argparse
import pandas as pd
import numpy as np
import os
import pickle
from multiprocessing import Pool
if __name__ == "__main__" and __package__ is None:
    from sys import path
    from os.path import dirname as dir
    path.append(dir(dir(path[0])))
    __package__ = "examples"
from utils.date_utils import get_doy
from utils.multiprocessing_utils import split_num_segments


def make_image_timeseries(inputs):
    rank, yearlocs, yearloc_groups, iminfo, year_savedir = inputs#[0]

    saved_files_info = []
    for ii, yearloc in enumerate(yearlocs):
        # ii, yearloc = 0, yearlocs[0]
        if ii % 1e3 == 0:
            print("process %d, location %d of %d" % (rank, ii+1, len(yearlocs)))

        idx = yearloc_groups[yearloc]
        data = iminfo.iloc[idx, :].sort_values(by='DOY').copy()
        data = data.drop_duplicates(subset=['DOY'], keep='first')  # some products downloaded twice

        Y = data['Year'].iloc[0]
        N = data['Nij'].iloc[0]
        W = data['Wij'].iloc[0]
        il = data['il'].iloc[0]
        jl = data['jl'].iloc[0]

        assert all(data['Year'] == Y)
        assert all(data['Nij'] == N)
        assert all(data['Wij'] == W)
        assert all(data['il'] == il)
        assert all(data['jl'] == jl)

        timeseries_sample = {'B01': [], 'B02': [], 'B03': [], 'B04': [], 'B05': [], 'B06': [], 'B07': [],
                             'B08': [], 'B8A': [], 'B09': [], 'B10': [], 'B11': [], 'B12': [], 'doy': []}
        for sample_info in data[['sample_path', 'DOY']].values:

            impath, doy = sample_info

            with open(impath, 'rb') as handle:
                sample = pickle.load(handle, encoding='latin1')

            for key in ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12']:
                timeseries_sample[key].append(sample[key])
            timeseries_sample['doy'].append(np.array(doy))

        for key in ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12', 'doy']:
            timeseries_sample[key] = np.stack(timeseries_sample[key])
        timeseries_sample['year'] = np.array(Y).astype(np.int32)

        timesteps = timeseries_sample['B02'].shape[0]

        savename = os.path.join(year_savedir, "%d_%d_%s.pickle" % (int(N), int(W), Y))
        with open(savename, 'wb') as handle:
            pickle.dump(timeseries_sample, handle, protocol=pickle.HIGHEST_PROTOCOL)

        saved_files_info.append([savename, Y, N, W, sample_size, sample_size, timesteps, il, jl, "completed"])

    saved_files_info = pd.DataFrame(data=saved_files_info, columns=['sample_path', 'Year', 'N', 'W', 'dy', 'dx', 'dt',
                                                                    'win_i', 'win_j', 'status'])
    return saved_files_info


def main():

    global yearloc_groups
    global iminfo
    global year_savedir

    iminfo = pd.read_csv(os.path.join(windows_dir, "extracted_windows_data_info.csv"))
    iminfo = iminfo[~pd.isnull(iminfo['sample_path'])].reset_index(drop=True)
    iminfo['DOY'] = iminfo['Date'].apply(lambda s: get_doy(str(s)))
    iminfo['Year'] = iminfo['Date'].apply(lambda s: str(s)[:4])
    years = iminfo['Year'].drop_duplicates().tolist()
    print("found windows for years %s" % ", ".join(years))

    pool = Pool(num_processes)

    saved_files_info = []

    for year in set(years):

        year_savedir = os.path.join(savedir, year)
        if not os.path.isdir(year_savedir):
            os.makedirs(year_savedir)

        yearloc_groups = iminfo[iminfo['Year'] == year].copy().groupby(['Nij', 'Wij'], as_index=False).groups
        yearlocs = list(yearloc_groups.keys())

        inputs = [[i, yearlocs_, yearloc_groups, iminfo, year_savedir]
                  for i, yearlocs_ in enumerate(split_num_segments(yearlocs, num_processes))]

        df = pool.map(make_image_timeseries, inputs)
        df = pd.concat(df)

        saved_files_info.append(df)

    df = pd.concat(saved_files_info).reset_index(drop=True)
    df.to_csv(os.path.join(savedir, "saved_timeseries_data_info.csv"), index=False)

    paths = df['sample_path'].apply(lambda s: s[len(savedir)+1:])
    paths.to_csv(os.path.join(savedir, "data_paths.csv"), header=None, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PyTorch ImageNet Training')
    parser.add_argument('--windows_dir', help='directory containing sentinel products')
    parser.add_argument('--savedir', help='save directory to extract ground truths in raster mode')
    parser.add_argument('--res', default=10, help='pixel size in meters')
    parser.add_argument('--sample_size', default=24, help='spatial resolution of dataset samples')
    parser.add_argument('--num_processes', default=4, help='number of parallel processes')
    args = parser.parse_args()
    windows_dir = args.windows_dir
    savedir = args.savedir
    res = int(args.res)
    sample_size = int(args.sample_size)
    num_processes = int(args.num_processes)

    main()
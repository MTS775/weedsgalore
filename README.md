# WeedsGalore Dataset :seedling::herb:	

This is the official implementation of the WACV 2025 paper **WeedsGalore: A Multispectral and Multitemporal UAV-based Dataset for Crop and Weed Segmentation in Agricultural Maize Fields.** 
WeedsGalore is a UAV-based multispectral dataset with dense annotations for crop and weed segmentation in maize fields. 
This repository contains code and download links for the dataset and pretrained models. 

[[`arXiv`](https://arxiv.org/abs/2502.13103)], [[`paper`](https://openaccess.thecvf.com/content/WACV2025/html/Celikkan_WeedsGalore_A_Multispectral_and_Multitemporal_UAV-Based_Dataset_for_Crop_and_WACV_2025_paper.html)], [[`dataset`](https://doidata.gfz.de/weedsgalore_e_celikkan_2024/)]

<a href="/img.png" target="_blank">
  <img src="/img.png" alt="WeedsGalore Preview" width="800"/>
</a>

## Dataset
### Download
Follow this [link](https://doidata.gfz.de/weedsgalore_e_celikkan_2024/) to download the dataset. The dataset (`weedsgalore-dataset`, 0.4GB) and full-field orthomosaics (`weedsgalore-orthomosaic`, 12GB, GeoTIFF) can be downloaded separately. 

### Structure

```
weedsgalore-dataset
└── 2023-05-25
    └── images
    └── semantics
    └── instances
    └── logs
└── 2023-05-30
    └── images
    └── ...  
└── ...
└── splits
    └── train.txt
    └── ... 
└── LICENSE.txt
```


### Licence
WeedsGalore dataset is distributed under the [Creative Commons Attribution (CC BY) Licence](https://creativecommons.org/licenses/by/4.0/).
Please refer to the [full licence text](https://doidata.gfz.de/weedsgalore_e_celikkan_2024/) for details. 

## Evaluation

### Requirements
Make sure to have the necessary dependencies installed. They are listed in `requirements.txt`.

### Install Packages
Example: Create a conda environment and install dependencies:
```
conda create -n weedsgalore python=3.7.12 -c conda-forge
conda activate weedsgalore
conda install pytorch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 pytorch-cuda=11.7 -c pytorch -c nvidia
conda install absl-py=1.3.0
conda install pillow=9.0.1
pip install torchmetrics==0.11.4
```

Run the evaluation script, replacing the flags with your paths and parameters:
```
python src/evaluate.py --dataset_path <weedsgalore-dataset_directory> --split test --ckpt <ckpt_directory> --in_channels 5 --num_classes 6
```

### Interactive Streamlit interface

The interface segments a selected date as a parcel, displays the input tiles and their predictions, and reports class proportions and (when semantic masks are present) IoU/mIoU. Tiles are arranged by identifier in a visual grid; the dataset does not provide tile coordinates, so this grid is not a georeferenced orthomosaic.

The original evaluation environment uses Python 3.7, which is too old for the Streamlit version required for directory uploads. Create a separate Python 3.10 environment with PyTorch, Streamlit, and the app dependencies installed together:
```
conda create -n weedsgalore-streamlit python=3.10 -y
conda activate weedsgalore-streamlit
conda install pytorch==1.13.1 torchvision==0.14.1 cpuonly -c pytorch -y
python -m pip install -r requirements-streamlit.txt
```

From the repository root, launch Streamlit through that same Python interpreter:
```
python -m streamlit run src/streamlit_app.py
```

Using `python -m streamlit` ensures the app runs under the active environment, where PyTorch is installed. The command above installs the CPU build; for CUDA, install the matching PyTorch/CUDA build using the [official PyTorch selector](https://pytorch.org/get-started/locally/) instead.

In the sidebar, select the RGB or MSI model and matching checkpoint. Choose a local dataset directory, or upload one date folder (including its `images` directory and optional `semantics` directory) or a ZIP archive. The pretrained checkpoints can be selected from `ckpts/`.

Inference with probabilistic model:
```
python src/evaluate_vimc.py --dataset_path <weedsgalore-dataset_directory> --split test --ckpt <ckpt_directory> --in_channels 5 --num_classes 3 --mc_samples=5
```

You can download pretrained models for DeepLabv3+ [here](https://doidata.gfz.de/weedsgalore_e_celikkan_2024/ckpts.zip) (for both MSI and RGB input, uni-weed and multi-weed case, deterministic and probabilistic variants).

## Training
Run the training script, replacing the flags with your paths and parameters (set `dlv3p_do=True` to run the probabilistic variant):
```
python src/train.py --dataset_path <weedsgalore-dataset_directory> --dataset_size_train 104 --in_channels 5 --num_classes 3 --dlv3p_do True --pretrained_backbone True --ckpt_resnet <path-to-backbone-weights> --batch_size 8 --num_workers 4 --lr 0.001 --epochs 100 --out_dir <output_directory> --log_interval 25 --ckpt_interval 100
```

## License
This project is licensed under the Apache-2.0 License. See LICENSES folder for details. 
```
   Copyright 2024 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
   Copyright 2024 Ekin Celikkan

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

```


## Citation
If you use the dataset or code, please cite our paper:

```
@InProceedings{Celikkan_2025_WACV,
    author    = {Celikkan, Ekin and Kunzmann, Timo and Yeskaliyev, Yertay and Itzerott, Sibylle and Klein, Nadja and Herold, Martin},
    title     = {WeedsGalore: A Multispectral and Multitemporal UAV-Based Dataset for Crop and Weed Segmentation in Agricultural Maize Fields},
    booktitle = {Proceedings of the Winter Conference on Applications of Computer Vision (WACV)},
    month     = {February},
    year      = {2025},
    pages     = {4767-4777}
}
```

# InsightFace_Pytorch

Pytorch0.4.1 codes for InsightFace

------

## 1. Intro

- This repo is a reimplementation of Arcface[(paper)](https://arxiv.org/abs/1801.07698), or Insightface[(github)](https://github.com/deepinsight/insightface)
- For models, including the pytorch implementation of the backbone modules of Arcface and MobileFacenet
- Codes for transform MXNET data records in Insightface[(github)](https://github.com/deepinsight/insightface) to Image Datafolders are provided
- Pretrained models are posted, include the [MobileFacenet](https://arxiv.org/abs/1804.07573) and IR-SE50 in the original paper

------

## 2. Pretrained Models & Performance

[IR-SE50 @ BaiduNetdisk](https://pan.baidu.com/s/12BUjjwy1uUTEF9HCx5qvoQ), [IR-SE50 @ Onedrive](https://1drv.ms/u/s!AhMqVPD44cDOhkPsOU2S_HFpY9dC)

| LFW(%) | CFP-FF(%) | CFP-FP(%) | AgeDB-30(%) | calfw(%) | cplfw(%) | vgg2_fp(%) |
| ------ | --------- | --------- | ----------- | -------- | -------- | ---------- |
| 0.9952 | 0.9962    | 0.9504    | 0.9622      | 0.9557   | 0.9107   | 0.9386     |

[Mobilefacenet @ BaiduNetDisk](https://pan.baidu.com/s/1hqNNkcAjQOSxUjofboN6qg), [Mobilefacenet @ OneDrive](https://1drv.ms/u/s!AhMqVPD44cDOhkSMHodSH4rhfb5u)

| LFW(%) | CFP-FF(%) | CFP-FP(%) | AgeDB-30(%) | calfw(%) | cplfw(%) | vgg2_fp(%) |
| ------ | --------- | --------- | ----------- | -------- | -------- | ---------- |
| 0.9918 | 0.9891    | 0.8986    | 0.9347      | 0.9402   | 0.866    | 0.9100     |

## 3. How to use

- clone

  ```
  git clone https://github.com/TropComplique/mtcnn-pytorch.git
  ```

### 3.1 Data Preparation

#### 3.1.1 Prepare Facebank (For testing over camera or video)

Provide the face images your want to detect in the data/face_bank folder, and guarantee it have a structure like following:

```
data/facebank/
        ---> id1/
            ---> id1_1.jpg
        ---> id2/
            ---> id2_1.jpg
        ---> id3/
            ---> id3_1.jpg
           ---> id3_2.jpg
```

#### 3.1.2 download the pretrained model to work_space/model

If more than 1 image appears in one folder, an average embedding will be calculated

#### 3.2.3 Prepare Dataset ( For training)

download the refined dataset: (emore recommended)

- [emore dataset @ BaiduDrive](https://pan.baidu.com/s/1eXohwNBHbbKXh5KHyItVhQ), [emore dataset @ Dropbox](https://www.dropbox.com/s/wpx6tqjf0y5mf6r/faces_ms1m-refine-v2_112x112.zip?dl=0)
- More Dataset please refer to the [original post](https://github.com/deepinsight/insightface/wiki/Dataset-Zoo)

**Note:** If you use the refined [MS1M](https://arxiv.org/abs/1607.08221) dataset and the cropped [VGG2](https://arxiv.org/abs/1710.08092) dataset, please cite the original papers.

- after unzip the files to 'data' path, run :

  ```
  python prepare_data.py
  ```

  after the execution, you should find following structure:

```
faces_emore/
            ---> agedb_30
            ---> calfw
            ---> cfp_ff
            --->  cfp_fp
            ---> cfp_fp
            ---> cplfw
            --->imgs
            ---> lfw
            ---> vgg2_fp
```

------

### 3.2 detect over camera:

- 1. download the desired weights to model folder:

- [IR-SE50 @ BaiduNetdisk](https://pan.baidu.com/s/12BUjjwy1uUTEF9HCx5qvoQ)
- [IR-SE50 @ Onedrive](https://1drv.ms/u/s!AhMqVPD44cDOhkPsOU2S_HFpY9dC)
- [Mobilefacenet @ BaiduNetDisk](https://pan.baidu.com/s/1hqNNkcAjQOSxUjofboN6qg)
- [Mobilefacenet @ OneDrive](https://1drv.ms/u/s!AhMqVPD44cDOhkSMHodSH4rhfb5u)

- 2 to take a picture, run

  ```
  python take_pic.py -n name
  ```

  press q to take a picture, it will only capture 1 highest possibility face if more than 1 person appear in the camera

- 3 or you can put any preexisting photo into the facebank directory, the file structure is as following:

```
- facebank/
         name1/
             photo1.jpg
             photo2.jpg
             ...
         name2/
             photo1.jpg
             photo2.jpg
             ...
         .....
    if more than 1 image appears in the directory, average embedding will be calculated
```

- 4 to start

  ```
  python face_verify.py 
  ```

- - -

### 3.3 detect over video:

```
​```
python infer_on_video.py -f [video file name] -s [save file name]
​```
```

the video file should be inside the data/face_bank folder

- Video Detection Demo [@Youtube](https://www.youtube.com/watch?v=6r9RCRmxtHE)

### 3.4 Training:

#### 3.4.1 Traditional Training (Original Script)

```bash
python train.py -b [batch_size] -lr [learning rate] -e [epochs]

# Example: Train MobileFaceNet on CASIA-WebFace
python train.py -net mobilefacenet -b 200 -w 4 -d casia-webface -e 20 -s 9981
```

#### 3.4.2 Modern Training (Recommended)

**New training script with improved features:**
- No PIL dependency (uses cv2 only)
- Better progress tracking with tqdm
- Simplified data loading
- TensorBoard integration

**Step 1: Check Dataset**
```bash
# Check if your dataset format is compatible with MobileFaceNet (112x112)
python check_dataset.py
```

**Step 2: Train Model**
```bash
# Basic usage
python train_modern.py -d datasets/casia-webface -b 200 -w 4 -e 20

# With initial step (continue training or adjust step counter)
python train_modern.py -d datasets/casia-webface -b 200 -w 4 -e 20 -s 9981

# Resume from checkpoint
python train_modern.py -d datasets/casia-webface -b 200 -w 4 -e 15 -s 11461 \
    -r work_space/models/mobilefacenet_epoch20_step11461_final.pth
```

**Step 3: Monitor Training**
```bash
# View training curves in TensorBoard
tensorboard --logdir=work_space/log
```

**Training Parameters:**
- `-d, --data_path`: Dataset path (default: `datasets/casia-webface`)
- `-b, --batch_size`: Batch size (default: 200)
- `-e, --epochs`: Number of epochs (default: 10)
- `-lr, --lr`: Learning rate (default: 0.001)
- `-w, --num_workers`: Number of workers (default: 4)
- `-s, --initial_step`: Initial step number for display (default: 0)
- `-r, --resume`: Resume from checkpoint (optional)

**Output:**
- Models saved in: `work_space/models/`
- TensorBoard logs in: `work_space/log/`

---

### 3.5 Model Conversion & Deployment (RK3568)

#### 3.5.1 PyTorch → ONNX Conversion

Convert trained PyTorch model to ONNX format:

```bash
# Convert pretrained model
python convert_to_onnx.py -i mobilefacenet.pth -o mobilefacenet.onnx

# Convert trained model
python convert_to_onnx.py -i work_space/models/mobilefacenet_epoch20_step11461_final.pth \
                          -o mobilefacenet_trained.onnx

# Custom batch size
python convert_to_onnx.py -i mobilefacenet.pth -o mobilefacenet.onnx --batch-size 1
```

**Requirements:**
```bash
pip install onnx onnxruntime
```

**Output:**
- ONNX model with verified accuracy
- Automatic validation against PyTorch output
- Model size: ~4.8 MB

#### 3.5.2 ONNX → RKNN Conversion (For RK3568 NPU)

**⚠️ Must run on Linux (VMware VM recommended)**

**Prerequisites:**
```bash
# Install RKNN-Toolkit2
pip install rknn-toolkit2==2.3.2
```

**Prepare Calibration Dataset:**
```bash
# Create filtered label file (only for int_data folders)
grep -E "casia-webface/000696|casia-webface/000697" \
    datasets/int_data/casia-webface.txt > datasets/int_data/int_data_labels.txt
```

**Convert to RKNN:**
```bash
# With INT8 quantization (recommended, 50 calibration images)
python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn

# Custom calibration image count
python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn --max-calib-images 100

# Without quantization (FP16, slower but more accurate)
python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn --no-quantization

# Custom dataset path
python convert_onnx_to_rknn.py -i mobilefacenet.onnx -o mobilefacenet.rknn \
    -d datasets/int_data -l datasets/int_data/int_data_labels.txt
```

**Conversion Parameters:**
- Target Platform: RK3568
- Quantization: INT8 (w8a8 - 权重8位 + 激活8位)
- Optimization Level: 3
- Preprocessing: RGB, mean=[127.5, 127.5, 127.5], std=[127.5, 127.5, 127.5]

**Output:**
- RKNN model: ~1-2 MB (quantized)
- Quantization accuracy loss: ~1-3%

#### 3.5.3 Deploy on RK3568

**Inference Example:**
```python
import cv2
import numpy as np
from rknnlite.api import RKNNLite

# Load model
rknn = RKNNLite()
rknn.load_rknn('mobilefacenet.rknn')
rknn.init_runtime()

# Prepare input (112x112 RGB image, uint8, [0-255])
img = cv2.imread('face.jpg')
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
img = cv2.resize(img, (112, 112))

# Add batch dimension: (112, 112, 3) -> (1, 112, 112, 3)
img = np.expand_dims(img, axis=0)

# Inference (specify NHWC format)
outputs = rknn.inference(inputs=[img], data_format='nhwc')
embedding = outputs[0][0]  # 512-dim feature vector

# Compare faces (cosine similarity)
similarity = np.dot(embedding1, embedding2)  # threshold: 0.3-0.5

rknn.release()
```

**Input Specification:**
- Size: 112×112
- Format: RGB, HWC (Height, Width, Channels)
- Type: uint8
- Range: [0, 255]
- Preprocessing: Automatically handled by RKNN model

**Output:**
- 512-dimensional feature vector (float32)
- L2-normalized

---

## 4. Project Structure

```
InsightFace_Pytorch/
├── train.py                    # Original training script
├── train_modern.py             # Modern training script (recommended)
├── check_dataset.py            # Dataset format checker
├── convert_to_onnx.py          # PyTorch → ONNX converter
├── convert_onnx_to_rknn.py     # ONNX → RKNN converter (Linux only)
├── model.py                    # Model definitions (MobileFaceNet, IR-SE, ArcFace)
├── config.py                   # Configuration file
├── Learner.py                  # Training learner class
├── data/                       # Data processing utilities
│   └── data_pipe.py
├── mtcnn_pytorch/              # Face detection & alignment
│   └── src/
│       └── align_trans.py      # Face alignment (for deployment)
├── datasets/                   # Training datasets
│   ├── casia-webface/          # Main training dataset
│   └── int_data/               # Calibration dataset for RKNN
│       ├── 000696/
│       ├── 000697/
│       └── int_data_labels.txt
├── work_space/                 # Training outputs
│   ├── models/                 # Saved models
│   └── log/                    # TensorBoard logs
└── mobilefacenet.pth          # Pretrained model
```

---

## 5. References 

- This repo is mainly inspired by [deepinsight/insightface](https://github.com/deepinsight/insightface) and [InsightFace_TF](https://github.com/auroua/InsightFace_TF)

## PS

- PRs are welcome, in case that I don't have the resource to train some large models like the 100 and 151 layers model
- Email : treb1en@qq.com

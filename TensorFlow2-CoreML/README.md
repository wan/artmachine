This project contains two notebooks. The first trains a simple DCGAN model in TensorFlow 2. The second converts that model to CoreML (for use on iOS).

<p align="center"><img src="https://raw.githubusercontent.com/wan/artmachine/master/TensorFlow2-CoreML/images/flowers.png" alt="flowers - grid" width="90%"></p>

## Motivation
I've been playing around with making generative art for iOS. I've also wanted to try out some of the newer dataset and training features in TensorFlow 2. These notebooks put everything together in a project folder for easy reuse and model experimentation.

Actually converting TensorFlow 2 models to CoreML has been a bit of a headache. There's beta support in [coremltools 4.0b1](https://github.com/apple/coremltools/releases), and experimental support in [tensorflow-onnx](https://github.com/onnx/tensorflow-onnx). I've run into a variety of problems e.g. vanishing layer dimensions during conversion, but am optimistic that things will improve in the near future.

## Moving forward
To make a long story short, I've found the simplest path forward (model architecture permitting) is to:
  1. Train your model with TensorFlow 2.x
  2. Save the trained weights
  3. Instantiate an *identical* TensorFlow 1.x model and load those weights
  4. Convert the TF1 model to CoreML with coremltools

Using another framework, e.g. Torch or Caffe, with [onnx-coreml](https://github.com/onnx/onnx-coreml) for CoreML conversion may be simpler for you. That said, expect hiccups.

## Installation / Environment
I'm assuming you know about Python development, and have some background knowledge about Generative Adversarial Networks and deep learning. If you need direction, these articles might be helpful: [Towards Data Science](https://towardsdatascience.com/understanding-generative-adversarial-networks-gans-cd6e4651a29) or [Machine Learning Mastery](https://machinelearningmastery.com/what-are-generative-adversarial-networks-gans/).

The notebooks require different versions of TensorFlow, so be sure to use a virtual environment to manage your runtime.

If you're not already using it, I'd also recommend installing ipykernel and creating two kernels for your Jupyter notebook (one for TensorFlow 1, and the other for TensorFlow 2), e.g.:
activate <your TensorFlow 1 environment>
```bash
python -m ipykernel install --user --name=tf1

activate <your TensorFlow 2 environment>
python -m ipykernel install --user --name=tf2
```

Then select the appropriate kernel in the notebook (Kernel -> Change kernel).

I have things running in a conda environment on a linux desktop with an old-ish GTX 1060 in it. If you want to keep it even simpler (and get access way better hardware), check out [Google Colab](https://colab.research.google.com/).

## Running the CoreML model
You can run model inference using Python and coremltools, but it's more exciting actually running on a device. [ContentView.swift](https://github.com/wan/artmachine/blob/master/TensorFlow2-CoreML/ContentView.swift) provides a very simple example of image generation running in SwiftUI. It uses GameKit's GKGaussianDistribution to create noise input to the model, and converts model output to an image which is displayed in the center of the screen. Tap to generate a new image!

## Animated Images!
<p align="center"><img src="https://raw.githubusercontent.com/wan/artmachine/master/TensorFlow2-CoreML/images/flowers.gif" alt="flowers - animated" width="256"></p>
<p align="center"><img src="https://raw.githubusercontent.com/wan/artmachine/master/TensorFlow2-CoreML/images/clouds.gif" alt="clouds - animated" width="256"></p>
<p align="center"><img src="https://raw.githubusercontent.com/wan/artmachine/master/TensorFlow2-CoreML/images/faces.gif" alt="faces - animated" width="256"></p>

### A model running on the iPhone 11 simulator
<p align="center"><img src="https://raw.githubusercontent.com/wan/artmachine/master/TensorFlow2-CoreML/images/ios-demo.gif" alt="ios - animated" width="256"></p>

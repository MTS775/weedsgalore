
# SPDX-FileCopyrightText: 2024 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-FileCopyrightText: 2024 Ekin Celikkan <ekin.celikkan@gfz-potsdam.de>
# SPDX-License-Identifier: Apache-2.0

from absl import app, flags
import torch
from torchmetrics.classification import MulticlassJaccardIndex, MulticlassCalibrationError, MulticlassConfusionMatrix
from datasets import WeedsGaloreDataset
from torch.utils.data import DataLoader, Subset
import torch.nn as nn
from nets import deeplabv3plus_resnet50
import matplotlib.pyplot as plt
import os

FLAGS = flags.FLAGS

flags.DEFINE_string('dataset', 'weedsgalore', 'options: weedsgalore')
flags.DEFINE_string('dataset_path', '/weedsgalore-dataset', 'dataset directory')
flags.DEFINE_string('split', 'test', 'Options: val, test')
flags.DEFINE_string('sample', '', 'Optional scene name to segment, e.g. 2023-05-25_0750')
flags.DEFINE_string('output', 'segmentation.png', 'Path to save the sample segmentation image')
flags.DEFINE_bool('show', False, 'Display the saved sample segmentation image')

flags.DEFINE_string('network', 'deeplabv3plus', 'options: deeplabv3plus')
flags.DEFINE_string('ckpt', '/dlv3p_msi_6.pth', 'checkpoint directory')

flags.DEFINE_integer('in_channels', 5, 'options: 3 (RGB), 5 (MSI)')
flags.DEFINE_integer('num_classes', 6, 'options: 3 (uni-weed), 6 (multi-weed)')
flags.DEFINE_integer('ignore_index', -1, 'ignore during loss and iou calculation')



def main(_):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using {device}")
    if device.type == 'cuda':
        print(f"Cuda current device: {torch.cuda.current_device()}")
        print(f"Cuda device name: {torch.cuda.get_device_name(0)}")


    net = deeplabv3plus_resnet50(num_classes=FLAGS.num_classes)
    net = net.to(device)

    # first conv to fit input channels
    net.backbone.conv1 = nn.Conv2d(FLAGS.in_channels, net.backbone.conv1.out_channels, kernel_size=7, stride=2, padding=3, bias=False, device=device)

    # load checkpoint
    model_weights_dir = FLAGS.ckpt
    model_dict = torch.load(model_weights_dir, map_location=device)
    net.load_state_dict(model_dict)

    # Dataset and dataloader
    dataset_path = FLAGS.dataset_path
    dataset = WeedsGaloreDataset(dataset_path=dataset_path, dataset_size=None, in_bands=FLAGS.in_channels,
                                        num_classes=FLAGS.num_classes, is_training=False, split=FLAGS.split, augmentation=False)

    eval_dataset = dataset
    if FLAGS.sample:
        samples = dataset.img_list.tolist()
        if FLAGS.sample not in samples:
            raise ValueError(f"Sample '{FLAGS.sample}' was not found in the '{FLAGS.split}' split.")
        eval_dataset = Subset(dataset, [samples.index(FLAGS.sample)])

    dataloader = DataLoader(dataset=eval_dataset, batch_size=1, shuffle=False, num_workers=1, collate_fn=None, drop_last=True)
    dataset_iter = iter(dataloader)

    # iou evaluator
    evaluator = MulticlassJaccardIndex(num_classes=FLAGS.num_classes, average=None, ignore_index=FLAGS.ignore_index).to(device)

    # mcce evaluator
    mcce = MulticlassCalibrationError(num_classes=FLAGS.num_classes, n_bins=FLAGS.num_classes, norm='l1', ignore_index=FLAGS.ignore_index).to(device)

    # confusion matrix
    confmat = MulticlassConfusionMatrix(num_classes=FLAGS.num_classes, normalize='true', ignore_index=FLAGS.ignore_index).to(device)

    net.eval()

    # Run evaluation on dataset
    for i, data in enumerate(dataset_iter):
        features, unique_labels, binary_labels = data
        features, unique_labels, binary_labels = features.to(device), unique_labels.to(device), binary_labels.to(device)

        if FLAGS.num_classes == 3:
            labels = binary_labels
        else:
            labels = unique_labels

        with torch.no_grad():
            out = net(features)

        out = torch.nn.functional.softmax(out, dim=1)

        # pred
        _, pred = torch.max(out, 1)

        if FLAGS.sample:
            rgb = features[0, :3].detach().cpu().permute(1, 2, 0).numpy()
            prediction = pred[0].detach().cpu().numpy()
            class_names = ['background', 'crop'] + [
                f'weed_{class_idx - 1}' for class_idx in range(2, FLAGS.num_classes)
            ]

            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            axes[0].imshow(rgb)
            axes[0].set_title('Input image (RGB)')
            axes[0].axis('off')
            segmentation = axes[1].imshow(
                prediction,
                cmap='tab10',
                vmin=-0.5,
                vmax=FLAGS.num_classes - 0.5,
                interpolation='nearest',
            )
            axes[1].set_title(f'Segmentation: {FLAGS.sample}')
            axes[1].axis('off')
            colorbar = fig.colorbar(segmentation, ax=axes[1], ticks=range(FLAGS.num_classes))
            colorbar.ax.set_yticklabels(class_names)
            fig.tight_layout()

            output_dir = os.path.dirname(os.path.abspath(FLAGS.output))
            os.makedirs(output_dir, exist_ok=True)
            fig.savefig(FLAGS.output, bbox_inches='tight')
            print(f"Segmentation image saved to: {os.path.abspath(FLAGS.output)}")
            if FLAGS.show:
                plt.show()
            plt.close(fig)

        # calculate metric
        evaluator.update(pred, labels)
        scene_scores = evaluator(pred, labels)
        mcce.update(out, labels)
        confmat.update(pred, labels)


    # print scores over all dataset
    print(f"\n{'=' * 40}")
    print(f"{'Overall scores':^40}")
    print(f"{'=' * 40}")
    scores = evaluator.compute()
    print(f'Split: {FLAGS.split}')
    print(f'mIoU: {scores.mean() * 100:.2f}%')
    print(f'iou bg: {scores[0] * 100:.2f}%')
    print(f'iou crop: {scores[1] * 100:.2f}%')
    for weed_idx, weed_iou in enumerate(scores[2:], start=2):
        print(f'iou weed_{weed_idx-1}: {weed_iou * 100:.2f}%')
    print(f"ECE: {mcce.compute()}")


if __name__ == '__main__':
    app.run(main)

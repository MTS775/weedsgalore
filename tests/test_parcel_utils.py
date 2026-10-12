import io
import unittest
import zipfile

import numpy as np
from PIL import Image

from src.parcel_utils import (
    index_parcel_files,
    index_zip,
    read_band,
    read_reference,
    scores_from_confusion,
)


class ParcelUtilsTests(unittest.TestCase):
    def test_groups_bands_and_optional_label_by_date_and_tile(self):
        entries = [
            ("2023-05-25/images/2023-05-25_0109_R.png", b"r"),
            ("2023-05-25/images/2023-05-25_0109_G.png", b"g"),
            ("2023-05-25/images/2023-05-25_0109_B.png", b"b"),
            ("2023-05-25/semantics/2023-05-25_0109.png", b"label"),
            ("2023-05-25/instances/2023-05-25_0109.png", b"instance"),
        ]

        parcels, ignored = index_parcel_files(entries)

        self.assertEqual(ignored, [])
        tile = parcels["2023-05-25"]["2023-05-25_0109"]
        self.assertEqual(tile["bands"], {"R": b"r", "G": b"g", "B": b"b"})
        self.assertEqual(tile["label"], b"label")

    def test_indexes_zip_members_without_extracting_archive(self):
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr("2023-05-25/images/2023-05-25_0109_R.png", b"red")

        parcels, ignored = index_zip(archive_buffer.getvalue())
        reference = parcels["2023-05-25"]["2023-05-25_0109"]["bands"]["R"]

        self.assertEqual(ignored, [])
        self.assertEqual(read_reference(reference), b"red")

    def test_read_band_keeps_uint16_input_as_float32(self):
        encoded = io.BytesIO()
        Image.fromarray(np.asarray([[0, 32768, 65535]], dtype=np.uint16)).save(
            encoded, format="PNG"
        )

        band = read_band(encoded.getvalue())

        self.assertEqual(band.dtype, np.float32)
        np.testing.assert_allclose(band, [[0.0, 32768.0 / 65535.0, 1.0]])

    def test_iou_ignores_classes_with_no_ground_truth_or_prediction(self):
        confusion = np.asarray([[3, 1, 0], [1, 2, 0], [0, 0, 0]])

        iou, mean_iou = scores_from_confusion(confusion)

        np.testing.assert_allclose(iou[:2], [3.0 / 5.0, 2.0 / 4.0])
        self.assertTrue(np.isnan(iou[2]))
        self.assertAlmostEqual(mean_iou, (3.0 / 5.0 + 2.0 / 4.0) / 2.0)


if __name__ == "__main__":
    unittest.main()

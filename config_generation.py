#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy
import colour
import PyOpenColorIO

from lib.agx_math import (
    calculate_ev_to_sr,
    calculate_sr_to_ev
)

from lib.agx_file import (
    OCIOWriteConfig,
    OCIOCreateAllocationTransform
)


if __name__ == "__main__":
    bt709_npm = colour.models.BT709_COLOURSPACE.RGB_to_XYZ_matrix
    bt2020_npm = colour.models.BT2020_COLOURSPACE.RGB_to_XYZ_matrix

    st2084 = colour.io.LUT1D(
        colour.models.eotf_ST2084(
            colour.io.LUT1D.linear_table(4096, [0., 1.])
        ),
        'ST2084 OETF',
        [0., 1.]
    )

    testing = [1., 0.]
    print(*testing)
    print(st2084.table[1])
    colour.write_LUT(st2084, "./ocio/luts/st2084_to_nits.spi1d", decimals=16)

    # Shape a scaling matrix for ST.2084
    ocio_st2084_scale = numpy.identity(4)
    ocio_st2084_scale /= 100.
    ocio_st2084_scale = ocio_st2084_scale.flatten()
    ocio_st2084_scale[-1] = 1.
    
    print(ocio_st2084_scale)
    # Shape the BT.709 to XYZ array for OpenColorIO
    ocio_bt709_to_xyz = numpy.pad(
        bt709_npm,
        [(0, 1), (0, 1)],
        mode='constant'
    )
    ocio_bt709_to_xyz = ocio_bt709_to_xyz.flatten()
    ocio_bt709_to_xyz[-1] = 1.

    print(ocio_bt709_to_xyz.shape)
    # Shape the BT.2020 to XYZ array for OpenColorIO
    ocio_bt2020_to_xyz = numpy.pad(
        bt2020_npm,
        [(0, 1), (0, 1)],
        mode='constant'
    )
    ocio_bt2020_to_xyz = ocio_bt2020_to_xyz.flatten()
    ocio_bt2020_to_xyz[-1] = 1.

    config_name = "Krita"
    minimum_exposure = calculate_sr_to_ev(
        0.001 / 100
    )
    maximum_exposure = calculate_sr_to_ev(
        10000. / 100
    )

    sr_middle_grey = 0.18

    config = PyOpenColorIO.Config()

    LUT_SEARCH_PATH = ["luts", "looks"]
    config.setSearchPath(':'.join(LUT_SEARCH_PATH))

    config.setRole(
        PyOpenColorIO.Constants.ROLE_SCENE_LINEAR,
        "BT.2020 SR Linear"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_REFERENCE,
        "BT.2020 SR Linear"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_COLOR_TIMING,
        config_name + " Log"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_COMPOSITING_LOG,
        config_name + " Log"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_COLOR_PICKING,
        config_name + " Log"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_DATA,
        "Non-Colour Data"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_DEFAULT,
        config_name + " Log"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_MATTE_PAINT,
        config_name + " Log"
    )

    config.setRole(
        PyOpenColorIO.Constants.ROLE_TEXTURE_PAINT,
        config_name + " Log"
    )

    # Basic BT.2020 scene referred linear colourspace
    colorspace = PyOpenColorIO.ColorSpace(
        family="Colorimetry",
        name="BT.2020 SR Linear"
    )
    colorspace.setDescription(
        "REC.2020 scene referred linear"
    )
    colorspace.setBitDepth(PyOpenColorIO.Constants.BIT_DEPTH_F32)
    colorspace.setAllocationVars(
        [
            numpy.log2(
                calculate_ev_to_sr(
                    minimum_exposure,
                    sr_middle_grey
                )
            ),
            numpy.log2(
                calculate_ev_to_sr(
                    maximum_exposure,
                    sr_middle_grey
                )
            )
        ]
    )
    colorspace.setAllocation(
        PyOpenColorIO.Constants.ALLOCATION_LG2
    )
    config.addColorSpace(colorspace)

    colorspace = PyOpenColorIO.ColorSpace(
        family="Core",
        name="Non-Colour Data"
    )

    colorspace.setDescription("Non-Colour Data")

    colorspace.setBitDepth(PyOpenColorIO.Constants.BIT_DEPTH_F32)

    colorspace.setIsData(True)

    config.addColorSpace(colorspace)

    # BT.709 colorimetry to BT.2020
    colorspace = PyOpenColorIO.ColorSpace(
        family="Colorimetry",
        name="BT.709 SR Linear"
    )
    colorspace.setDescription(
        "Colorimetric BT.709 transform"
    )
    # colorspace.setBitDepth(PyOpenColorIO.Constants.BIT_DEPTH_F32)
    # colorspace.setAllocationVars([-12.473931188, 12.526068812])
    # colorspace.setAllocation(PyOpenColorIO.Constants.ALLOCATION_LG2)
    transform_bt709_to_xyz = PyOpenColorIO.MatrixTransform(
        ocio_bt709_to_xyz
    )
    transform_bt2020_to_xyz = PyOpenColorIO.MatrixTransform(
        ocio_bt2020_to_xyz
    )
    transform_bt2020_to_xyz.setDirection(
        PyOpenColorIO.Constants.TRANSFORM_DIR_INVERSE
    )
    transform = PyOpenColorIO.GroupTransform()
    transform.setTransforms(
        [
            transform_bt709_to_xyz,
            transform_bt2020_to_xyz
        ]
    )
    colorspace.setTransform(
        transform,
        PyOpenColorIO.Constants.COLORSPACE_DIR_TO_REFERENCE
    )
    config.addColorSpace(colorspace)

    # Full colorimetric sRGB 2.2 transform
    colorspace = PyOpenColorIO.ColorSpace(
        family="Colorimetry",
        name="BT.709 E2.2 Nonlinear"
    )
    colorspace.setDescription(
        "Colorimetric BT.709 2.2 Transfer"
    )
    transform_transfer = PyOpenColorIO.ExponentTransform()
    transform_transfer.setValue([2.2, 2.2, 2.2, 1.])
    transform_colorimetry = PyOpenColorIO.ColorSpaceTransform()
    transform_colorimetry.setSrc("BT.709 SR Linear")
    transform_colorimetry.setDst("BT.2020 SR Linear")

    transform = PyOpenColorIO.GroupTransform()
    transform.setTransforms(
        [
            transform_transfer,
            transform_colorimetry
        ]
    )
    colorspace.setTransform(
        transform,
        PyOpenColorIO.Constants.COLORSPACE_DIR_TO_REFERENCE
    )
    config.addColorSpace(colorspace)

    # Full colorimetric BT.2020 ST.2084 transform
    colorspace = PyOpenColorIO.ColorSpace(
        family="Colorimetry",
        name="BT.2020 ST.2084 Nonlinear"
    )
    colorspace.setDescription(
        "Colorimetric BT.2020 ST.2084 Transfer"
    )
    transform_scale = PyOpenColorIO.MatrixTransform(
        ocio_st2084_scale
    )
    transform_transfer = PyOpenColorIO.FileTransform()
    transform_transfer.setSrc("st2084_to_nits.spi1d")
    transform_transfer.setInterpolation(PyOpenColorIO.Constants.INTERP_LINEAR)

    transform = PyOpenColorIO.GroupTransform()
    transform.setTransforms(
        [
            transform_transfer,
            transform_scale
        ]
    )
    colorspace.setTransform(
        transform,
        PyOpenColorIO.Constants.COLORSPACE_DIR_TO_REFERENCE
    )
    config.addColorSpace(colorspace)

    # Non colour data transform
    colorspace = PyOpenColorIO.ColorSpace(
        family="Core",
        name="Non-Colour Data"
    )
    colorspace.setDescription("Non-Colour Data")
    colorspace.setBitDepth(PyOpenColorIO.Constants.BIT_DEPTH_F32)
    colorspace.setIsData(True)
    config.addColorSpace(colorspace)

    # Add base shaper / log encoding
    colorspace = PyOpenColorIO.ColorSpace()

    colorspace.setAllocationVars(
        [
            numpy.log2(
                calculate_ev_to_sr(
                    minimum_exposure,
                    sr_middle_grey)
            ),
            numpy.log2(
                calculate_ev_to_sr(
                    maximum_exposure,
                    sr_middle_grey
                )
            )
        ]
    )

    colorspace.setBitDepth(PyOpenColorIO.Constants.BIT_DEPTH_F32)
    colorspace.setDescription(config_name + " Log")
    colorspace.setFamily("Transfer")
    colorspace.setIsData(False)
    colorspace.setName(config_name + " Log")

    colorspace.setAllocationVars(
        [
            numpy.log2(
                calculate_ev_to_sr(
                    minimum_exposure,
                    sr_middle_grey
                )
            ),
            numpy.log2(
                calculate_ev_to_sr(
                    maximum_exposure,
                    sr_middle_grey
                )
            )
        ]
    )

    colorspace.setAllocation(PyOpenColorIO.Constants.ALLOCATION_LG2)
    transform = OCIOCreateAllocationTransform(
        numpy.log2(
            calculate_ev_to_sr(
                minimum_exposure,
                sr_middle_grey
            )
        ),
        numpy.log2(
            calculate_ev_to_sr(
                maximum_exposure,
                sr_middle_grey
            )
        ),
        type=PyOpenColorIO.Constants.ALLOCATION_LG2
    )

    colorspace.setTransform(
        transform,
        PyOpenColorIO.Constants.COLORSPACE_DIR_FROM_REFERENCE
    )

    config.addColorSpace(colorspace)

    displays = [
        [
            "100 nit REC.709 E2.2 Nonlinear", 100, [
                ["2.2 Transfer", "BT.709 E2.2 Nonlinear"],
                ["Scene Referred Linear", "BT.709 SR Linear"]
            ]
        ],
        # ["HDR10 1000 nit REC.2020", 1000, ["Linear", "ST.2084"]],
        [
            "10000 nit BT.2020 ST.2084 Nonlinear", 10000, [
                ["ST.2084 Transfer", "BT.2020 ST.2084 Nonlinear"],
                ["Scene Referred Linear", "BT.2020 SR Linear"]
            ]
        ]
    ]

    for display_name, nits, views in displays:
        for view_name, view_transform in views:
            config.addDisplay(display_name, view_name, view_transform)

    config.setActiveDisplays(displays[0][0])
    config.setActiveViews(views[0][0])

    OCIOWriteConfig("ocio", config)

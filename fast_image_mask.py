# fast_image_mask.py
import numpy as np
from numba import njit, prange
from PIL import Image


# MasksConfig constants
mHardWinterStreetConditionGreyToleranceValue = 31
mHardWinterStreetConditionRGBSumLargerThanValue = 256
mHardWinterStreetConditionRGBSumLessThanValue = 508
mHardWinterStreetAverageAdditionRandomFactor = 6.0
mHardWinterStreetAverageAdditionRandomOffset = -2.0
mHardWinterStreetAverageFactor = 0.9
mHardWinterStreetAverageRedOffset = 0
mHardWinterStreetAverageGreenOffset = 0
mHardWinterStreetAverageBlueOffset = 10
mHardWinterDarkConditionRGBSumLessThanValue = 96
mHardWinterDarkConditionRGDiffValue = 12
mHardWinterDarkConditionRandomLessThanValue = 0.21
mHardWinterDarkRandomFactor = 11.0
mHardWinterDarkRedOffset = 250
mHardWinterDarkGreenOffset = 253
mHardWinterDarkBlueOffset = 253
mHardWinterVeryDarkStreetFactor = 1.47
mHardWinterVeryDarkNormalFactor = 1.27
mHardWinterAlmostWhiteConditionRGBSumLargerEqualThanValue = 608
mHardWinterAlmostWhiteConditionRGBSumLessEqualThanValue = 752
mHardWinterAlmostWhiteRedFactor = 1.06
mHardWinterAlmostWhiteGreenFactor = 1.09
mHardWinterAlmostWhiteBlueFactor = 1.1
mHardWinterRestConditionRGDiffValue = 10
mHardWinterRestRedMin = 250
mHardWinterRestGBOffsetToRed = -2
mHardWinterRestCondition2RGDiffValue = 10
mHardWinterRestForestConditionRGBSumLessThan = 240
mHardWinterRestForestGreenOffset = -30
mHardWinterRestNonForestGreenLimit = 250
mHardWinterRestNonForestRedOffsetToGreen = -5
mHardWinterRestNonForestBlueOffsetToGreen = -2
mHardWinterRestRestBlueMin = 250
mHardWinterRestRestRGToBlueOffset = -4

mWinterStreetGreyConditionGreyToleranceValue = 47
mWinterStreetGreyConditionRGBSumLargerThanValue = 256
mWinterStreetGreyMaxFactor = 1.4
mWinterStreetGreyRandomFactor = 11.0
mWinterDarkConditionRGBSumLessThanValue = 288
mWinterDarkConditionRGBSumLargerThanValue = 18
mWinterDarkRedAddition = 4
mWinterDarkGreenAddition = -11
mWinterDarkBlueAddition = 3
mWinterBrightConditionRGBSumLargerEqualThanValue = 288
mWinterBrightConditionRGBSumLessThanValue = 752
mWinterBrightRedAddition = -20
mWinterBrightGreenAddition = -14
mWinterBrightBlueAddition = -12
mWinterGreenishConditionBlueIntegerFactor = 7
mWinterGreenishConditionGreenIntegerFactor = 5
mWinterGreenishRedAddition = -13
mWinterGreenishGreenAddition = -25
mWinterGreenishBlueAddition = 0
mWinterRestRedAddition = 0
mWinterRestGreenAddition = -12
mWinterRestBlueAddition = 0

mAutumnDarkConditionRGBSumLessThanValue = 288
mAutumnDarkConditionRGBSumLargerThanValue = 18
mAutumnDarkRedAddition = 9
mAutumnDarkGreenAddition = -8
mAutumnDarkBlueAddition = 8
mAutumnBrightConditionRGBSumLargerEqualThanValue = 288
mAutumnBrightConditionRGBSumLessThanValue = 752
mAutumnBrightRedAddition = -16
mAutumnBrightGreenAddition = -10
mAutumnBrightBlueAddition = -7
mAutumnGreenishConditionBlueIntegerFactor = 7
mAutumnGreenishConditionGreenIntegerFactor = 5
mAutumnGreenishRedAddition = -9
mAutumnGreenishGreenAddition = -20
mAutumnGreenishBlueAddition = 0
mAutumnRestRedAddition = 0
mAutumnRestGreenAddition = -16
mAutumnRestBlueAddition = 0

mSpringDarkConditionRGBSumLessThanValue = 288
mSpringDarkConditionRGBSumLargerThanValue = 18
mSpringDarkRedAddition = 9
mSpringDarkGreenAddition = -8
mSpringDarkBlueAddition = 8
mSpringBrightConditionRGBSumLargerEqualThanValue = 288
mSpringBrightConditionRGBSumLessThanValue = 752
mSpringBrightRedAddition = 15
mSpringBrightGreenAddition = 10
mSpringBrightBlueAddition = -10
mSpringGreenishConditionBlueIntegerFactor = 7
mSpringGreenishConditionGreenIntegerFactor = 5
mSpringGreenishRedAddition = 10
mSpringGreenishGreenAddition = 5
mSpringGreenishBlueAddition = -5
mSpringRestRedAddition = 0
mSpringRestGreenAddition = 0
mSpringRestBlueAddition = 0

mNightStreetGreyConditionGreyToleranceValue = 11
mNightStreetConditionRGBSumLessEqualThanValue = 510
mNightStreetConditionRGBSumLargerThanValue = 0
mNightStreetLightDots1DitherProbabily = 0.01
mNightStreetLightDots2DitherProbabily = 0.02
mNightStreetLightDots3DitherProbabily = 0.05
mNightStreetLightDot1Red = 255
mNightStreetLightDot1Green = 255
mNightStreetLightDot1Blue = 255
mNightStreetLightDot2Red = 255
mNightStreetLightDot2Green = 200
mNightStreetLightDot2Blue = 140
mNightStreetLightDot3Red = 255
mNightStreetLightDot3Green = 180
mNightStreetLightDot3Blue = 80
mNightStreetRedAddition = 100
mNightStreetGreenAddition = 50
mNightStreetBlueAddition = -50
mNightNonStreetLightness = 0.5
mSpareOutWaterForSeasonsGeneration = False
mNoSnowInWaterForWinterAndHardWinter = False
mHardWinterStreetsConditionOn = True


def _load_mask(mask_path):
    """Load mask file and determine water pixels (black pixels)."""
    try:
        mask_img = Image.open(mask_path).convert('RGB')
        mask_arr = np.array(mask_img)
        # Water is black pixel (R=0, G=0, B=0)
        return ((mask_arr[:, :, 0] == 0) &
                (mask_arr[:, :, 1] == 0) &
                (mask_arr[:, :, 2] == 0))
    except:
        # If mask doesn't exist or error, assume no water
        return None


def _load_image(img_path):
    """Load image and convert to RGB numpy array."""
    img = Image.open(img_path).convert('RGB')
    return np.array(img)


@njit(cache=True)
def _apply_night_transform(image, mask):
    """Numba-optimized night transformation."""
    h, w, c = image.shape
    result = image.copy().astype(np.int32)

    for i in prange(h):
        for j in range(w):
            # Process all pixels (mSpareOutWaterForSeasonsGeneration = False)

            r = result[i, j, 0]
            g = result[i, j, 1]
            b = result[i, j, 2]

            sum_rgb = r + g + b

            # Check street conditions
            is_grey = ((abs(r - b) <= mNightStreetGreyConditionGreyToleranceValue) and
                       (abs(r - g) <= mNightStreetGreyConditionGreyToleranceValue) and
                       (abs(g - b) <= mNightStreetGreyConditionGreyToleranceValue))
            is_street = is_grey and (sum_rgb > mNightStreetConditionRGBSumLargerThanValue) and (sum_rgb <= mNightStreetConditionRGBSumLessEqualThanValue)

            if is_street:
                rand_val = np.random.uniform(0.0, 1.0)
                if rand_val < mNightStreetLightDots1DitherProbabily:
                    result[i, j, 0] = mNightStreetLightDot1Red
                    result[i, j, 1] = mNightStreetLightDot1Green
                    result[i, j, 2] = mNightStreetLightDot1Blue
                elif rand_val < mNightStreetLightDots2DitherProbabily:
                    result[i, j, 0] = mNightStreetLightDot2Red
                    result[i, j, 1] = mNightStreetLightDot2Green
                    result[i, j, 2] = mNightStreetLightDot2Blue
                elif rand_val < mNightStreetLightDots3DitherProbabily:
                    result[i, j, 0] = mNightStreetLightDot3Red
                    result[i, j, 1] = mNightStreetLightDot3Green
                    result[i, j, 2] = mNightStreetLightDot3Blue
                else:
                    r += mNightStreetRedAddition
                    g += mNightStreetGreenAddition
                    b += mNightStreetBlueAddition
            else:
                # Normal land/water - make factor 2 darker
                r = int(mNightNonStreetLightness * float(r))
                g = int(mNightNonStreetLightness * float(g))
                b = int(mNightNonStreetLightness * float(b))

            # Clamp RGB values to [0, 255]
            if r > 255: r = 255
            elif r < 0: r = 0
            if g > 255: g = 255
            elif g < 0: g = 0
            if b > 255: b = 255
            elif b < 0: b = 0

            result[i, j, 0] = r
            result[i, j, 1] = g
            result[i, j, 2] = b

    return result.astype(np.uint8)


@njit(cache=True)
def _apply_hard_winter_transform(image, mask):
    """Numba-optimized hard winter transformation."""
    h, w, c = image.shape
    result = image.copy().astype(np.int32)

    for i in prange(h):
        for j in range(w):
            # Process all pixels (mSpareOutWaterForSeasonsGeneration = False)

            r = result[i, j, 0]
            g = result[i, j, 1]
            b = result[i, j, 2]

            sum_rgb = r + g + b

            # Street processing
            is_grey_streets = ((abs(r - b) <= mHardWinterStreetConditionGreyToleranceValue) and
                               (abs(r - g) <= mHardWinterStreetConditionGreyToleranceValue) and
                               (abs(g - b) <= mHardWinterStreetConditionGreyToleranceValue))

            if mHardWinterStreetsConditionOn \
                    and is_grey_streets \
                    and sum_rgb >= mHardWinterStreetConditionRGBSumLargerThanValue \
                    and sum_rgb < mHardWinterStreetConditionRGBSumLessThanValue:
                avg_val = float(sum_rgb) / 3.0
                rand_val = np.random.uniform(0.0, 1.0)

                r = int(mHardWinterStreetAverageFactor * (avg_val + rand_val * mHardWinterStreetAverageAdditionRandomFactor + mHardWinterStreetAverageAdditionRandomOffset)
                        + mHardWinterStreetAverageRedOffset)
                g = int(mHardWinterStreetAverageFactor * (avg_val + rand_val * mHardWinterStreetAverageAdditionRandomFactor + mHardWinterStreetAverageAdditionRandomOffset)
                        + mHardWinterStreetAverageGreenOffset)
                b = int(mHardWinterStreetAverageFactor * (avg_val + rand_val * mHardWinterStreetAverageAdditionRandomFactor + mHardWinterStreetAverageAdditionRandomOffset)
                        + mHardWinterStreetAverageBlueOffset)
            elif sum_rgb < mHardWinterDarkConditionRGBSumLessThanValue:
                # Dark pixel processing
                snow_allowed = not mNoSnowInWaterForWinterAndHardWinter

                if snow_allowed and g > (r - mHardWinterDarkConditionRGDiffValue) and g > b:
                    rand_val = np.random.uniform(0.0, 1.0)
                    if rand_val < mHardWinterDarkConditionRandomLessThanValue:
                        r = mHardWinterDarkRedOffset + int(rand_val * mHardWinterDarkRandomFactor)
                        g = mHardWinterDarkGreenOffset + int(rand_val * mHardWinterDarkRandomFactor)
                        b = mHardWinterDarkBlueOffset + int(rand_val * mHardWinterDarkRandomFactor)
                else:
                    # Leave very dark pixel unchanged
                    if is_grey_streets:  # streets
                        r = int(mHardWinterVeryDarkStreetFactor * float(r))
                        g = int(mHardWinterVeryDarkStreetFactor * float(g))
                        b = int(mHardWinterVeryDarkStreetFactor * float(b))
                    else:  # normal
                        r = int(mHardWinterVeryDarkNormalFactor * float(r))
                        g = int(mHardWinterVeryDarkNormalFactor * float(g))
                        b = int(mHardWinterVeryDarkNormalFactor * float(b))
            elif sum_rgb >= mHardWinterAlmostWhiteConditionRGBSumLargerEqualThanValue:
                if sum_rgb <= mHardWinterAlmostWhiteConditionRGBSumLessEqualThanValue:
                    r = int(mHardWinterAlmostWhiteRedFactor * float(r))
                    g = int(mHardWinterAlmostWhiteGreenFactor * float(g))
                    b = int(mHardWinterAlmostWhiteBlueFactor * float(b))
            else:
                # Dominating color logic
                snow_allowed = not mNoSnowInWaterForWinterAndHardWinter

                if snow_allowed and r > (g + mHardWinterRestConditionRGDiffValue) and r > b:
                    if r < mHardWinterRestRedMin:
                        r = mHardWinterRestRedMin
                    g = r + mHardWinterRestGBOffsetToRed
                    b = r + mHardWinterRestGBOffsetToRed
                elif g >= (r - mHardWinterRestCondition2RGDiffValue) and g >= b:
                    if not snow_allowed or sum_rgb < mHardWinterRestForestConditionRGBSumLessThan:  # forest
                        g += mHardWinterRestForestGreenOffset
                    else:  # non-forest
                        if g < mHardWinterRestNonForestGreenLimit:
                            g = mHardWinterRestNonForestGreenLimit
                        r = g + mHardWinterRestNonForestRedOffsetToGreen
                        b = g + mHardWinterRestNonForestBlueOffsetToGreen
                elif snow_allowed and b >= r and b > g:
                    if b < mHardWinterRestRestBlueMin:
                        b = mHardWinterRestRestBlueMin
                    r = b + mHardWinterRestRestRGToBlueOffset
                    g = b + mHardWinterRestRestRGToBlueOffset

            # Clamp RGB values to [0, 255]
            if r > 255: r = 255
            elif r < 0: r = 0
            if g > 255: g = 255
            elif g < 0: g = 0
            if b > 255: b = 255
            elif b < 0: b = 0

            result[i, j, 0] = r
            result[i, j, 1] = g
            result[i, j, 2] = b

    return result.astype(np.uint8)


@njit(cache=True)
def _apply_autumn_transform(image, mask):
    """Numba-optimized autumn transformation."""
    h, w, c = image.shape
    result = image.copy().astype(np.int32)

    for i in prange(h):
        for j in range(w):
            # Process all pixels (mSpareOutWaterForSeasonsGeneration = False)

            r = result[i, j, 0]
            g = result[i, j, 1]
            b = result[i, j, 2]

            sum_rgb = r + g + b

            if sum_rgb > mAutumnDarkConditionRGBSumLargerThanValue and sum_rgb < mAutumnDarkConditionRGBSumLessThanValue:
                # Dark pixel but not black
                r += mAutumnDarkRedAddition
                g += mAutumnDarkGreenAddition
                b += mAutumnDarkBlueAddition
            elif sum_rgb >= mAutumnBrightConditionRGBSumLargerEqualThanValue and sum_rgb < mAutumnBrightConditionRGBSumLessThanValue:
                # Rather bright pixel
                r += mAutumnBrightRedAddition
                g += mAutumnBrightGreenAddition
                b += mAutumnBrightBlueAddition
            elif mAutumnGreenishConditionBlueIntegerFactor * b < mAutumnGreenishConditionGreenIntegerFactor * g:
                # Very greenish pixel
                r += mAutumnGreenishRedAddition
                g += mAutumnGreenishGreenAddition
                b += mAutumnGreenishBlueAddition
            else:
                # Rest condition
                r += mAutumnRestRedAddition
                g += mAutumnRestGreenAddition
                b += mAutumnRestBlueAddition

            # Clamp RGB values to [0, 255]
            if r > 255: r = 255
            elif r < 0: r = 0
            if g > 255: g = 255
            elif g < 0: g = 0
            if b > 255: b = 255
            elif b < 0: b = 0

            result[i, j, 0] = r
            result[i, j, 1] = g
            result[i, j, 2] = b

    return result.astype(np.uint8)


@njit(cache=True)
def _apply_spring_transform(image, mask):
    """Numba-optimized spring transformation."""
    h, w, c = image.shape
    result = image.copy().astype(np.int32)

    for i in prange(h):
        for j in range(w):
            # Process all pixels (mSpareOutWaterForSeasonsGeneration = False)

            r = result[i, j, 0]
            g = result[i, j, 1]
            b = result[i, j, 2]

            sum_rgb = r + g + b

            if sum_rgb > mSpringDarkConditionRGBSumLargerThanValue and sum_rgb < mSpringDarkConditionRGBSumLessThanValue:
                # Dark pixel but not black
                r += mSpringDarkRedAddition
                g += mSpringDarkGreenAddition
                b += mSpringDarkBlueAddition
            elif sum_rgb >= mSpringBrightConditionRGBSumLargerEqualThanValue and sum_rgb < mSpringBrightConditionRGBSumLessThanValue:
                # Rather bright pixel
                r += mSpringBrightRedAddition
                g += mSpringBrightGreenAddition
                b += mSpringBrightBlueAddition
            elif mSpringGreenishConditionBlueIntegerFactor * b < mSpringGreenishConditionGreenIntegerFactor * g:
                # Very greenish pixel
                r += mSpringGreenishRedAddition
                g += mSpringGreenishGreenAddition
                b += mSpringGreenishBlueAddition
            else:
                # Rest condition
                r += mSpringRestRedAddition
                g += mSpringRestGreenAddition
                b += mSpringRestBlueAddition

            # Clamp RGB values to [0, 255]
            if r > 255: r = 255
            elif r < 0: r = 0
            if g > 255: g = 255
            elif g < 0: g = 0
            if b > 255: b = 255
            elif b < 0: b = 0

            result[i, j, 0] = r
            result[i, j, 1] = g
            result[i, j, 2] = b

    return result.astype(np.uint8)


@njit(cache=True)
def _apply_winter_transform(image, mask):
    h, w, c = image.shape
    result = image.copy().astype(np.int32)

    for i in prange(h):
        for j in range(w):
            r = result[i, j, 0]
            g = result[i, j, 1]
            b = result[i, j, 2]

            sum_rgb = r + g + b

            is_grey_streets = ((abs(r - b) <= mWinterStreetGreyConditionGreyToleranceValue) and
                               (abs(r - g) <= mWinterStreetGreyConditionGreyToleranceValue) and
                               (abs(g - b) <= mWinterStreetGreyConditionGreyToleranceValue))

            if is_grey_streets and sum_rgb > mWinterStreetGreyConditionRGBSumLargerThanValue:
                max_val = max(r, g, b)
                r = int(np.random.uniform(0.0, 1.0) * mWinterStreetGreyRandomFactor + max_val)
                g = int(np.random.uniform(0.0, 1.0) * mWinterStreetGreyRandomFactor + max_val)
                b = int(np.random.uniform(0.0, 1.0) * mWinterStreetGreyRandomFactor + max_val)
            elif sum_rgb > mWinterDarkConditionRGBSumLargerThanValue and sum_rgb < mWinterDarkConditionRGBSumLessThanValue:
                r += mWinterDarkRedAddition
                g += mWinterDarkGreenAddition
                b += mWinterDarkBlueAddition
            elif sum_rgb >= mWinterBrightConditionRGBSumLargerEqualThanValue and sum_rgb < mWinterBrightConditionRGBSumLessThanValue:
                r += mWinterBrightRedAddition
                g += mWinterBrightGreenAddition
                b += mWinterBrightBlueAddition
            elif mWinterGreenishConditionBlueIntegerFactor * b < mWinterGreenishConditionGreenIntegerFactor * g:
                r += mWinterGreenishRedAddition
                g += mWinterGreenishGreenAddition
                b += mWinterGreenishBlueAddition
            else:
                r += mWinterRestRedAddition
                g += mWinterRestGreenAddition
                b += mWinterRestBlueAddition

            # Clamp RGB values to [0, 255]
            if r > 255: r = 255
            elif r < 0: r = 0
            if g > 255: g = 255
            elif g < 0: g = 0
            if b > 255: b = 255
            elif b < 0: b = 0

            result[i, j, 0] = r
            result[i, j, 1] = g
            result[i, j, 2] = b

    return result.astype(np.uint8)


# Public interface functions
def create_night(imgName, outName, maskName):
    image = _load_image(imgName)
    mask = _load_mask(maskName)
    result = _apply_night_transform(image, mask)
    result_img = Image.fromarray(result, mode='RGB')
    result_img.save(outName, format='BMP')


def create_hard_winter(imgName, outName, maskName):
    image = _load_image(imgName)
    mask = _load_mask(maskName)
    result = _apply_hard_winter_transform(image, mask)
    result_img = Image.fromarray(result, mode='RGB')
    result_img.save(outName, format='BMP')


def create_autumn(imgName, outName, maskName):
    image = _load_image(imgName)
    mask = _load_mask(maskName)
    result = _apply_autumn_transform(image, mask)
    result_img = Image.fromarray(result, mode='RGB')
    result_img.save(outName, format='BMP')


def create_spring(imgName, outName, maskName):
    image = _load_image(imgName)
    mask = _load_mask(maskName)
    result = _apply_spring_transform(image, mask)
    result_img = Image.fromarray(result, mode='RGB')
    result_img.save(outName, format='BMP')


def create_winter(imgName, outName, maskName):
    image = _load_image(imgName)
    mask = _load_mask(maskName)
    result = _apply_winter_transform(image, mask)
    result_img = Image.fromarray(result, mode='RGB')
    result_img.save(outName, format='BMP')


if __name__ == '__main__':
    print("Result from create_night:", create_night("TEST.bmp", "TEST_night.bmp", "TEST.tif"))
    print("Result from create_hard_winter:", create_hard_winter("TEST.bmp", "TEST_hard_winter.bmp", "TEST.tif"))
    print("Result from create_autumn:", create_autumn("TEST.bmp", "TEST_autumn.bmp", "TEST.tif"))
    print("Result from create_spring:", create_spring("TEST.bmp", "TEST_spring.bmp", "TEST.tif"))
    print("Result from create_winter:", create_winter("TEST.bmp", "TEST_winter.bmp", "TEST.tif"))

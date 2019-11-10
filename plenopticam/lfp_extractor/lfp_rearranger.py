#!/usr/bin/env python

__author__ = "Christopher Hahne"
__email__ = "info@christopherhahne.de"
__license__ = """
    Copyright (c) 2019 Christopher Hahne <info@christopherhahne.de>

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

import numpy as np

from plenopticam.misc import Normalizer
from plenopticam.lfp_extractor import LfpViewpoints, LfpExporter
from plenopticam.lfp_extractor.lfp_contrast import LfpContrast
from plenopticam.misc.hist_eq import HistogramEqualizer
from plenopticam.lfp_extractor.lfp_hotpixels import LfpHotPixels
from plenopticam.lfp_extractor.lfp_color_eq import LfpColorEqualizer


class LfpRearranger(LfpViewpoints):

    def __init__(self, lfp_img_align=None, *args, **kwargs):
        super(LfpRearranger, self).__init__(*args, **kwargs)

        self._lfp_img_align = Normalizer(lfp_img_align).uint16_norm() if lfp_img_align is not None else None
        self._dtype = self._lfp_img_align.dtype

    def var_init(self):

        # initialize output image array
        if len(self._lfp_img_align.shape) == 3:
            m, n, p = self._lfp_img_align.shape
        else:
            m, n, p = (self._lfp_img_align.shape[0], self._lfp_img_align.shape[1], 1)

        self._vp_img_arr = np.zeros([int(self._M), int(self._M), int(m/self._M), int(n/self._M), p], dtype=self._dtype)

    def main(self):

        # rearrange light-field to viewpoint representation
        self.viewpoint_extraction()

        # histogram equalization
        if self.cfg.params[self.cfg.opt_cont]:
            obj = HistogramEqualizer(img=self.vp_img_arr)
            self.vp_img_arr = obj.lum_eq()
            #self.vp_img_arr = obj.awb_eq()
            del obj

        # color and contrast handling
        obj = LfpContrast(vp_img_arr=self.vp_img_arr, cfg=self.cfg, sta=self.sta, p_lo=0.0, p_hi=1.0)
        # contrast automation
        #obj.contrast_bal()
        self.vp_img_arr = obj.vp_img_arr
        del obj

        # remove hot pixels if option is set
        if self.cfg.params[self.cfg.opt_hotp]:
            obj = LfpHotPixels(vp_img_arr=self.vp_img_arr, cfg=self.cfg, sta=self.sta)
            obj.main()
            self.vp_img_arr = obj.vp_img_arr
            del obj

        # color equalization
        if self.cfg.params[self.cfg.opt_colo]:
            obj = LfpColorEqualizer(vp_img_arr=self.vp_img_arr, cfg=self.cfg, sta=self.sta)
            obj.main()
            self.vp_img_arr = obj._vp_img_arr
            del obj

        obj = LfpContrast(vp_img_arr=self.vp_img_arr, cfg=self.cfg, sta=self.sta, p_lo=0.0, p_hi=1.0)
        # automatic white balance
        if self.cfg.params[self.cfg.opt_awb_]:
            obj.p_lo = 0.005
            obj.p_hi = 0.995
            obj.auto_wht_bal()
            obj.p_lo = 0
            obj.p_hi = 1

        # automatic saturation
        if self.cfg.params[self.cfg.opt_sat_]:
            obj.sat_bal()

        self.vp_img_arr = obj.vp_img_arr
        del obj

        # write viewpoint data to hard drive
        if self.cfg.params[self.cfg.opt_view]:
            obj = LfpExporter(vp_img_arr=self.vp_img_arr, cfg=self.cfg, sta=self.sta)
            obj.write_viewpoint_data()
            del obj

    def viewpoint_extraction(self):

        # print status
        self.sta.status_msg('Viewpoint extraction', self.cfg.params[self.cfg.opt_prnt])
        self.sta.progress(None, self.cfg.params[self.cfg.opt_prnt])

        # initialize basic light-field parameters
        self.var_init()

        # rearrange light field to multi-view image representation
        for j in range(self._M):
            for i in range(self._M):

                # check interrupt status
                if self.sta.interrupt:
                    return False

                # extract viewpoint by pixel rearrangement
                self._vp_img_arr[j, i, :, :, :] = self._lfp_img_align[j::self._M, i::self._M, :]

                # print status
                percentage = (((j*self._M+i+1)/self._M**2)*100)
                self.sta.progress(percentage, self.cfg.params[self.cfg.opt_prnt])

        return True
